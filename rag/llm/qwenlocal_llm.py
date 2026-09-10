from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from rag.llm.base import BaseLLM
from rag.llm.types import (
  ChatMessage, ChatResponse, CompletionResponse, LLMMetadata,
  MessageRole, CompletionResponseGen, ChatResponseGen
)
import torch
from pydantic import BaseModel, Field, PrivateAttr
from typing import Optional, List, Generator
import threading
import asyncio
import time


class QwenLocalLLM(BaseLLM, BaseModel):
  model_name: str
  tokenizer_name: Optional[str] = None
  max_new_tokens: int = 256
  context_window: int = 8192
  temperature: float = 0.7
  top_k: int = 50
  top_p: float = 0.9
  num_beams: int = 1
  do_sample: bool = True
  use_cache: bool = True
  device_map: str = "auto"
  torch_dtype: str = "float16"
  device: str = Field(default="cuda")

  _model = PrivateAttr()
  _tokenizer = PrivateAttr()

  def __init__(self, **data):
    if "max_tokens" in data and "max_new_tokens" not in data:
      data["max_new_tokens"] = data.pop("max_tokens")
    super().__init__(**data)
    self._tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name or self.model_name)
    self._model = AutoModelForCausalLM.from_pretrained(
      self.model_name,
      device_map=self.device_map,
      torch_dtype=getattr(torch, self.torch_dtype),
    ).to(self.device)

  @property
  def max_tokens(self) -> int:
    return self.max_new_tokens

  @property
  def metadata(self) -> LLMMetadata:
    return LLMMetadata(
      context_window=self.context_window,
      num_output=self.max_new_tokens,
      is_chat_model=True,
      is_function_calling_model=False,
      model_name=self.model_name
    )

  def chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponse:
    prompt = self._tokenizer.apply_chat_template(
      [{"role": m.role.value, "content": m.content} for m in messages],
      tokenize=False,
      add_generation_prompt=True
    )

    inputs = self._tokenizer(prompt, return_tensors="pt").to(self.device)
    outputs = self._model.generate(
      **inputs,
      max_new_tokens=self.max_new_tokens,
      temperature=self.temperature,
      top_k=self.top_k,
      top_p=self.top_p,
      do_sample=self.do_sample,
      num_beams=self.num_beams,
      use_cache=self.use_cache,
    )
    response_ids = outputs[0][inputs.input_ids.shape[-1]:]
    decoded = self._tokenizer.decode(response_ids, skip_special_tokens=True).strip()

    return ChatResponse(
      message=ChatMessage(role=MessageRole.ASSISTANT, content=decoded),
      raw={"output": decoded}
    )

  def predict(self, prompt, system_prompt: Optional[str] = None, **prompt_args) -> str:
    system_prompt = system_prompt or "Responde con base en el contexto."

    if hasattr(prompt, "format_messages"):
      messages = prompt.format_messages(**prompt_args)
      messages.insert(0, ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
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
      messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=MessageRole.USER, content=formatted_prompt)
      ]

    return self.chat(messages).message.content

  async def achat(self, messages: List[ChatMessage], **kwargs):
    return self.chat(messages, **kwargs)

  async def apredict(self, prompt: str, **kwargs):
    return self.predict(prompt, **kwargs)

  def complete(self, prompt: str, **kwargs) -> CompletionResponse:
    messages = [ChatMessage(role=MessageRole.USER, content=prompt)]
    result = self.chat(messages)
    return CompletionResponse(text=result.message.content, raw=result.raw)

  # --- STREAMING SYNC ---

  def stream_chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponseGen:
    prompt = self._tokenizer.apply_chat_template(
      [{"role": m.role.value, "content": m.content} for m in messages],
      tokenize=False,
      add_generation_prompt=True
    )
    inputs = self._tokenizer(prompt, return_tensors="pt").to(self.device)
    streamer = TextIteratorStreamer(self._tokenizer, skip_prompt=True, skip_special_tokens=True)

    thread = threading.Thread(
      target=self._model.generate,
      kwargs=dict(
        **inputs,
        streamer=streamer,
        max_new_tokens=self.max_new_tokens,
        temperature=self.temperature,
        top_k=self.top_k,
        top_p=self.top_p,
        do_sample=self.do_sample,
        num_beams=self.num_beams,
        use_cache=self.use_cache,
      ),
      daemon=True
    )
    thread.start()

    def generator() -> Generator[ChatResponse, None, None]:
      content = ""
      for token in streamer:
        if not token.strip():
          continue
        content += token
        yield ChatResponse(
          message=ChatMessage(role=MessageRole.ASSISTANT, content=content),
          raw={"token": token}
        )

    return generator()

  def stream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
    messages = [ChatMessage(role=MessageRole.USER, content=prompt)]
    return self._stream_raw_completion(messages)

  def stream(self, prompt, llm=None, **prompt_args) -> Generator[str, None, None]:
    llm = llm or self

    # Construcción del mensaje
    if hasattr(prompt, "format_messages"):
        # Usa el llm para que SelectorPromptTemplate funcione correctamente
        messages = prompt.format_messages(llm=llm, **prompt_args)
    else:
        # Prompt clásico tipo string
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
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=formatted_prompt),
        ]

    # Aplicar la plantilla chat
    prompt_str = self._tokenizer.apply_chat_template(
        [{"role": m.role.value, "content": m.content} for m in messages],
        tokenize=False,
        add_generation_prompt=True
    )

    # Debug del prompt final
    print("\n🧾 PROMPT FINAL ENVIADO AL MODELO:\n")
    print(prompt_str)

    inputs = self._tokenizer(prompt_str, return_tensors="pt").to(self.device)
    streamer = TextIteratorStreamer(self._tokenizer, skip_prompt=True, skip_special_tokens=True)

    # Generación en hilo separado
    thread = threading.Thread(
        target=self._model.generate,
        kwargs=dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
            do_sample=self.do_sample,
            num_beams=self.num_beams,
            use_cache=self.use_cache,
        ),
        daemon=True
    )
    thread.start()

    def generator() -> Generator[str, None, None]:
        for token in streamer:
            if token.strip():
                yield token

    return generator()

  # --- STREAMING ASYNC ---

  async def astream_chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponseGen:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: self.stream_chat(messages, **kwargs))

  async def astream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: self.stream_complete(prompt, **kwargs))

  async def astream(self, prompt, **prompt_args) -> Generator[str, None, None]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: self.stream(prompt, **prompt_args))

  async def acomplete(self, prompt: str, **kwargs):
    return self.complete(prompt, **kwargs)
