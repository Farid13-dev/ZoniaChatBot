from typing import Any, List, Optional

from rag.callbacks.callback_manager import CallbackManager
from rag.retrievers.base import BaseRetriever
from rag.node.base_node import NodeWithScore
from rag.rerank.base import BaseNodePostprocessor
from rag.retrievers.types import QueryBundle, QueryType

from .base import BaseEngine
from rag.synthesizer.types import RESPONSE_TYPE

class RetrieverEngine(BaseEngine):
    """Retriever query engine.

    Args:
        retriever (BaseRetriever): A retriever object.
        node_postprocessors (Optional[List[BaseNodePostprocessor]]): List of node postprocessors objects.
        callback_manager (Optional[CallbackManager]): A callback manager.
    """

    def __init__(
            self,
            retriever: BaseRetriever,
            node_postprocessors: Optional[List[BaseNodePostprocessor]] = None,
            callback_manager: Optional[CallbackManager] = None,
    ) -> None:
        self._retriever = retriever
        self._node_postprocessors = node_postprocessors or []
        callback_manager = callback_manager or CallbackManager([])
        for node_postprocessor in self._node_postprocessors:
            node_postprocessor.callback_manager = callback_manager

        super().__init__(callback_manager)

    def _apply_node_postprocessors(
            self, nodes: List[NodeWithScore], str_or_query_bundle: QueryType
    ) -> List[NodeWithScore]:
        for idx, node_postprocessor in enumerate(self._node_postprocessors):
            nodes = node_postprocessor.postprocess_nodes(
                nodes, str_or_query_bundle=str_or_query_bundle
            )
            #print(f"Score Rerank {idx}: {[score_node.get_score() for score_node in nodes]}")
        return nodes

    def retrieve(self, str_or_query_bundle: QueryType) -> List[NodeWithScore]:
        nodes = self._retriever.retrieve(str_or_query_bundle)
        #print(f"Score Retrieval: {[score_node.get_score() for score_node in nodes]}")
        return self._apply_node_postprocessors(nodes, str_or_query_bundle=str_or_query_bundle)

    async def aretrieve(self, str_or_query_bundle: QueryType) -> List[NodeWithScore]:
        nodes = await self._retriever.aretrieve(str_or_query_bundle)
        return self._apply_node_postprocessors(nodes, str_or_query_bundle=str_or_query_bundle)

    def _run_engine(self, str_or_query_bundle: QueryType) -> List[NodeWithScore]:
        return self.retrieve(str_or_query_bundle)

    async def _arun_engine(self, str_or_query_bundle: QueryType) -> List[NodeWithScore]:
        return await self.aretrieve(str_or_query_bundle)

    @property
    def retriever(self) -> BaseRetriever:
        """Get the retriever object."""
        return self._retriever

    @property
    def node_postprocessors(self) -> List[BaseNodePostprocessor]:
        """Get the node postprocessors."""
        return self._node_postprocessors


from typing import Optional, List
from rag.retrievers.base import BaseRetriever
from rag.rerank.base import BaseNodePostprocessor
from rag.callbacks import CallbackManager
from rag.node.base_node import NodeWithScore
from rag.retrievers.types import QueryType
from rag.synthesizer.base_synthesizer import BaseSynthesizer
from rag.engine.retriever_engine import RetrieverEngine


class RetrieverQueryEngine:
    """
    Envoltura alrededor de RetrieverEngine que opcionalmente acepta un response_synthesizer
    pero de momento expone solo `.retrieve()`.
    """

    def __init__(
            self,
            retriever: BaseRetriever,
            response_synthesizer: Optional[BaseSynthesizer] = None,  # Se acepta pero no se usa aún
            node_postprocessors: Optional[List[BaseNodePostprocessor]] = None,
            callback_manager: Optional[CallbackManager] = None,
    ) -> None:
        self.engine = RetrieverEngine(
            retriever=retriever,
            node_postprocessors=node_postprocessors,
            callback_manager=callback_manager,
        )
        self.response_synthesizer = response_synthesizer

    def retrieve(self, query: QueryType) -> List[NodeWithScore]:
        return self.engine.retrieve(query)

    async def aretrieve(self, query: QueryType) -> List[NodeWithScore]:
        return await self.engine.aretrieve(query)

    # ✅ NUEVO: método requerido por SubQuestionQueryEngine
    def query(self, query: QueryType) -> RESPONSE_TYPE:
        nodes = self.retrieve(query)
        if self.response_synthesizer is None:
            raise ValueError("No se definió un response_synthesizer en RetrieverQueryEngine.")
        return self.response_synthesizer.synthesize(query, nodes=nodes)

    # ✅ NUEVO: método asíncrono opcional
    async def aquery(self, query: QueryType) -> RESPONSE_TYPE:
        nodes = await self.aretrieve(query)
        if self.response_synthesizer is None:
            raise ValueError("No se definió un response_synthesizer en RetrieverQueryEngine.")
        return await self.response_synthesizer.asynthesize(query, nodes=nodes)
