"""Chat do Doremi no navegador: streamlit run app.py."""

from __future__ import annotations

import uuid

import streamlit as st

from emporio import agent as ag
from emporio import llm
from emporio.config import load_env

# Sugestões do enunciado do desafio
EXAMPLES = (
    "Quais violões vocês têm até R$ 1000?",
    "Qual o endereço da loja?",
    "Quanto custa o Takamine GD20?",
    "Comprei um violão pelo site e me arrependi. Posso devolver?",
)
WELCOME = (
    "Oi! Eu sou o Doremi, assistente virtual da Empório da Música. Posso ajudar com "
    "instrumentos, preços, frete, pedidos e trocas."
)
AVATARS = {"user": ":material/person:", "assistant": "🎸"}


@st.cache_resource
def _agent():
    """Um grafo por processo; cada aba tem a sua conversa (thread_id)."""
    load_env()
    model = llm.chat_model()
    return ag.build_agent(model), llm.label(model)


def _markdown(text: str) -> None:
    st.markdown(text.replace("$", r"\$"))  # sem isso, "R$ 10 ... R$ 20" vira fórmula LaTeX


def _steps(steps: list[str]) -> None:
    if steps:
        with st.expander(f"Consultas ({len(steps)})", icon=":material/manage_search:"):
            st.code("\n".join(steps), language=None)


st.set_page_config(page_title="Doremi · Empório da Música", page_icon="🎸")
graph, model_name = _agent()
session = st.session_state
if "thread" not in session:
    session.thread, session.history = uuid.uuid4().hex, []

with st.sidebar:
    st.header("Empório da Música")
    st.caption("Instrumentos musicais em Campo Grande (MS)")
    if st.button("Nova conversa", icon=":material/add_comment:", width="stretch"):
        session.thread, session.history = uuid.uuid4().hex, []
    show_steps = st.toggle("Mostrar consultas", help="Ferramentas chamadas e notas internas")
    st.divider()
    st.caption(f"Modelo: {model_name}")

st.title("Doremi")
st.caption("Assistente virtual da Empório da Música")

# Tela inicial: saudação e sugestões, apagadas quando a conversa começa.
intro, clicked = st.empty(), []
if not session.history:
    with intro.container():
        with st.chat_message("assistant", avatar=AVATARS["assistant"]):
            st.markdown(WELCOME)
        columns = st.columns(2)
        clicked = [
            q
            for i, q in enumerate(EXAMPLES)
            if columns[i % 2].button(q.replace("$", r"\$"), key=q, width="stretch")
        ]

for role, text, steps in session.history:
    with st.chat_message(role, avatar=AVATARS[role]):
        _markdown(text)
        if show_steps:
            _steps(steps)

text = st.chat_input("Escreva sua mensagem") or (clicked[0] if clicked else None)
if text:
    intro.empty()
    with st.chat_message("user", avatar=AVATARS["user"]):
        _markdown(text)
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        try:
            with st.spinner("Doremi está digitando..."):
                answer = ag.reply(graph, session.thread, text)
        except Exception as e:  # provedor fora do ar, chave inválida: a conversa continua
            st.error(f"Erro ao falar com o modelo: {e}")
            st.stop()
        steps = ag.trace(graph, session.thread)
        _markdown(answer)
        if show_steps:
            _steps(steps)
    session.history += [("user", text, []), ("assistant", answer, steps)]
