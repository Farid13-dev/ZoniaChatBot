# rag/engine/base_query_engine.py

from abc import ABC, abstractmethod
from rag.retrievers.types import QueryType
from rag.node.base_node import NodeWithScore
from rag.callbacks.callback_manager import CallbackManager

class BaseQueryEngine(ABC):
    """Base class for all query engines."""

    def __init__(self, callback_manager: CallbackManager = None) -> None:
        self.callback_manager = callback_manager or CallbackManager()

    @abstractmethod
    def query(self, query: QueryType) -> str:
        pass

    async def aquery(self, query: QueryType) -> str:
        raise NotImplementedError("Asynchronous querying not implemented.")
