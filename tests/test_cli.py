from test_agent import C40, fake, tool_call

from emporio import __main__ as cli
from emporio import llm


def chat(monkeypatch, capsys, model, *lines, argv=()):
    monkeypatch.setattr(llm, "chat_model", lambda: model)
    monkeypatch.setattr("sys.argv", ["emporio", *argv])
    inputs = iter(lines)

    def typed(_prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", typed)
    cli.main()
    return capsys.readouterr().out


def test_conversation_until_exit(monkeypatch, capsys):
    model = fake(tool_call("get_product", product_id=81), C40)
    out = chat(monkeypatch, capsys, model, "Quanto custa o violão Yamaha C40?", "/sair")
    assert f"Doremi: {C40}" in out
    assert "ferramenta:" not in out


def test_debug_shows_tools_and_notes(monkeypatch, capsys):
    model = fake("Oi!", "Oi! Sou o Doremi.")
    out = chat(monkeypatch, capsys, model, "Oi", argv=["--debug"])  # sem /sair: termina no EOF
    assert "[nota interna: nudge]" in out and "Doremi: Oi! Sou o Doremi." in out


def test_new_conversation_forgets_the_previous(monkeypatch, capsys):
    model = fake(tool_call("store_status"), "Abrimos às 9h.", "Oi!", "Oi, tudo bem?")
    chat(monkeypatch, capsys, model, "Que horas abre?", "/nova", "Oi")
    assert "Que horas abre?" not in [m.text for m in model.calls[-1]]


def test_model_error_keeps_the_conversation(monkeypatch, capsys):
    model = fake()  # sem respostas roteirizadas: a chamada falha
    out = chat(monkeypatch, capsys, model, "Oi", "/sair")
    assert "(erro ao falar com o modelo" in out
