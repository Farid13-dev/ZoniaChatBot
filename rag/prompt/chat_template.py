"""Prompts."""
#	Base para prompts multimensaje (ChatGPT-style).
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
import logging

from rag.llm.types import MessageRole, ChatMessage

if TYPE_CHECKING:
  from rag.llm.base import LLM

logger = logging.getLogger(__name__)

from typing import Any, Callable, Dict, List, Optional
from copy import deepcopy
import logging

from rag.llm.types import ChatMessage
from rag.prompt.types import PromptType
from rag.output_parser.base import BaseOutputParser
from rag.prompt.base_prompt import BasePromptTemplate
from rag.prompt.utils import get_template_vars, messages_to_prompt

from pydantic import Field

logger = logging.getLogger(__name__)


class ChatPromptTemplate(BasePromptTemplate):
  message_templates: List[ChatMessage] = Field(default_factory=list)
  prompt_type: str = PromptType.CUSTOM
  output_parser: Optional[BaseOutputParser] = None
  metadata: Dict[str, Any] = Field(default_factory=dict)
  template_var_mappings: Dict[str, Any] = Field(default_factory=dict)
  function_mappings: Dict[str, Callable] = Field(default_factory=dict)
  kwargs: Dict[str, Any] = Field(default_factory=dict)
  template_vars: List[str] = Field(default_factory=list)

  def __init__(self, **data: Any):
    super().__init__(**data)

    # Agrega el tipo de prompt al metadata
    self.metadata["prompt_type"] = self.prompt_type

    # Extrae variables de los mensajes
    template_vars = []
    for message_template in self.message_templates:
      template_vars.extend(get_template_vars(message_template.content or ""))
    self.template_vars = template_vars

  def partial_format(self, **kwargs: Any) -> "ChatPromptTemplate":
    prompt = deepcopy(self)
    prompt.kwargs.update(kwargs)
    return prompt

  def format(self, llm=None, **kwargs: Any) -> str:
    del llm  # unused
    messages = self.format_messages(**kwargs)
    return messages_to_prompt(messages)

  def format_messages(self, llm=None, **kwargs: Any) -> List[ChatMessage]:
    del llm  # unused
    all_kwargs = {**self.kwargs, **kwargs}
    mapped_all_kwargs = self._map_all_vars(all_kwargs)

    messages: List[ChatMessage] = []
    for message_template in self.message_templates:
      template_vars = get_template_vars(message_template.content or "")
      relevant_kwargs = {
        k: v for k, v in mapped_all_kwargs.items() if k in template_vars
      }
      content_template = message_template.content or ""
      content = content_template.format(**relevant_kwargs)
      message: ChatMessage = message_template.copy()
      message.content = content
      messages.append(message)

    if self.output_parser is not None:
      messages = self.output_parser.format_messages(messages)

    return messages

  def get_template(self, llm=None) -> str:
    return messages_to_prompt(self.message_templates)


"""Prompts for ChatGPT."""
# text qa prompt
# Prompt del sistema para preguntas y respuestas
# TEXT_QA_SYSTEM_PROMPT = ChatMessage(
#     content=(
#         "Eres un sistema experto en preguntas y respuestas, reconocido y confiable en todo el mundo.\n"
#         "Siempre responde la consulta usando exclusivamente la información del contexto proporcionado, "
#         "y no conocimiento previo.\n"
#         "Algunas reglas que debes seguir:\n"
#         "1. Nunca hagas referencia directa al contexto en tu respuesta.\n"
#         "2. Evita frases como 'Según el contexto...', 'el texto...', La información del contexto...', o cualquier otra de ese estilo."
#     ),
#     role=MessageRole.SYSTEM,
# )

TEXT_QA_SYSTEM_PROMPT = ChatMessage(
  content=(
    "Eres un asistente experta en preguntas y respuestas, reconocida y confiable en todo el mundo.\n"
    "Siempre responde la consulta usando exclusivamente la información del contexto proporcionado, sin conocimiento previo.\n"
    "Si no puedes responder con precisión basada en el contexto, di claramente: "
    "'No tengo suficiente información para responder, por favor reformula la pregunta.'\n"
    "Reglas importantes:\n"
    "1. Nunca hagas referencia directa al contexto en tu respuesta.\n"
    "2. Evita frases como 'Según el contexto...' o 'La información dice...'.\n"
    "4. No uses asteriscos, guiones, Markdown, ni símbolos decorativos.\n"
    "3. Puedes usar listas numeradas si ayudan a organizar mejor la respuesta.\n"
  ),
  role=MessageRole.SYSTEM,
)

# Prompt para preguntas y respuestas con contexto
TEXT_QA_PROMPT_TMPL_MSGS = [
  TEXT_QA_SYSTEM_PROMPT,
  ChatMessage(
    content=(
      "A continuación se presenta información de contexto.\n"
      "---------------------\n"
      "{context_str}\n"
      "---------------------\n"
      "Usando únicamente esta información de contexto y sin conocimiento previo, "
      "responde la siguiente pregunta.\n"
      "Pregunta: {query_str}\n"
      "Respuesta: "
    ),
    role=MessageRole.USER,
  ),
]

CHAT_TEXT_QA_PROMPT = ChatPromptTemplate(message_templates=TEXT_QA_PROMPT_TMPL_MSGS)

# Prompt para resumen de múltiples fuentes (modo árbol)
TREE_SUMMARIZE_PROMPT_TMPL_MSGS = [
  TEXT_QA_SYSTEM_PROMPT,
  ChatMessage(
    content=(
      "A continuación se presenta información de múltiples fuentes.\n"
      "---------------------\n"
      "{context_str}\n"
      "---------------------\n"
      "Usando únicamente esta información y sin conocimiento previo, "
      "responde la siguiente pregunta.\n"
      "Pregunta: {query_str}\n"
      "Respuesta: "
    ),
    role=MessageRole.USER,
  ),
]

CHAT_TREE_SUMMARIZE_PROMPT = ChatPromptTemplate(
  message_templates=TREE_SUMMARIZE_PROMPT_TMPL_MSGS
)
