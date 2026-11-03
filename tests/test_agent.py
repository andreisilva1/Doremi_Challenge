import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from emporio import agent as ag
from emporio import llm


class FakeChat(GenericFakeChatModel):
    """Devolve as respostas roteirizadas e anota as mensagens de cada chamada."""

    calls: list = []

    def bind_tools(self, tools, **kwargs):
        def call(messages):
            self.calls.append(list(messages))
            return self.invoke(messages)

        return RunnableLambda(call)


def fake(*answers) -> FakeChat:
    return FakeChat(messages=iter(answers), calls=[])


def tool_call(name, **args) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{name}"}])


def run(model, *texts, thread="t1"):
    graph = ag.build_agent(model)
    answers = [ag.reply(graph, thread, t) for t in texts]
    return graph, answers


def state(graph, thread="t1"):
    return graph.get_state({"configurable": {"thread_id": thread}}).values["messages"]


C40 = "O Yamaha C40 sai por R$ 599,90, ou até 6x de R$ 99,98 sem juros no cartão."


def test_grounded_answer_after_lookup_passes():
    model = fake(tool_call("get_product", product_id=81), C40)
    graph, [answer] = run(model, "Quanto custa o violão Yamaha C40?")
    assert answer == C40
    assert len(model.calls) == 2


def test_system_prompt_and_tool_result_reach_the_model():
    model = fake(tool_call("get_product", product_id=81), C40)
    run(model, "Quanto custa o violão Yamaha C40?")
    messages = model.calls[1]
    assert isinstance(messages[0], SystemMessage) and "Doremi" in messages[0].text
    result = json.loads(messages[-1].text)
    assert isinstance(messages[-1], ToolMessage)
    assert result["cartao_credito"] == "até 6x de R$ 99,98 sem juros"


def test_answer_without_lookup_gets_one_nudge():
    model = fake(
        "Sim, vendemos saxofone!",
        tool_call("search_products", query="saxofone"),
        "Não trabalhamos com saxofone no momento.",
    )
    graph, [answer] = run(model, "Vocês vendem saxofone?")
    assert answer == "Não trabalhamos com saxofone no momento."
    assert len(model.calls) == 3
    notes = [m for m in state(graph) if ag.is_note(m)]
    assert [m.additional_kwargs[ag.NOTE] for m in notes] == [ag.NUDGE]


def test_nudge_happens_once():
    model = fake("Oi! Sou o Doremi.", "Oi! Sou o Doremi, como posso ajudar?")
    _, [answer] = run(model, "Oi")
    assert answer == "Oi! Sou o Doremi, como posso ajudar?"
    assert len(model.calls) == 2


def test_invented_numbers_trigger_a_correction():
    model = fake(
        tool_call("get_product", product_id=81), "Sai por R$ 599,90 ou 10x de R$ 59,99.", C40
    )
    graph, [answer] = run(model, "Quanto custa o violão Yamaha C40?")
    assert answer == C40
    [note] = [m for m in state(graph) if ag.is_note(m)]
    assert "10x, R$ 59,99" in note.text


def test_second_failure_falls_back_to_the_team():
    bad = "Sai por R$ 499,90."
    model = fake(tool_call("get_product", product_id=81), bad, "Sai por R$ 459,90.")
    graph, [answer] = run(model, "Quanto custa o violão Yamaha C40?")
    assert answer == ag.FALLBACK
    assert "Sai por R$ 459,90." not in [m.text for m in state(graph)]


def test_repeated_identical_calls_run_once():
    calls = [{"name": "store_status", "args": {}, "id": f"call_{i}"} for i in range(3)]
    calls.append({"name": "get_policy", "args": {"topic": "troca"}, "id": "call_policy"})
    model = fake(AIMessage("", tool_calls=calls), "Estamos abertos!")
    graph, [answer] = run(model, "A loja tá aberta?")
    assert answer == "Estamos abertos!"
    results = [m.tool_call_id for m in state(graph) if isinstance(m, ToolMessage)]
    assert results == ["call_0", "call_policy"]


def test_duplicate_tool_use_blocks_are_dropped_from_anthropic_content():
    blocks = [
        {"type": "text", "text": "Vou ver."},
        {"type": "tool_use", "id": "a", "name": "store_status", "input": {}},
        {"type": "tool_use", "id": "b", "name": "store_status", "input": {}},
    ]
    calls = [{"name": "store_status", "args": {}, "id": i} for i in "ab"]
    kept = ag._dedupe(AIMessage(blocks, tool_calls=calls))
    assert [c["id"] for c in kept.tool_calls] == ["a"]
    assert [b.get("id") for b in kept.content] == [None, "a"]


def test_tool_loop_ends_in_the_fallback():
    loop = [tool_call("store_status") for _ in range(ag.MAX_TOOL_ROUNDS + 1)]
    model = fake(*loop, "nunca chega aqui")
    graph, [answer] = run(model, "Na Black Friday abre até mais tarde?")
    assert answer == ag.FALLBACK
    assert len(model.calls) == ag.MAX_TOOL_ROUNDS + 1
    assert not state(graph)[-1].tool_calls


def test_conversation_memory_is_per_thread():
    model = fake(
        tool_call("get_product", product_id=81),
        C40,
        tool_call("store_status"),
        "Pode passar quando quiser!",
    )
    graph = ag.build_agent(model)
    ag.reply(graph, "a", "Quanto custa o violão Yamaha C40?")
    ag.reply(graph, "a", "E a loja abre que horas?")
    second_turn = model.calls[2]
    assert "Quanto custa o violão Yamaha C40?" in [m.text for m in second_turn]
    assert graph.get_state({"configurable": {"thread_id": "b"}}).values == {}


def test_numbers_from_earlier_turns_and_from_the_client_are_grounded():
    """PED-05: a data de referência também vale como fonte."""
    sources = '{"preco": "R$ 599,90", "cartao_credito": "até 6x de R$ 99,98"} 23/03/2026'
    answer = "Dentro dos seus R$ 800: o C40 por R$ 599,90 em 6x de R$ 99,98, hoje 23/03."
    assert ag.ungrounded(answer, sources, "tem violão até 800 reais?") == []


@pytest.mark.parametrize(
    ("answer", "missing"),
    [
        ("Fica R$ 1.234,56.", ["R$ 1.234,56"]),
        ("Parcela em 12x.", ["12x"]),
        ("Entregue em 17/02/2026.", ["17/02/2026"]),
        ("Prazo até 05/03/2025.", ["05/03/2025"]),
        ("R$ 500,00 de frete grátis acima de R$ 500.", []),
    ],
)
def test_ungrounded_values(answer, missing):
    assert ag.ungrounded(answer, "acima de R$ 500 até 05/03/2026") == missing


def test_provider_defaults(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    chosen = llm.chat_model()
    assert (type(chosen).__name__, chosen.model) == ("ChatOllama", "qwen3.5:9b")
    assert chosen.num_predict == 2048


def test_anthropic_builds_without_network(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm.chat_model("anthropic").model == "claude-sonnet-5-5"
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-5-5")
    assert llm.chat_model("anthropic").model == "claude-haiku-5-5"


def test_unknown_provider():
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        llm.chat_model("openai")
