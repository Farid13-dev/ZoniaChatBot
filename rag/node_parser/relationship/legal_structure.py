# import re
# from pathlib import Path
# from typing import List, Optional, Callable
#
# from rag.node.base_node import TextNode, Document
# from rag.node_parser.base import NodeParser
# from rag.bridge.pydantic import Field
# from rag.callbacks.callback_manager import CallbackManager
# from rag.node_parser.utils import default_id_func
# from rag.rag_utils.utils import get_tokenizer
# from typing import Sequence
# from rag.node.base_node import BaseNode
# from rag.bridge.pydantic import PrivateAttr  # ya lo tienes
#
# class LegalStructureParser(NodeParser):
#     """Parser especializado en documentos legales con estructura jerárquica."""
#     _tokenizer: Callable = PrivateAttr()
#     def __init__(
#             self,
#             tokenizer=None,
#             callback_manager: Optional[CallbackManager] = None,
#             include_metadata: bool = True,
#             include_prev_next_rel: bool = True,
#             id_func: Optional[callable] = None,
#     ):
#         super().__init__(
#             callback_manager=callback_manager or CallbackManager(),
#             include_metadata=include_metadata,
#             include_prev_next_rel=include_prev_next_rel,
#             id_func=id_func or default_id_func,
#         )
#         self._tokenizer = tokenizer or get_tokenizer()
#
#     @classmethod
#     def class_name(cls) -> str:
#         return "LegalStructureParser"
#
#     # def get_nodes_from_documents(self, documents: List[Document], **kwargs) -> List[TextNode]:
#     #     all_nodes = []
#     #     for doc in documents:
#     #         chunks = parse_pdf_grouped_by_structure(doc.text)
#     #         for chunk in chunks:
#     #             full_text = chunk["contenido"]
#     #             token_count = len(self._tokenizer(full_text))
#     #             node = TextNode(
#     #                 text=full_text,
#     #                 metadata={
#     #                     "chunk_id": chunk["chunk_id"],
#     #                     "titulo": chunk["titulo"],
#     #                     "capitulo": chunk["capitulo"],
#     #                     "subcapitulo": chunk["subcapitulo"],
#     #                     "articulos": chunk["articulo"],
#     #                     "paragrafos": chunk["paragrafo"],
#     #                     "token_count": token_count,
#     #                 },
#     #             )
#     #             all_nodes.append(node)
#     #     return all_nodes
#
#     def save_to_file(self,content, filename):
#         file_path = Path(f"data/{filename}")
#         with open(file_path, "w", encoding="utf-8") as f:
#             f.write(content)
#         print(f"✅ Guardado: {file_path}")
#
#     def get_nodes_from_documents(self, documents: List[Document], **kwargs) -> List[TextNode]:
#         from rag.node.base_node import TextNode  # Asegura el import correcto
#         combined_text = "\n".join([doc.text for doc in documents])
#         self.save_to_file(combined_text, "combined_text.txt")
#         chunks = parse_pdf_grouped_by_structure(combined_text)
#         chunks_output = "\n\n".join(
#             f"[Chunk {chunk['chunk_id']}]\n{chunk['contenido']}" for chunk in chunks
#         )
#         self.save_to_file(chunks_output, "chunks_output.txt")
#
#         nodes = []
#         for chunk in chunks:
#             full_text = chunk["contenido"]
#             token_count = len(self._tokenizer(full_text))
#             node = TextNode(
#                 text=full_text,
#                 metadata={
#                     "chunk_id": chunk["chunk_id"],
#                     "titulo": chunk["titulo"],
#                     "capitulo": chunk["capitulo"],
#                     "subcapitulo": chunk["subcapitulo"],
#                     "articulos": chunk["articulo"],
#                     "paragrafos": chunk["paragrafo"],
#                     "token_count": token_count,
#                 },
#             )
#             nodes.append(node)
#
#         return nodes
#
#     def _parse_nodes(self, nodes: Sequence[BaseNode], show_progress: bool = False, **kwargs) -> List[BaseNode]:
#         return list(nodes)
#
#
# # === Funciones auxiliares ===
#
# def split_combined_headers(line):
#     titulo_match = re.search(r"(t[ií]tulo\s+\d+[:\s].*?)(?=cap[ií]tulo\s+\d+[:\s])", line, re.IGNORECASE)
#     capitulo_match = re.search(r"(cap[ií]tulo\s+\d+[:\s].*)", line, re.IGNORECASE)
#     titulo = titulo_match.group(1).strip() if titulo_match else None
#     capitulo = capitulo_match.group(1).strip() if capitulo_match else None
#     return titulo, capitulo
#
#
# def parse_pdf_grouped_by_structure(text: str):
#     lines = text.splitlines()
#     chunks, chunk_id = [], 0
#     current_titulo = current_capitulo = current_subcapitulo = None
#     current_articles, current_paragraphs, current_text_block, buffer = [], [], [], []
#
#     def save_group_chunk():
#         nonlocal chunk_id
#         if buffer:
#             current_text_block.append("\n".join(buffer).strip())
#             buffer.clear()
#         if current_articles or current_paragraphs or current_text_block:
#             full_text = "\n".join(
#                 filter(None, [current_titulo, current_capitulo, current_subcapitulo] + current_text_block)).strip()
#             chunks.append({
#                 "chunk_id": chunk_id,
#                 "titulo": current_titulo,
#                 "capitulo": current_capitulo,
#                 "subcapitulo": current_subcapitulo,
#                 "articulo": current_articles.copy(),
#                 "paragrafo": current_paragraphs.copy(),
#                 "contenido": full_text
#             })
#             chunk_id += 1
#         current_articles.clear()
#         current_paragraphs.clear()
#         current_text_block.clear()
#         buffer.clear()
#
#     for line in lines:
#         l = line.strip()
#         if not l:
#             continue
#         if re.search(r"t[ií]tulo\s+\d+[:\s].*cap[ií]tulo\s+\d+[:\s]", l, re.IGNORECASE):
#             save_group_chunk()
#             current_titulo, current_capitulo = split_combined_headers(l)
#             current_subcapitulo = None
#             continue
#         if re.match(r"^t[ií]tulo\s+\d+[:\s]", l, re.IGNORECASE):
#             save_group_chunk()
#             current_titulo = l
#             current_capitulo = current_subcapitulo = None
#             continue
#         if re.match(r"^cap[ií]tulo\s+\d+[:\s]", l, re.IGNORECASE):
#             save_group_chunk()
#             current_capitulo = l
#             current_subcapitulo = None
#             continue
#         if re.match(r"^subcap[ií]tulo\s+\d+[:\s]", l, re.IGNORECASE):
#             save_group_chunk()
#             current_subcapitulo = l
#             continue
#         if re.match(r"^art[íi]culo\s+\d+", l, re.IGNORECASE):
#             if buffer:
#                 current_text_block.append("\n".join(buffer).strip())
#                 buffer.clear()
#             current_articles.append(l)
#             buffer.append(l)
#             continue
#         if re.match(r"^par[aá]grafo\s*\d*[:\s]?", l, re.IGNORECASE):
#             current_paragraphs.append(l)
#             buffer.append(l)
#             continue
#         buffer.append(l)
#
#     save_group_chunk()
#     return chunks


import re
from pathlib import Path
from typing import List, Optional, Callable, Sequence, Tuple

from rag.node.base_node import TextNode, Document, BaseNode
from rag.node_parser.base import NodeParser
from rag.bridge.pydantic import Field, PrivateAttr
from rag.callbacks.callback_manager import CallbackManager
from rag.node_parser.utils import default_id_func
from rag.rag_utils.utils import get_tokenizer


class LegalStructureParser(NodeParser):
    """Parser especializado en documentos legales con estructura jerárquica y metadatos."""

    _tokenizer: Callable = PrivateAttr()

    def __init__(
        self,
        tokenizer=None,
        callback_manager: Optional[CallbackManager] = None,
        include_metadata: bool = True,
        include_prev_next_rel: bool = True,
        id_func: Optional[Callable] = None,
    ):
        super().__init__(
            callback_manager=callback_manager or CallbackManager(),
            include_metadata=include_metadata,
            include_prev_next_rel=include_prev_next_rel,
            id_func=id_func or default_id_func,
        )
        self._tokenizer = tokenizer or get_tokenizer()

    @classmethod
    def class_name(cls) -> str:
        return "LegalStructureParser"

    def _count_tokens(self, text: str) -> int:
      if hasattr(self._tokenizer, "encode"):
        return len(self._tokenizer.encode(text))
      return len(self._tokenizer(text))  # fallback para otros tokenizers

    def get_nodes_from_documents(self, documents: List[Document], **kwargs) -> List[TextNode]:
        lines_with_meta = []

        for doc in documents:
            metadata = doc.metadata
            for line in doc.text.splitlines():
                if line.strip():
                    lines_with_meta.append((line.strip(), metadata))

        chunks = parse_pdf_grouped_by_structure_with_metadata(lines_with_meta)

        nodes = []
        for chunk in chunks:
            # token_count = len(self._tokenizer(chunk["text"]))
            token_count = self._count_tokens(chunk["text"])

            #token_count = len(self._tokenizer.encode(chunk["text"]))  # ✅ CORRECTO

            node = TextNode(
                text=chunk["text"],
                metadata={**chunk, "token_count": token_count}
            )
            nodes.append(node)

        return nodes

    def _parse_nodes(self, nodes: Sequence[BaseNode], show_progress: bool = False, **kwargs) -> List[BaseNode]:
        return list(nodes)


# === Función auxiliar mejorada con metadatos por página ===

def split_combined_headers(line: str) -> Tuple[Optional[str], Optional[str]]:
    titulo_match = re.search(r"(t[ií]tulo\s+\d+[:\s].*?)(?=cap[ií]tulo\s+\d+[:\s])", line, re.IGNORECASE)
    capitulo_match = re.search(r"(cap[ií]tulo\s+\d+[:\s].*)", line, re.IGNORECASE)
    titulo = titulo_match.group(1).strip() if titulo_match else None
    capitulo = capitulo_match.group(1).strip() if capitulo_match else None
    return titulo, capitulo


def parse_pdf_grouped_by_structure_with_metadata(
    lines_with_meta: List[Tuple[str, dict]]
) -> List[dict]:
    chunks, chunk_id = [], 0
    current_titulo = current_capitulo = current_subcapitulo = None
    current_articles, current_paragraphs, current_text_block, buffer = [], [], [], []
    last_metadata: dict = {}

    def save_group_chunk():
        nonlocal chunk_id
        if buffer:
            current_text_block.append("\n".join(buffer).strip())
            buffer.clear()

        if current_articles or current_paragraphs or current_text_block:
            full_text = "\n".join(
                filter(None, [current_titulo, current_capitulo, current_subcapitulo] + current_text_block)
            ).strip()

            chunks.append({
                "chunk_id": chunk_id,
                "titulo": current_titulo,
                "capitulo": current_capitulo,
                "subcapitulo": current_subcapitulo,
                "articulos": current_articles.copy(),
                "paragrafos": current_paragraphs.copy(),
                "text": full_text,
                **last_metadata,
            })
            chunk_id += 1

        current_articles.clear()
        current_paragraphs.clear()
        current_text_block.clear()
        buffer.clear()

    for line, metadata in lines_with_meta:
        last_metadata = metadata  # actualiza siempre
        if re.search(r"t[ií]tulo\s+\d+[:\s].*cap[ií]tulo\s+\d+[:\s]", line, re.IGNORECASE):
            save_group_chunk()
            current_titulo, current_capitulo = split_combined_headers(line)
            current_subcapitulo = None
            continue
        if re.match(r"^t[ií]tulo\s+\d+[:\s]", line, re.IGNORECASE):
            save_group_chunk()
            current_titulo = line
            current_capitulo = current_subcapitulo = None
            continue
        if re.match(r"^cap[ií]tulo\s+\d+[:\s]", line, re.IGNORECASE):
            save_group_chunk()
            current_capitulo = line
            current_subcapitulo = None
            continue
        if re.match(r"^subcap[ií]tulo\s+\d+[:\s]", line, re.IGNORECASE):
            save_group_chunk()
            current_subcapitulo = line
            continue
        if re.match(r"^art[íi]culo\s+\d+", line, re.IGNORECASE):
            if buffer:
                current_text_block.append("\n".join(buffer).strip())
                buffer.clear()
            current_articles.append(line)
            buffer.append(line)
            continue
        if re.match(r"^par[aá]grafo\s*\d*[:\s]?", line, re.IGNORECASE):
            current_paragraphs.append(line)
            buffer.append(line)
            continue

        buffer.append(line)

    save_group_chunk()
    return chunks
