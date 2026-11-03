"""Chat model escolhido pelo .env: LLM_PROVIDER e, opcionalmente, LLM_MODEL."""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel

DEFAULT_MODELS = {
    "ollama": "qwen3.5:9b",
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-5.4-mini",
    "deepseek": "deepseek-flash",
}


def chat_model(provider: str | None = None, model: str | None = None) -> BaseChatModel:
    provider = (provider or os.environ.get("LLM_PROVIDER") or "ollama").strip().lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(
            f"LLM_PROVIDER desconhecido: {provider!r}; use {', '.join(DEFAULT_MODELS)}"
        )
    name = model or os.environ.get("LLM_MODEL") or DEFAULT_MODELS[provider]
    # Importações locais: cada provedor carrega só o próprio pacote.
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=name,
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
            num_ctx=16384,  # o padrão do Ollama trunca o prompt com as ferramentas
            num_predict=2048,  # sem teto, um laço de chamadas repetidas enche o contexto
            reasoning=False,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=name)  # os GPT-5 de raciocínio recusam temperature
    if provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(model=name, temperature=0)
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=name, max_tokens=16000)  # os Claude 5.5 recusam temperature


def label(model: BaseChatModel) -> str:
    """Classe e modelo para as interfaces; OpenAI e DeepSeek guardam o nome em model_name."""
    name = getattr(model, "model_name", None) or getattr(model, "model", "")
    return f"{type(model).__name__}: {name}"
