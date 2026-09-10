import json
from typing import Sequence

from rag.prompt.prompt_template import PromptTemplate
from rag.prompt.types import PromptType
from rag.tools.types import ToolMetadata
from .base import SubQuestion

# deprecated, kept for backward compatibility
SubQuestionPrompt = PromptTemplate


def build_tools_text(tools: Sequence[ToolMetadata]) -> str:
    tools_dict = {}
    for tool in tools:
        tools_dict[tool.name] = tool.description
    return json.dumps(tools_dict, indent=4)


PREFIX = """\
Given a user question, and a list of tools, output a list of relevant sub-questions \
in json markdown that when composed can help answer the full user question:

"""

example_query_str = (
    "Compare and contrast the revenue growth and EBITDA of Uber and Lyft for year 2021"
)
example_tools = [
    ToolMetadata(
        name="uber_10k",
        description="Provides information about Uber financials for year 2021",
    ),
    ToolMetadata(
        name="lyft_10k",
        description="Provides information about Lyft financials for year 2021",
    ),
]
example_tools_str = build_tools_text(example_tools)
example_output = [
    SubQuestion(
        sub_question="What is the revenue growth of Uber", tool_name="uber_10k"
    ),
    SubQuestion(sub_question="What is the EBITDA of Uber", tool_name="uber_10k"),
    SubQuestion(
        sub_question="What is the revenue growth of Lyft", tool_name="lyft_10k"
    ),
    SubQuestion(sub_question="What is the EBITDA of Lyft", tool_name="lyft_10k"),
]
example_output_str = json.dumps({"items": [x.dict() for x in example_output]}, indent=4)

EXAMPLES = f"""\
# Example 1
<Tools>
```json
{example_tools_str}
```

<User Question>
{example_query_str}


<Output>
```json
{example_output_str}
```

""".replace(
    "{", "{{"
).replace(
    "}", "}}"
)

SUFFIX = """\
# Example 2
<Tools>
```json
{tools_str}
```

<User Question>
{query_str}

<Output>
"""

DEFAULT_SUB_QUESTION_PROMPT_TMPL = PREFIX + EXAMPLES + SUFFIX

# DEFAULT_CONTEXTUAL_SUBQUESTION_PROMPT_TMPL = """\
# "A continuación se muestra información de contexto.\n"
#     "---------------------\n"
#     "{context_str}\n"
#     "---------------------\n"
# "Pregunta planteada por el usuario:\n"
#     "---------------------\n"
#     "{query_str}\n"
#     "---------------------\n"
#
# "Tu tarea es descomponer esta pregunta en **exactamente {max_subquestions} sub-preguntas** claras, específicas y **directamente relacionadas con el contexto**."
#
# "Algunas reglas que debes seguir:\n"
#         "1. Usa únicamente esta información de contexto y sin conocimiento previo"
#         "2. Usa palabras claves del contexto para refomular la sub-pregunta."
#         "3. Nunca hagas referencia directa al contexto en la sub-preguntas."
#         "4. Evita frases como "Según el contexto...", "el texto menciona...", "la información indica..." u otras similares."
#
# Formato de salida: JSON con esta estructura exacta:
#
# ```json
# {{
#   "items": [
#     {{ "sub_question": "..." }},
#     {{ "sub_question": "..." }},
#     {{ "sub_question": "..." }}
#   ]
# }}
# """

DEFAULT_CONTEXTUAL_SUBQUESTION_PROMPT_TMPL = """\
A continuación encontrarás información de contexto:
---------------------
{context_str}
---------------------

Pregunta original del usuario:
---------------------
{query_str}
---------------------

Tu tarea consiste en **dividir la pregunta del usuario en exactamente {max_subquestions} sub-preguntas** que:

1. Sean claras y lo más específicas posible.
2. Estén directamente relacionadas con la información de contexto (sin añadir conocimiento externo).
3. Reformulen con tus propias palabras utilizando términos clave del contexto.
4. No hagan referencia explícita al propio contexto (evita frases como “según el texto…”, “el documento indica…”, etc.).

Devuelve la respuesta **únicamente** con el siguiente formato JSON:

```json
{{
  "items": [
    {{ "sub_question": "..." }},
    {{ "sub_question": "..." }},
    {{ "sub_question": "..." }}
  ]
}}
"""

JOINT_QA_SUBQUESTION_PROMPT_TMPL = """\
"A continuación se muestra información de contexto.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Dada la información de contexto y sin usar conocimientos previos, "
    "responde a la siguiente pregunta.\n"
    "Pregunta: {query_str}\n"
    "Respuesta: "

"Tu segunda tarea es descomponer esta pregunta en **exactamente {max_subquestions} subpreguntas** claras, específicas y **directamente relacionadas con el contenido del contexto**."

"Algunas reglas que debes seguir:\n"
        "1. Nunca hagas referencia directa al contexto en tus preguntas."
        "2. Evita frases como "Según el contexto...", "el texto menciona...", "la información indica..." u otras similares."
        "3. Evita hacer subpreguntas que ya estén claramente resueltas en la pregunta original o que repitan lo que ya se pregunta."
        "4. Asegúrate de que cada subpregunta pueda responderse exclusivamente con el contexto proporcionado."

"Formato de salida JSON con esta estructura exacta:"

```json
{{
  "answer": "...respuesta aquí...",
  "items": [
    {{ "sub_question": "..." }},
    {{ "sub_question": "..." }},
    {{ "sub_question": "..." }}
  ]
}}
"""
joint_prompt = PromptTemplate(
    template=JOINT_QA_SUBQUESTION_PROMPT_TMPL,
    prompt_type=PromptType.CUSTOM
)
