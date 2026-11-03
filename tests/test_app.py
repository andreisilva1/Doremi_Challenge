from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from test_agent import C40, fake, tool_call

from emporio import llm

APP = str(Path(__file__).resolve().parent.parent / "app.py")
WELCOME = (
    "Oi! Eu sou o Doremi, assistente virtual da Empório da Música. Posso ajudar com "
    "instrumentos, preços, frete, pedidos e trocas."
)


@pytest.fixture
def app(monkeypatch):
    def start(*answers):
        model = fake(*answers)
        monkeypatch.setattr(llm, "chat_model", lambda: model)
        st.cache_resource.clear()
        return AppTest.from_file(APP, default_timeout=30).run()

    yield start
    st.cache_resource.clear()


def test_answer_keeps_reais_out_of_latex(app):
    at = app(tool_call("get_product", product_id=81), C40)
    at.chat_input[0].set_value("Quanto custa o violão Yamaha C40?").run()
    assert not at.exception
    assert at.chat_message[1].markdown[0].value == C40.replace("$", r"\$")


def test_example_button_and_steps(app):
    at = app(tool_call("store_status"), "Fica na Rua 14 de Maio, 3200.")
    at.toggle[0].set_value(True)
    next(b for b in at.button if b.label == "Qual o endereço da loja?").click().run()
    assert at.chat_message[0].markdown[0].value == "Qual o endereço da loja?"
    assert "ferramenta: store_status()" in at.chat_message[1].code[0].value


def test_new_conversation_clears_the_history(app):
    at = app("Oi!", "Oi! Sou o Doremi.")
    assert at.chat_message[0].markdown[0].value == WELCOME
    at.chat_input[0].set_value("Oi").run()
    assert [m.markdown[0].value for m in at.chat_message] == ["Oi", "Oi! Sou o Doremi."]
    next(b for b in at.button if b.label == "Nova conversa").click().run()
    assert [m.markdown[0].value for m in at.chat_message] == [WELCOME]
