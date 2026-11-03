"""Agente LangGraph: o modelo escolhe a ferramenta e redige; o código confere os números.

Fluxo de cada mensagem do cliente:

    agent -> tools -> agent ... -> check -> fim
                                     \\-> agent (nota interna pedindo para refazer)

- Se a resposta sai sem nenhuma consulta, o check pede uma vez que consulte. Obrigar a chamada
  (tool_choice) seria errado para saudação e fora do escopo, e o Ollama não aceita.
- Todo R$, parcela (Nx) e data da resposta precisa aparecer nos resultados das ferramentas
  da conversa ou no que o cliente escreveu. Se não aparece, o check pede para refazer uma vez;
  na segunda falha, troca a resposta por uma mensagem fixa que oferece a equipe.
- Chamadas repetidas na mesma resposta são descartadas, e mais de MAX_TOOL_ROUNDS rodadas de
  ferramenta numa mesma mensagem também terminam na mensagem fixa.
"""

from __future__ import annotations

import functools
import json
import re
from decimal import Decimal
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from emporio import tools
from emporio.config import reference_date
from emporio.prompts import system_prompt
from emporio.rules import COMPLAINT_RESPONSE, STORE_INFO

# Notas internas são mensagens do usuário marcadas; a interface não as mostra.
NOTE = "emporio_note"
NUDGE, CORRECTION = "nudge", "correction"
NUDGE_TEXT = (
    "[nota interna do sistema, não é o cliente] Você respondeu sem consultar as ferramentas. "
    "Se a resposta depende de algum dado da loja, chame a ferramenta agora, em vez de dizer "
    "que vai consultar. Se não depende (saudação, assunto fora do escopo), responda de novo "
    "normalmente. Não comente esta nota com o cliente."
)
CORRECTION_TEXT = (
    "[nota interna do sistema, não é o cliente] Sua resposta citou valores que não aparecem nos "
    "resultados das ferramentas: {values}. Refaça a resposta usando só o que as ferramentas "
    "trouxeram; consulte de novo se precisar, ou diga que não tem a informação."
)
FALLBACK = (
    "Não consegui confirmar essas informações agora. Posso encaminhar sua dúvida para a nossa "
    f"equipe, que responde em {COMPLAINT_RESPONSE} pelo WhatsApp {STORE_INFO['whatsapp']} ou "
    f"pelo e-mail {STORE_INFO['email']}. Quer que eu encaminhe?"
)
# Rodadas de ferramenta por mensagem do cliente; acima disso o modelo está em laço.
MAX_TOOL_ROUNDS = 6

MONEY = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)")
INSTALLMENTS = re.compile(r"\b(\d{1,2})\s?x\b", re.IGNORECASE)
DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b")
NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?")


def _decimal(text: str) -> Decimal:
    return Decimal(text.replace(".", "").replace(",", "."))


def ungrounded(answer: str, sources: str, client_text: str = "") -> list[str]:
    """Valores da resposta que não aparecem nas fontes, na ordem em que foram escritos.

    Dinheiro compara pelo valor (R$ 500 = R$ 500,00); o cliente pode ter dito o valor sem R$.
    Data sem ano casa com a mesma data com ano.
    """
    money = {_decimal(m) for m in MONEY.findall(sources)}
    money |= {_decimal(n) for n in NUMBER.findall(client_text)}
    installments = set(INSTALLMENTS.findall(sources + " " + client_text))
    dates = {(int(d), int(m), y or None) for d, m, y in DATE.findall(sources + " " + client_text)}
    day_month = {(d, m) for d, m, _ in dates}

    missing = []
    for match in MONEY.finditer(answer):
        if _decimal(match[1]) not in money:
            missing.append(match)
    for match in INSTALLMENTS.finditer(answer):
        if match[1] not in installments:
            missing.append(match)
    for match in DATE.finditer(answer):
        d, m, y = int(match[1]), int(match[2]), match[3]
        if (d, m) not in day_month or (y and (d, m, y) not in dates and (d, m, None) not in dates):
            missing.append(match)
    return [match[0] for match in sorted(missing, key=lambda match: match.start())]


def _as_tool(func) -> StructuredTool:
    """Ferramenta do LangChain que devolve JSON legível (acentos e R$ preservados)."""

    @functools.wraps(func)
    def run(*args, **kwargs):
        result = func(*args, **kwargs)
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

    return StructuredTool.from_function(run)


def _note(kind: str, text: str) -> HumanMessage:
    return HumanMessage(text, additional_kwargs={NOTE: kind})


def is_note(message: AnyMessage) -> bool:
    return isinstance(message, HumanMessage) and NOTE in message.additional_kwargs


def _turn(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Mensagens depois da última mensagem do cliente (notas internas não contam)."""
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage) and not is_note(messages[i]):
            return messages[i + 1 :]
    return messages


def _dedupe(response: AIMessage) -> AIMessage:
    """Descarta chamadas idênticas repetidas na mesma resposta (modelos locais chegam a dezenas)."""
    seen, kept = set(), []
    for call in response.tool_calls:
        key = (call["name"], json.dumps(call["args"], sort_keys=True))
        if key not in seen:
            seen.add(key)
            kept.append(call)
    if len(kept) == len(response.tool_calls):
        return response
    ids = {call["id"] for call in kept}
    content = response.content
    if isinstance(content, list):  # Anthropic repete as chamadas como blocos tool_use
        content = [
            b
            for b in content
            if not (isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") not in ids)
        ]
    return response.model_copy(update={"tool_calls": kept, "content": content})


def build_agent(model: BaseChatModel, checkpointer=None):
    """Grafo compilado; a memória da conversa fica no checkpointer, por thread_id."""
    lc_tools = [_as_tool(f) for f in tools.TOOLS]
    llm = model.bind_tools(lc_tools)

    def agent(state: MessagesState):
        system = SystemMessage(system_prompt(reference_date()))
        return {"messages": [_dedupe(llm.invoke([system, *state["messages"]]))]}

    def route(state: MessagesState) -> Literal["tools", "check", "give_up"]:
        messages = state["messages"]
        if not messages[-1].tool_calls:
            return "check"
        rounds = sum(1 for m in _turn(messages) if isinstance(m, AIMessage) and m.tool_calls)
        return "give_up" if rounds > MAX_TOOL_ROUNDS else "tools"

    def give_up(state: MessagesState):
        last = state["messages"][-1]
        return {"messages": [RemoveMessage(id=last.id), AIMessage(FALLBACK)]}

    def check(state: MessagesState) -> Command[Literal["agent", "__end__"]]:
        messages = state["messages"]
        answer, turn = messages[-1], _turn(messages)
        notes = [m.additional_kwargs[NOTE] for m in turn if is_note(m)]
        if NUDGE not in notes and not any(isinstance(m, ToolMessage) for m in turn):
            return Command(goto="agent", update={"messages": [_note(NUDGE, NUDGE_TEXT)]})

        sources = " ".join(m.text for m in messages if isinstance(m, ToolMessage))
        sources += f" {reference_date():%d/%m/%Y}"
        client = " ".join(
            m.text for m in messages if isinstance(m, HumanMessage) and not is_note(m)
        )
        missing = ungrounded(answer.text, sources, client)
        if not missing:
            return Command(goto=END)
        if CORRECTION not in notes:
            text = CORRECTION_TEXT.format(values=", ".join(missing))
            return Command(goto="agent", update={"messages": [_note(CORRECTION, text)]})
        return Command(
            goto=END, update={"messages": [RemoveMessage(id=answer.id), AIMessage(FALLBACK)]}
        )

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(lc_tools))
    graph.add_node("check", check)
    graph.add_node("give_up", give_up)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route)
    graph.add_edge("tools", "agent")
    graph.add_edge("give_up", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def reply(agent, thread_id: str, text: str) -> str:
    """Envia a mensagem do cliente na conversa `thread_id` e devolve a resposta final."""
    config = {"configurable": {"thread_id": thread_id}}
    state = agent.invoke({"messages": [HumanMessage(text)]}, config)
    return state["messages"][-1].text


def trace(agent, thread_id: str) -> list[str]:
    """Ferramentas chamadas e notas internas da última mensagem do cliente, para as interfaces."""
    messages = agent.get_state({"configurable": {"thread_id": thread_id}}).values["messages"]
    steps = []
    for m in _turn(messages):
        if isinstance(m, AIMessage):
            for call in m.tool_calls:
                args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
                steps.append(f"ferramenta: {call['name']}({args})")
        elif is_note(m):
            steps.append(f"nota interna: {m.additional_kwargs[NOTE]}")
    return steps
