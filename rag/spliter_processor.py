from typing import Union, List
import jieba
import re


class spliter_processor:
  def __init__(self, chunk_size: int = 250, chunk_overlap: int = 50):
    self.chunk_size = chunk_size
    self.chunk_overlap = chunk_overlap

  def _split_spanish_text(self, text: str) -> List[str]:
    # División de texto espáñol por frases mediante expresiones regulares
    sentences = re.split(r'(?<=[.!?])\s+', text.replace('\n', ' '))
    chunks = []
    current_chunk = ''
    for sentence in sentences:
      if len(current_chunk) + len(sentence) <= self.chunk_size:
        current_chunk += (' ' if current_chunk else '') + sentence
      else:
        if len(sentence) > self.chunk_size:
          for i in range(0, len(sentence), self.chunk_size):
            chunks.append(sentence[i:i + self.chunk_size])
          current_chunk = ''
        else:
          chunks.append(current_chunk)
          current_chunk = sentence
    if current_chunk:  # Añade el último trozo
      chunks.append(current_chunk)

    if self.chunk_overlap > 0 and len(chunks) > 1:
      chunks = self._handle_overlap(chunks)

    return chunks

  def _handle_overlap(self, chunks: List[str]) -> List[str]:
    # Tratamiento de los solapamientos entre bloques
    overlapped_chunks = []
    for i in range(len(chunks) - 1):
      chunk = chunks[i] + ' ' + chunks[i + 1][:self.chunk_overlap]
      overlapped_chunks.append(chunk.strip())
    overlapped_chunks.append(chunks[-1])
    return overlapped_chunks


full_text = """
    acuerdo 09 de 2007 (mayo 18) por el cual se adopta el estatuto estudiantil.
    el consejo superior de la universidad de la amazonia en ejercicio de sus atribuciones legales y estatutarias, y, considerando que: el artículo 69 de la constitución nacional y el artículo 28 de la ley 30 de 1992, establecen que en el marco de la autonomía universitaria, uno de los aspectos a determinar, es la adopción del estatuto estudiantil.
    en coherencia con el artículo 109 de la ley 30 de 1992 o norma que la modifique o sustituya, la universidad de la amazonia debe tener un estatuto estudiantil que regule aspectos tales como: requisitos de inscripción, admisión y matrícula, derechos y deberes, distinciones e incentivos, régimen disciplinario y demás aspectos académicos.
    los programas académicos de pregrado preparan para el desempeño de ocupaciones, para el ejercicio de una profesión o disciplina determinada, de naturaleza tecnológica o científica, acorde con lo establecido en el artículo 9º de la ley 30 de 1992, en concordancia con los artículos 19 y 107 ibidem.
    es responsabilidad de las instancias y directivas de la institución, actualizar y modernizar, las normas que regulan los procesos académicos y administrativos de la universidad de la amazonia.
    en mérito de lo expuesto, acuerda: artículo 1, adopción: adoptar el presente estatuto estudiantil para regular las relaciones recíprocas, entre la universidad de la amazonia y sus estudiantes de pregrado.
    """
splitter = spliter_processor(chunk_size=250, chunk_overlap=0)

sentences = splitter._split_spanish_text(full_text)

print("Sentences:", sentences)
