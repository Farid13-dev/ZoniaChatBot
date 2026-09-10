from rag.llm.huggingface_llm import HuggingFaceLLM
from rag.llm.qwenlocal_llm import QwenLocalLLM
from rag.llm.openai_llm import OpenAILLM
from rag.llm.mock_llm import MockLLM
from rag.config.schema import LlmConfig
from rag.llm.base import BaseLLM
from typing import Optional, Union


def resolve_llm(llm: Optional[Union[str, BaseLLM, LlmConfig]] = None) -> BaseLLM:
    if llm is None:
        print("LLM is explicitly disabled. Using MockLLM.")
        return MockLLM()

    if isinstance(llm, BaseLLM):
        return llm

    if isinstance(llm, str):
        if llm.lower() == "openai":
            return OpenAILLM()
        raise ValueError(f"Unknown LLM string type: {llm}")

    if isinstance(llm, LlmConfig):
        model_name = llm.model_name.lower()
        provider = getattr(llm, "provider", "openai").lower()

        # Groq expone una API compatible con OpenAI: mismo cliente, otra URL.
        # Se acepta como proveedor propio para que aparezca en la UI de admin.
        if provider in ("openai", "groq"):
            api_base = getattr(llm, "api_base", None)
            if provider == "groq" and not api_base:
                api_base = "https://api.groq.com/openai/v1"
            return OpenAILLM(
                model_name=llm.model_name,
                api_key=llm.api_key,
                api_base=api_base,
            )

        elif provider == "huggingface":
            return HuggingFaceLLM(model_name=llm.model_name, api_key=llm.api_key)

        elif provider == "local":
            if "qwen" in model_name:
                return QwenLocalLLM(model_name=llm.model_name)
            # Podrías extenderlo a otros modelos locales tipo LLaMA, Mistral, etc.
            raise ValueError(f"Modelo local no reconocido: {llm.model_name}")

    raise ValueError(f"Unknown LLM type: {llm}")
