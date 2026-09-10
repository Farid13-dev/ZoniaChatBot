from typing import List, Optional
from rag.node.base_node import BaseNode  # Ajusta según tu ruta real
from urllib.parse import quote


class Message:
  def __init__(self, message: str = "", id: Optional[int] = None) -> None:
    self.id = id
    self.message = message

  def __str__(self) -> str:
    return self.message


class Question(Message):
  def __init__(self, message: str = "", id: Optional[int] = None) -> None:
    super().__init__(message, id)

  # def extract_sources(nodes: List[BaseNode]) -> List[dict]:
  #   """Extrae fuentes como diccionarios estructurados para el frontend."""
  #   fuentes = []
  #   for i, node in enumerate(nodes):
  #     meta = node.metadata or {}
  #     fuente = {
  #       "indice": i + 1,
  #       "documento": meta.get("file_name", "Desconocido"),
  #       "pagina": meta.get("num_page", "-")
  #     }
  #     fuentes.append(fuente)
  #   return fuentes

def extract_sources(nodes: List[BaseNode]) -> List[dict]:
    """Extrae fuentes como objetos estructurados y con enlaces a documentos."""
    fuentes = []
    for i, node in enumerate(nodes):
      meta = node.metadata or {}
      file_name = meta.get("file_name", "desconocido.pdf")
      num_page = meta.get("num_page", "-")

      fuente = {
        "indice": i + 1,
        "documento": file_name,
        "pagina": num_page,
        "url": f"http://localhost:8000/pdfjs/web/viewer.html?file={quote(f'/corpus_emb/{file_name}')}#page={num_page}"

      }
      fuentes.append(fuente)
    return fuentes


class Answer(Message):
  def __init__(
    self,
    message: str = "",
    nodes: Optional[List[BaseNode]] = None,
    id: Optional[int] = None,
    saved_question: Optional[str] = None,
  ) -> None:
    super().__init__(message, id)
    self.sources = extract_sources(nodes or [])
    self.saved_question = saved_question

  def lines(self) -> List[str]:
    return self.message.splitlines()
