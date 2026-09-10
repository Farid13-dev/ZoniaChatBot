import re
import logging
from typing import Callable, List, Optional, Set, Dict, cast, TYPE_CHECKING

import pandas as pd
import spacy

from rag.callbacks.callback_manager import CallbackManager
from rag.constants import DEFAULT_SIMILARITY_TOP_K
from rag.retrievers.base import BaseRetriever, QueryBundle
from rag.node.base_node import BaseNode, NodeWithScore
from rag.rag_utils.utils import globals_helper

if TYPE_CHECKING:
    from rag.storage.docstore.base import BaseDocumentStore
    from rag.indices.vector_store import VectorStoreIndex

logger = logging.getLogger(__name__)

# Cargar modelo de spaCy
nlp = spacy.load("es_core_news_sm")


def extract_keywords_dual(text_chunk: str, max_keywords: Optional[int] = None) -> Dict[str, List[str]]:
    doc = nlp(text_chunk.lower())
    keywords_original = [token.text for token in doc if token.pos_ in {"NOUN", "ADJ", "PROPN"}]
    keywords_lemmas = [token.lemma_ for token in doc if token.pos_ in {"NOUN", "ADJ", "PROPN"}]

    counts_lemmas = pd.Series(keywords_lemmas).value_counts()
    top_lemmas = counts_lemmas.index.tolist()[:max_keywords]

    lemma_to_original = {}
    for lemma, original in zip(keywords_lemmas, keywords_original):
        if lemma not in lemma_to_original:
            lemma_to_original[lemma] = original

    top_originals = [lemma_to_original[lemma] for lemma in top_lemmas]

    return {
        "lemmas": list(top_lemmas),
        "original_forms": top_originals
    }


def tokenizer_for_bm25(text: str) -> List[str]:
    dual = extract_keywords_dual(text)
    return list(set(dual["lemmas"] + dual["original_forms"]))  # Usamos ambas para la búsqueda


class BM25Retriever(BaseRetriever):
    def __init__(
        self,
        nodes: List[BaseNode],
        tokenizer: Optional[Callable[[str], List[str]]] = None,
        similarity_top_k: int = DEFAULT_SIMILARITY_TOP_K,
        callback_manager: Optional[CallbackManager] = None,
    ) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            raise ImportError("Please install rank_bm25: pip install rank-bm25")

        self._nodes = nodes
        self._tokenizer = tokenizer or tokenizer_for_bm25
        self._similarity_top_k = similarity_top_k
        self._corpus = [self._tokenizer(node.get_content()) for node in self._nodes]
        self.bm25 = BM25Okapi(self._corpus)
        super().__init__(callback_manager)

    @classmethod
    def from_defaults(
        cls,
        index: Optional["VectorStoreIndex"] = None,
        nodes: Optional[List[BaseNode]] = None,
        docstore: Optional["BaseDocumentStore"] = None,
        tokenizer: Optional[Callable[[str], List[str]]] = None,
        similarity_top_k: int = DEFAULT_SIMILARITY_TOP_K,
    ) -> "BM25Retriever":
        if sum(bool(val) for val in [index, nodes, docstore]) != 1:
            raise ValueError("Please pass exactly one of index, nodes, or docstore.")

        if index is not None:
            docstore = index.docstore

        if docstore is not None:
            nodes = cast(List[BaseNode], list(docstore.docs.values()))

        assert nodes is not None, "Please pass exactly one of index, nodes, or docstore."

        tokenizer = tokenizer or tokenizer_for_bm25
        return cls(
            nodes=nodes,
            tokenizer=tokenizer,
            similarity_top_k=similarity_top_k,
        )

    def _get_scored_nodes(self, query: str) -> List[NodeWithScore]:
        dual_keywords = extract_keywords_dual(query)
        combined_query_terms = list(set(dual_keywords["lemmas"] + dual_keywords["original_forms"]))

        # print("🔎 Búsqueda con términos combinados:", combined_query_terms)
        # print("🗣️  Palabras originales:", dual_keywords["original_forms"])

        doc_scores = self.bm25.get_scores(combined_query_terms)

        scored_nodes = []
        for i, node in enumerate(self._nodes):
            node_copy = node.copy()
            node_copy.metadata = node_copy.metadata or {}
            node_copy.metadata["query_terms"] = dual_keywords["original_forms"]
            scored_nodes.append(NodeWithScore(node=node_copy, score=doc_scores[i]))

        return scored_nodes

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        if query_bundle.custom_embedding_strs or query_bundle.embedding:
            logger.warning("BM25Retriever does not support embeddings, skipping...")

        scored_nodes = self._get_scored_nodes(query_bundle.query_str)
        return sorted(scored_nodes, key=lambda x: x.score or 0.0, reverse=True)[:self._similarity_top_k]


# import re
# import logging
# from typing import Callable, List, Optional, Set, cast, TYPE_CHECKING
#
# import pandas as pd
# import spacy
#
# from rag.callbacks.callback_manager import CallbackManager
# from rag.constants import DEFAULT_SIMILARITY_TOP_K
# from rag.retrievers.base import BaseRetriever, QueryBundle
# from rag.node.base_node import BaseNode, NodeWithScore
# from rag.rag_utils.utils import globals_helper  # Tu lista de stopwords personalizada
#
# if TYPE_CHECKING:
#     from rag.storage.docstore.base import BaseDocumentStore
#     from rag.indices.vector_store import VectorStoreIndex
#
# logger = logging.getLogger(__name__)
#
# # Cargar spaCy solo para stopwords y lematización ligera
# nlp = spacy.load("es_core_news_sm")
# spanish_stopwords = nlp.Defaults.stop_words.union(globals_helper.stopwords)
#
#
# def simple_extract_keywords(
#     text_chunk: str, max_keywords: Optional[int] = None, filter_stopwords: bool = True
# ) -> Set[str]:
#     tokens = [t.strip().lower() for t in re.findall(r"\w+", text_chunk)]
#     if filter_stopwords:
#         tokens = [t for t in tokens if t not in spanish_stopwords]
#     value_counts = pd.Series(tokens).value_counts()
#     keywords = value_counts.index.tolist()[:max_keywords]
#     return set(keywords)
#
#
# def tokenize_remove_stopwords(text: str) -> List[str]:
#     words = list(simple_extract_keywords(text))
#     return words
#
#
# class BM25Retriever(BaseRetriever):
#     def __init__(
#         self,
#         nodes: List[BaseNode],
#         tokenizer: Optional[Callable[[str], List[str]]] = None,
#         similarity_top_k: int = DEFAULT_SIMILARITY_TOP_K,
#         callback_manager: Optional[CallbackManager] = None,
#     ) -> None:
#         try:
#             from rank_bm25 import BM25Okapi
#         except ImportError:
#             raise ImportError("Please install rank_bm25: pip install rank-bm25")
#
#         self._nodes = nodes
#         self._tokenizer = tokenizer or tokenize_remove_stopwords
#         self._similarity_top_k = similarity_top_k
#         self._corpus = [self._tokenizer(node.get_content()) for node in self._nodes]
#         self.bm25 = BM25Okapi(self._corpus)
#         super().__init__(callback_manager)
#
#     @classmethod
#     def from_defaults(
#         cls,
#         index: Optional["VectorStoreIndex"] = None,
#         nodes: Optional[List[BaseNode]] = None,
#         docstore: Optional["BaseDocumentStore"] = None,
#         tokenizer: Optional[Callable[[str], List[str]]] = None,
#         similarity_top_k: int = DEFAULT_SIMILARITY_TOP_K,
#     ) -> "BM25Retriever":
#         if sum(bool(val) for val in [index, nodes, docstore]) != 1:
#             raise ValueError("Please pass exactly one of index, nodes, or docstore.")
#
#         if index is not None:
#             docstore = index.docstore
#
#         if docstore is not None:
#             nodes = cast(List[BaseNode], list(docstore.docs.values()))
#
#         assert nodes is not None, "Please pass exactly one of index, nodes, or docstore."
#
#         tokenizer = tokenizer or tokenize_remove_stopwords
#         return cls(
#             nodes=nodes,
#             tokenizer=tokenizer,
#             similarity_top_k=similarity_top_k,
#         )
#
#     def _get_scored_nodes(self, query: str) -> List[NodeWithScore]:
#         tokenized_query = self._tokenizer(query)
#         print("Key:", tokenized_query)
#         doc_scores = self.bm25.get_scores(tokenized_query)
#
#         return [
#             NodeWithScore(node=node, score=doc_scores[i])
#             for i, node in enumerate(self._nodes)
#         ]
#
#     def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
#         if query_bundle.custom_embedding_strs or query_bundle.embedding:
#             logger.warning("BM25Retriever does not support embeddings, skipping...")
#
#         scored_nodes = self._get_scored_nodes(query_bundle.query_str)
#         return sorted(scored_nodes, key=lambda x: x.score or 0.0, reverse=True)[:self._similarity_top_k]
