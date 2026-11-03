"""Conversa com o Doremi no terminal: python -m emporio [--debug]."""

from __future__ import annotations

import argparse
import uuid

from emporio import agent as ag
from emporio import llm
from emporio.config import load_env

HELP = "Digite sua mensagem. /nova começa outra conversa; /sair (ou Ctrl+C) encerra."


def main() -> None:
    parser = argparse.ArgumentParser(description="Atendimento da Empório da Música no terminal.")
    parser.add_argument(
        "--debug", action="store_true", help="mostra as ferramentas chamadas e as notas internas"
    )
    args = parser.parse_args()

    load_env()
    model = llm.chat_model()
    graph = ag.build_agent(model)
    print(f"Doremi, da Empório da Música ({llm.label(model)})")
    print(HELP)

    thread = uuid.uuid4().hex
    while True:
        try:
            text = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text == "/sair":
            return
        if text == "/nova":
            thread = uuid.uuid4().hex
            print("(nova conversa)")
            continue
        if not text:
            continue
        try:
            answer = ag.reply(graph, thread, text)
        except Exception as e:  # provedor fora do ar, chave inválida: a conversa continua
            print(f"\n(erro ao falar com o modelo: {e})")
            continue
        if args.debug:
            for step in ag.trace(graph, thread):
                print(f"  [{step}]")
        print(f"\nDoremi: {answer}")


if __name__ == "__main__":
    main()
