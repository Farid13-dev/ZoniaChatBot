from enum import Enum

class ResponseMode(str, Enum):
    """Modos de respuesta del generador de respuestas (y del sintetizador)."""

    SIMPLE_SUMMARIZE = "simple_summarize"
    """
    Une todos los fragmentos de texto en uno solo y realiza una llamada al LLM.
    Esto fallará si el texto combinado excede el tamaño de la ventana de contexto.
    """

    TREE_SUMMARIZE = "tree_summarize"
    """
    Construye un índice en forma de árbol sobre el conjunto de nodos candidatos, utilizando un prompt de resumen inicializado con la consulta.
    El árbol se construye de abajo hacia arriba, y al final se devuelve el nodo raíz como respuesta.
    """

    GENERATION = "generation"
    """Ignora el contexto y utiliza únicamente el LLM para generar una respuesta."""

    NO_TEXT = "no_text"
    """Devuelve los nodos de contexto recuperados, sin sintetizar una respuesta final."""
