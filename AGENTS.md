# Instruções para assistentes de código

## Fontes da verdade

- `data/*.csv`: catálogo, promoções, pedidos e clientes (março/2026).
- `data/políticas_da_loja.pdf`: manual; versão usada pelo agente em `knowledge/policies.md`.
- `knowledge/rules.md`: matriz de regras; cada código marcado **T** tem teste que o cita.

## Regras de trabalho

- Contas (descontos, parcelas, frete, prazos) em Python, nunca pelo modelo.
- Mudou uma regra: atualizar `knowledge/rules.md` e o teste juntos.
- Regras de negócio sem dependência de LangChain; as ferramentas só as embrulham.
- Código, nomes e commits em inglês (Conventional Commits). Comentários e docstrings em pt-BR.
- Commits pequenos, um por mudança lógica. Sem force-push que achate o histórico; nada muda depois do
  prazo.
- Antes de concluir: `pytest` e `ruff check .` passando.
