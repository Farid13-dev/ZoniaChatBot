from huggingface_hub import InferenceClient
from typing import Sequence, Optional, Generator
from rag.llm.base import BaseLLM
from rag.llm.types import (
    ChatMessage, ChatResponse, CompletionResponse, LLMMetadata,
    MessageRole, CompletionResponseGen, ChatResponseGen
)
from pydantic import Field, BaseModel


class HuggingFaceLLM(BaseLLM, BaseModel):
    model_name: str = Field(...)
    api_key: str = Field(...)
    max_tokens: int = 512
    context_window: int = 8192
    temperature: float = 0.7
    top_p: Optional[float] = None

    @property
    def client(self) -> InferenceClient:
        return InferenceClient(api_key=self.api_key)

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=self.context_window,
            num_output=512,
            is_chat_model=True,
            is_function_calling_model=False,
            model_name=self.model_name,
        )

    def chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": msg.role.value, "content": msg.content} for msg in messages],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            **kwargs
        )
        message = response["choices"][0]["message"]
        return ChatResponse(
            message=ChatMessage(role=MessageRole.ASSISTANT, content=message["content"]),
            raw=response
        )

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            **kwargs
        )
        return CompletionResponse(
            text=response["choices"][0]["message"]["content"],
            raw=response
        )

    def predict(self, prompt, system_prompt: Optional[str] = None, **prompt_args):
        system_prompt = system_prompt or "Responde con base en el contexto."

        if hasattr(prompt, "format_messages"):
            messages = prompt.format_messages(**prompt_args)
            messages.insert(0, {"role": "system", "content": system_prompt})
            message_payload = [
                {"role": msg["role"] if isinstance(msg, dict) else msg.role.value,
                 "content": msg["content"] if isinstance(msg, dict) else msg.content}
                for msg in messages
            ]
        else:
            template_str = prompt.template if hasattr(prompt, "template") else str(prompt)
            expected_args = {
                k for k in ["context", "context_str", "query", "query_str", "tools_str"]
                if f"{{{k}}}" in template_str
            }
            format_args = {k: v for k, v in prompt_args.items() if k in expected_args}
            try:
                formatted_prompt = template_str.format(**format_args)
            except KeyError as e:
                raise ValueError(f"Falta el argumento requerido en prompt_args: {e}")
            message_payload = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": formatted_prompt}
            ]

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=message_payload,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )
        return response.choices[0].message.content.strip()

    async def apredict(self, prompt, **prompt_args):
        return self.predict(prompt, **prompt_args)

    def stream_chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponseGen:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": msg.role.value, "content": msg.content} for msg in messages],
            stream=True,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            **kwargs
        )

        def generator() -> Generator[ChatResponse, None, None]:
            content = ""
            for chunk in response:
                delta = getattr(chunk.choices[0].delta, "content", "")
                if delta:
                    content += delta
                    yield ChatResponse(
                        message=ChatMessage(role=MessageRole.ASSISTANT, content=content),
                        raw=chunk
                    )

        return generator()

    def stream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            **kwargs
        )

        def generator() -> Generator[CompletionResponse, None, None]:
            content = ""
            for chunk in response:
                delta = getattr(chunk.choices[0].delta, "content", "")
                if delta:
                    content += delta
                    yield CompletionResponse(text=content, raw=chunk)

        return generator()

    def stream(self, prompt, llm=None, **prompt_args) -> Generator[str, None, None]:
      llm = llm or self

      # Detectar si es prompt tipo chat
      if hasattr(prompt, "format_messages"):
        # ⚠️ Asegúrate de pasar el llm para que el SelectorPromptTemplate funcione correctamente
        messages = prompt.format_messages(llm=llm, **prompt_args)
      else:
        # Prompt plano tipo string con system_prompt opcional
        system_prompt = prompt_args.pop("system_prompt", "Responde con base en el contexto.")
        template_str = prompt.template if hasattr(prompt, "template") else str(prompt)
        expected_args = {
          k for k in ["context", "context_str", "query", "query_str", "tools_str"]
          if f"{{{k}}}" in template_str
        }
        format_args = {k: v for k, v in prompt_args.items() if k in expected_args}
        try:
          formatted_prompt = template_str.format(**format_args)
        except KeyError as e:
          raise ValueError(f"Falta el argumento requerido en prompt_args: {e}")
        messages = [
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": formatted_prompt},
        ]

      # Convertir todos a dict (si es necesario)
      message_payload = [
        {"role": msg["role"] if isinstance(msg, dict) else msg.role.value,
         "content": msg["content"] if isinstance(msg, dict) else msg.content}
        for msg in messages
      ]

      response = self.client.chat.completions.create(
        model=self.model_name,
        messages=message_payload,
        stream=True,
        max_tokens=self.max_tokens,
        temperature=self.temperature,
        top_p=self.top_p,
      )

      def generator() -> Generator[str, None, None]:
        for chunk in response:
          delta = getattr(chunk.choices[0].delta, "content", "")
          if delta:
            yield delta

      return generator()

    async def achat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        return self.chat(messages, **kwargs)

    async def acomplete(self, prompt: str, **kwargs) -> CompletionResponse:
        return self.complete(prompt, **kwargs)

    async def astream_chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponseGen:
        return self.stream_chat(messages, **kwargs)

    async def astream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        return self.stream_complete(prompt, **kwargs)

    async def astream(self, prompt, **prompt_args):
        return self.stream(prompt, **prompt_args)
