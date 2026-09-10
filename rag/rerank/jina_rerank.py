import os
from typing import List, Optional, Any
from rag.bridge.pydantic import Field, PrivateAttr
from rag.callbacks import CBEventType, EventPayload
from rag.node.base_node import NodeWithScore
from rag.retrievers.types import QueryBundle
from rag.rerank.base import BaseNodePostprocessor


class JinaRerank(BaseNodePostprocessor):
    model_name: str = Field(description="Jina model name.")
    top_n: int = Field(default=3)
    tokenizer_name: Optional[str] = Field(default=None)
    device: str = Field(default="cpu")
    max_length: int = Field(default=512)
    stride: int = Field(default=256)
    batch_size: int = Field(default=8)
    sliding_window: bool = Field(default=True)  # ✅ Nuevo parámetro
    score_aggregation: str = Field(default="mean")
    _tokenizer: Any = PrivateAttr()
    _model: Any = PrivateAttr()

    def __init__(
            self,
            model_name: str = "jinaai/jina-reranker-v2-base-en",
            top_n: int = 3,
            tokenizer_name: Optional[str] = None,
            device: str = "cpu",
            max_length: int = 512,
            stride: int = 256,
            batch_size: int = 8,
            sliding_window: bool = True,
            score_aggregation: str = "mean",
            **kwargs
    ):
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError:
            raise ImportError("Please install transformers and torch: `pip install transformers torch`")

        super().__init__(
            model_name=model_name,
            top_n=top_n,
            tokenizer_name=tokenizer_name,
            device=device,
            max_length=max_length,
            stride=stride,
            batch_size=batch_size,
            sliding_window=sliding_window,
            score_aggregation=score_aggregation,
            **kwargs
        )

        self._tokenizer = AutoTokenizer.from_pretrained(tokenizer_name or model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model_name, trust_remote_code=True
        ).to(device)

    @classmethod
    def class_name(cls) -> str:
        return "JinaRerank"

    def _sliding_window_split(self, text: str) -> List[str]:
        tokens = self._tokenizer.encode(text, truncation=False)
        chunks = []
        for i in range(0, len(tokens), self.stride):
            window = tokens[i:i + self.max_length]
            if not window:
                break
            chunks.append(self._tokenizer.decode(window, skip_special_tokens=True))
            if i + self.max_length >= len(tokens):
                break
        return chunks

    def _postprocess_nodes(
            self,
            nodes: List[NodeWithScore],
            query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        if query_bundle is None:
            raise ValueError("Missing query bundle.")
        if len(nodes) == 0:
            return []

        from transformers import pipeline

        with self.callback_manager.event(
                CBEventType.RERANKING,
                payload={
                    EventPayload.NODES: nodes,
                    EventPayload.MODEL_NAME: self.model_name,
                    EventPayload.QUERY_STR: query_bundle.query_str,
                },
        ) as event:
            pipe = pipeline(
                "text-classification",
                model=self._model,
                tokenizer=self._tokenizer,
                device=0 if self.device == "cuda" else -1,
            )

            final_results = []

            for idx, node in enumerate(nodes):
                content = node.node.get_content()

                # ✅ Sliding window opcional
                if self.sliding_window:
                    text_chunks = self._sliding_window_split(content)
                    # print(f"🧩 Nodo {idx} dividido en {len(text_chunks)} chunks (stride={self.stride})")
                else:
                    # print(f"⚠️ Nodo {idx} → sliding_window desactivado. Truncando a {self.max_length} tokens.")
                    text_chunks = [content]

                inputs = [{"text": query_bundle.query_str, "text_pair": chunk} for chunk in text_chunks]
                results = pipe(inputs, truncation=True, max_length=self.max_length, batch_size=self.batch_size)
                chunk_scores = [res["score"] for res in results]

                # best_score = max(chunk_scores) if chunk_scores else 0.0
                if chunk_scores:
                    if self.score_aggregation == "mean":
                        best_score = sum(chunk_scores) / len(chunk_scores)
                    else:
                        best_score = max(chunk_scores)
                else:
                    best_score = 0.0

                final_results.append(NodeWithScore(node=node.node, score=best_score))

            reranked_nodes = sorted(final_results, key=lambda x: x.score, reverse=True)[:self.top_n]

            event.on_end(payload={EventPayload.NODES: reranked_nodes})

        return reranked_nodes
