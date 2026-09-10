"""Set of default prompts."""
#	Base para prompts simples tipo texto plano.
from rag.prompt.prompt_template import PromptTemplate
from rag.prompt.types import PromptType

############################################
# Tree
############################################

DEFAULT_SUMMARY_PROMPT_TMPL = (
  "Escribe un resumen del siguiente contenido. Intenta usar únicamente "
  "la información proporcionada. "
  "Intenta incluir la mayor cantidad de detalles clave posible.\n"
  "\n"
  "{context_str}\n"
  "\n"
  'RESUMEN:"""\n'
)

DEFAULT_SUMMARY_PROMPT = PromptTemplate(
  DEFAULT_SUMMARY_PROMPT_TMPL, prompt_type=PromptType.SUMMARY
)

# insert prompts
DEFAULT_INSERT_PROMPT_TMPL = (
  "A continuación se muestra información de contexto en una lista numerada "
  "(del 1 al {num_chunks}), "
  "donde cada elemento corresponde a un resumen.\n"
  "---------------------\n"
  "{context_list}"
  "---------------------\n"
  "Dada la información de contexto, aquí hay una nueva pieza de información: {new_chunk_text}\n"
  "Responde con el número correspondiente al resumen que debería actualizarse. "
  "La respuesta debe ser el número del resumen más relevante para la nueva información.\n"
)

DEFAULT_INSERT_PROMPT = PromptTemplate(
  DEFAULT_INSERT_PROMPT_TMPL, prompt_type=PromptType.TREE_INSERT
)

# # single choice
DEFAULT_QUERY_PROMPT_TMPL = (
  "A continuación se muestran varias opciones en una lista numerada "
  "(del 1 al {num_chunks}), "
  "donde cada elemento corresponde a un resumen.\n"
  "---------------------\n"
  "{context_list}"
  "\n---------------------\n"
  "Usando únicamente las opciones mostradas (sin conocimiento previo), elige "
  "la que sea más relevante para responder la siguiente pregunta: '{query_str}'\n"
  "Proporciona la elección en el siguiente formato: 'RESPUESTA: <número>' y explica "
  "por qué se seleccionó ese resumen en relación con la pregunta.\n"
)

DEFAULT_QUERY_PROMPT = PromptTemplate(
  DEFAULT_QUERY_PROMPT_TMPL, prompt_type=PromptType.TREE_SELECT
)

# multiple choice
DEFAULT_QUERY_PROMPT_MULTIPLE_TMPL = (
  "A continuación se muestran varias opciones en una lista numerada "
  "(del 1 al {num_chunks}), "
  "donde cada elemento corresponde a un resumen.\n"
  "---------------------\n"
  "{context_list}"
  "\n---------------------\n"
  "Usando únicamente las opciones mostradas (sin conocimiento previo), selecciona las mejores "
  "opciones (máximo {branching_factor}, ordenadas de mayor a menor relevancia) que sean "
  "más relevantes para la pregunta: '{query_str}'\n"
  "Proporciona las elecciones en el siguiente formato: 'RESPUESTA: <números>' y explica por qué "
  "fueron seleccionadas en relación con la pregunta.\n"
)

DEFAULT_QUERY_PROMPT_MULTIPLE = PromptTemplate(
  DEFAULT_QUERY_PROMPT_MULTIPLE_TMPL, prompt_type=PromptType.TREE_SELECT_MULTIPLE
)

DEFAULT_REFINE_PROMPT_TMPL = (
  "La pregunta original es la siguiente: {query_str}\n"
  "Se proporciona una respuesta existente: {existing_answer}\n"
  "Tenemos la oportunidad de refinar la respuesta existente "
  "(solo si es necesario) con algo de contexto adicional:\n"
  "------------\n"
  "{context_msg}\n"
  "------------\n"
  "Dado el nuevo contexto, mejora la respuesta original para que responda mejor a la pregunta. "
  "Si el contexto no es útil, devuelve la respuesta original.\n"
  "Respuesta refinada: "
)

DEFAULT_REFINE_PROMPT = PromptTemplate(
  DEFAULT_REFINE_PROMPT_TMPL, prompt_type=PromptType.REFINE
)

DEFAULT_TEXT_QA_PROMPT_TMPL = (
  "A continuación se muestra información de contexto.\n"
  "---------------------\n"
  "{context_str}\n"
  "---------------------\n"
  "Dada la información de contexto y sin usar conocimientos previos, "
  "responde a la siguiente pregunta.\n"
  "Pregunta: {query_str}\n"
  "Respuesta: "
)

DEFAULT_TEXT_QA_PROMPT = PromptTemplate(
  DEFAULT_TEXT_QA_PROMPT_TMPL, prompt_type=PromptType.QUESTION_ANSWER
)

DEFAULT_TREE_SUMMARIZE_TMPL = (
  "A continuación se muestra información de múltiples fuentes.\n"
  "---------------------\n"
  "{context_str}\n"
  "---------------------\n"
  "Dada la información proporcionada por múltiples fuentes y sin usar conocimiento externo, "
  "responde a la siguiente pregunta.\n"
  "Pregunta: {query_str}\n"
  "Respuesta: "
)

DEFAULT_TREE_SUMMARIZE_PROMPT = PromptTemplate(
  DEFAULT_TREE_SUMMARIZE_TMPL, prompt_type=PromptType.SUMMARY
)

############################################
# Keyword Table
############################################

DEFAULT_KEYWORD_EXTRACT_TEMPLATE_TMPL = (
  "A continuación se proporciona un texto. Extrae hasta {max_keywords} "
  "palabras clave del texto. Evita palabras vacías o irrelevantes.\n"
  "---------------------\n"
  "{text}\n"
  "---------------------\n"
  "Proporciona las palabras clave en el siguiente formato (separadas por comas): 'PALABRAS CLAVE: <palabras>'\n"
)

DEFAULT_KEYWORD_EXTRACT_TEMPLATE = PromptTemplate(
  DEFAULT_KEYWORD_EXTRACT_TEMPLATE_TMPL, prompt_type=PromptType.KEYWORD_EXTRACT
)

# NOTE: the keyword extraction for queries can be the same as
# the one used to build the index, but here we tune it to see if performance is better.
DEFAULT_QUERY_KEYWORD_EXTRACT_TEMPLATE_TMPL = (
  "A continuación se proporciona una pregunta. Extrae hasta {max_keywords} "
  "palabras clave que podamos usar para buscar las mejores respuestas. Evita palabras vacías.\n"
  "usa unicamente las palabras clave proporcionadas."
  "---------------------\n"
  "{question}\n"
  "---------------------\n"
  "Proporciona las palabras clave en el siguiente formato (separadas por comas): 'PALABRAS CLAVE: <palabras>'\n"
)

DEFAULT_QUERY_KEYWORD_EXTRACT_TEMPLATE = PromptTemplate(
  DEFAULT_QUERY_KEYWORD_EXTRACT_TEMPLATE_TMPL,
  prompt_type=PromptType.QUERY_KEYWORD_EXTRACT,
)

REFORMULATE_QUESTION_WITH_KEYWORDS_TMPL = (
  "A continuación se proporciona una pregunta original.\n"
  "---------------------\n"
  "Pregunta original: {original_question}\n"
  "---------------------\n"
  "Se proporciona una lista de palabras clave."
  "Palabras clave: {keywords}\n"
  "---------------------\n"
  "Tu tarea es **reformular la pregunta** de forma clara y natural, **usando únicamente las palabras clave proporcionadas**.\n"
  "Si no puedes formar una pregunta con las palabras clave, devuelve la pregunta original sin cambios.\n"
  "La salida debe ser una pregunta completa.\n"
  "---------------------\n"
  "Pregunta reformulada:"
)

REFORMULATE_QUESTION_WITH_KEYWORDS = PromptTemplate(
  REFORMULATE_QUESTION_WITH_KEYWORDS_TMPL,
  prompt_type=PromptType.CUSTOM,
)

# REFORMULATE_WITH_INTERNAL_KEYWORDS_TMPL = (
#   "A continuación se proporciona una pregunta, posiblemente con errores gramaticales o incompleta.\n"
#   "---------------------\n"
#   "Pregunta: {question}\n"
#   "---------------------\n"
#   "Tu tarea es **reformular la pregunta** de forma clara y natural en español, **usando únicamente la pregunta**.\n"
#   "Identifica las palabras claves importantes de la pregunta. Luego, úsalas para reconstruir la pregunta de forma completa.\n"
#   "La salida debe ser una pregunta completa.\n"
#   "---------------------\n"
#   "Pregunta reformulada:"
# )

REFORMULATE_WITH_INTERNAL_KEYWORDS_TMPL = (
    "A continuación se proporciona una pregunta en español, que puede tener errores gramaticales o estar incompleta.\n"
    "---------------------\n"
    "Pregunta: {question}\n"
    "---------------------\n"
    "Tu tarea es reformular la pregunta de forma **clara y natural**, manteniendo **exactamente las palabras clave importantes** presentes en la pregunta original.\n"
    "No debes cambiar el significado ni reemplazar palabras clave por sinónimos o conceptos parecidos.\n"
    "No agregues información nueva ni intentes mejorar el contenido más allá de la corrección gramatical o estructural.\n"
    "La salida debe ser una **única pregunta reformulada**, clara, completa y en español neutro.\n"
    "---------------------\n"
    "Pregunta reformulada:"
)


REFORMULATE_WITH_INTERNAL_KEYWORDS = PromptTemplate(
  template=REFORMULATE_WITH_INTERNAL_KEYWORDS_TMPL,
  prompt_type=PromptType.CUSTOM,
)

############################################
# Simple Input
############################################

DEFAULT_SIMPLE_INPUT_TMPL = "{query_str}"
DEFAULT_SIMPLE_INPUT_PROMPT = PromptTemplate(
  DEFAULT_SIMPLE_INPUT_TMPL, prompt_type=PromptType.SIMPLE_INPUT
)

############################################
# Choice Select
############################################

DEFAULT_CHOICE_SELECT_PROMPT_TMPL = (
  "A continuación se muestra una lista de documentos. Cada documento tiene un número y un resumen. "
  "También se proporciona una pregunta.\n"
  "Responde con los números de los documentos que se deben consultar para responder la pregunta, en orden de relevancia, "
  "junto con un puntaje de relevancia del 1 al 10.\n"
  "No incluyas documentos que no sean relevantes.\n"
  "Ejemplo de formato:\n"
  "Documento 1:\n<resumen del documento 1>\n\n"
  "Documento 2:\n<resumen del documento 2>\n\n"
  "...\n\n"
  "Pregunta: <pregunta>\n"
  "Respuesta:\n"
  "Doc: 9, Relevancia: 7\n"
  "Doc: 3, Relevancia: 4\n"
  "Doc: 7, Relevancia: 3\n\n"
  "Ahora tú:\n\n"
  "{context_str}\n"
  "Pregunta: {query_str}\n"
  "Respuesta:\n"
)

DEFAULT_CHOICE_SELECT_PROMPT = PromptTemplate(
  DEFAULT_CHOICE_SELECT_PROMPT_TMPL, prompt_type=PromptType.CHOICE_SELECT
)

USER_PROMT_ITENT_DOUBLE = """\
    "A continuación se proporciona una pregunta. "
    "---------------------\n"
    "{query_str}\n"
    "---------------------\n"
    "Tu tarea es clasificar la pregunta en negativo o positivo"
    "Negativo:\n"
        "1. Insultos o lenguaje inapropiado."
        "2. Sentimientos o emociones (ej. “estoy triste”, “me siento feliz”, etc)."
        "3. Es un saludo o despedida (ej. "hola", "buenos días", "gracias", "hasta luego", etc.)."
        "4. Es corta o carece de sentido (“a”, “?”, “asdf”, “65”, etc.)."
        "5. Preguntas fuera del alcance (ej. “hazme una carta”, “cómo ganar dinero”, etc.)."
    "Positivo:\n"
        "1. Tiene estructura coherente o intención clara"
        "2. Es una pregunta realcionada con temas universitarios, (por ejemplo, requisitos de inscripción, admisión y matrícula, derechos y deberes, distinciones e incentivos, régimen disciplinario, aspectos académicos, aspectos administrativos, posgrado, pregrado , etc.)."

Clasifica la intención **únicamente como una de las siguientes dos etiquetas**:
- `"Positivo"`
- `"Negativo"`

Formato de salida: JSON con esta estructura exacta:

```json
{{
 "etiqueta": "Positivo" | "Negativo",
 "motivo": "Breve explicación del por qué"
}}
"""
PROMT_USER_INTENT_DOUBLE = PromptTemplate(
  template=USER_PROMT_ITENT_DOUBLE,
  prompt_type=PromptType.CUSTOM,
)

USER_PROMT_ITENT_TREE = """\
    "A continuación se proporciona una pregunta. "
    "---------------------\n"
    "{query_str}\n"
    "---------------------\n"
    "Tu tarea es clasificar la pregunta en negativo o positivo"
    "Positivo:\n"
        "1. Tiene estructura coherente o intención clara"
        "2. Es una pregunta realcionada con temas universitarios, (por ejemplo, requisitos de inscripción, admisión y matrícula, derechos y deberes, distinciones e incentivos, régimen disciplinario, aspectos académicos, aspectos administrativos, posgrado, pregrado , etc.)"
    "Negativo:\n"
        "1. Insultos o lenguaje inapropiado."
        "2. Sentimientos o emociones (ej. “estoy triste”, “me siento feliz”, etc)."
        "4. Es corta o carece de sentido (“a”, “?”, “asdf”, “65”, etc.)."
        "5. Preguntas fuera del alcance (ej. “hazme una carta”, “cómo ganar dinero”, etc.)."
    "Neutro:\n
        "1. Es un saludo (ej. "hola", "buenos días", etc."
        "2. Es una despedida (ej. "gracias", "hasta luego", etc.)"
        "3. Es una expresión social, cortesía, o interacción sin intención de consulta académica."

Clasifica la intención **únicamente como una de las siguientes tres etiquetas**:
- `"Positivo"`
- `"Negativo"`
- `"Neutro"`

Formato de salida: JSON con esta estructura exacta:

```json
{{
 "etiqueta": "Positivo" | "Negativo" | "Neutro",
 "motivo": "Breve explicación del por qué"
}}
"""
PROMT_USER_INTENT_TREE = PromptTemplate(
  template=USER_PROMT_ITENT_TREE,
  prompt_type=PromptType.CUSTOM,
)
