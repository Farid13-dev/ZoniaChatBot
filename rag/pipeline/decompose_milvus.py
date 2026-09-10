import logging
import time
from typing import Optional, List

from transformers import AutoTokenizer

from rag.config.schema import (
    SplitterConfig,
    MilvusConfig,
    EmbeddingConfig,
    LlmConfig,
    IndexRetrieverConfig,
    ResponseConfig,
    QuestionGenConfig

)
from rag.core.service_context import ServiceContext
from rag.core.storage_context import StorageContext
from rag.callbacks import CallbackManager
from rag.node_parser.text.sentence import SentenceSplitter
from rag.embeddings.huggingface import HuggingFaceEmbedding
from rag.core.prompt_helper import PromptHelper
from rag.question_gen import question_generator

from rag.retrievers.dense import VectorIndexRetriever
from rag.retrievers.types import QueryBundle
from rag.indices.vector_store import VectorStoreIndex
from rag.engine.retriever_engine import RetrieverQueryEngine
from rag.tools import QueryEngineTool
from rag.vector_stores.milvus import MilvusVectorStore
from rag.engine.subquestion_engine import SubQuestionQueryEngine
from rag.question_gen.question_generator import LLMQuestionGenerator
from rag.synthesizer.utils import get_response_synthesizer
from rag.question_gen.prompt_gen import DEFAULT_SUB_QUESTION_PROMPT_TMPL, DEFAULT_CONTEXTUAL_SUBQUESTION_PROMPT_TMPL
from rag.question_gen.contextual_generator import ContextualQuestionGenerator  # o como lo llames

logger = logging.getLogger(__name__)


class MilvusSubquetionPipeline:
    def __init__(
            self,
            splitter_config: SplitterConfig,
            milvus_config: MilvusConfig,
            index_retriver_config: IndexRetrieverConfig,
            embed_config: EmbeddingConfig,
            llm_config: LlmConfig,
            response_config: ResponseConfig,
            qgen_config: QuestionGenConfig
    ) -> None:
        self.splitter_config = splitter_config
        self.milvus_config = milvus_config
        self.index_retriver_config = index_retriver_config
        self.response_config = response_config
        self.llm_config = llm_config
        self.qgen_config = qgen_config
        # callback manager
        callback_manager = CallbackManager()

        # node parser
        tokenizer = AutoTokenizer.from_pretrained(self.splitter_config.model_name_tokenizer)
        node_parser = SentenceSplitter(
            separator=self.splitter_config.separator,
            chunk_size=self.splitter_config.chunk_size,
            chunk_overlap=self.splitter_config.chunk_overlap,
            tokenizer=tokenizer.encode,
            paragraph_separator=self.splitter_config.paragraph_separator,
            secondary_chunking_regex=self.splitter_config.secondary_chunking_regex,
            callback_manager=callback_manager,
        )

        # embed model
        self.embed_model = self.get_embed_mode(embed_config)

        # prompt helper - tong hop 3 cai params cua llm, emb, node parser
        prompt_helper = PromptHelper()

        self.service_context = ServiceContext(
            llm=self.llm_config,
            prompt_helper=prompt_helper,
            embed_model=self.embed_model,
            node_parser=node_parser,
            callback_manager=callback_manager,
        )

    def run(self, query, documents):
        """Wrap time"""
        start_build_collection_index = int(round(time.time() * 1000))

        # TODO: build milvus vector from documents
        milvus_vector_store = MilvusVectorStore(
            dim=self.embed_model.get_model_dim(),
            host=self.milvus_config.host,
            port=self.milvus_config.port,
            uri=self.milvus_config.uri,
            address=self.milvus_config.address,
            user=self.milvus_config.user,
            collection_name=self.milvus_config.collection_name,
            embedding_field=self.milvus_config.embedding_field,
            doc_id_field=self.milvus_config.primary_field,
            text_field=self.milvus_config.text_field,
            consistency_level=self.milvus_config.consistency_level,
            overwrite=self.milvus_config.overwrite,
            index_params=self.milvus_config.index_params,
            search_params=self.milvus_config.search_params,
        )

        # construct index and customize storage context
        storage_context = StorageContext.from_defaults(
            vector_store=milvus_vector_store
        )

        # build nodes
        nodes = []
        for each_parser in self.service_context.transformations:
            parsing_nodes = each_parser.get_nodes_from_documents(
                documents=documents,
                show_progress=True,
            )
            nodes.extend(parsing_nodes)

        # build index
        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            service_context=self.service_context,
            store_nodes_override=self.index_retriver_config.store_nodes_override,
            insert_batch_size=self.index_retriver_config.insert_batch_size,
            use_async=self.index_retriver_config.use_async,
            show_progress=self.index_retriver_config.show_progress,
        )

        end_build_collection_index = int(round(time.time() * 1000))
        print(f"Time for build collection and index: {end_build_collection_index - start_build_collection_index} ms")

        # TODO: build retriever
        retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=self.index_retriver_config.similarity_top_k,
            sparse_top_k=self.index_retriver_config.sparse_top_k,
            alpha=self.index_retriver_config.alpha,
            vector_store_query_mode=self.index_retriver_config.vector_store_query_mode,
        )
        response_synthesizer = get_response_synthesizer(
            service_context=self.service_context,
            callback_manager=self.service_context.callback_manager,
            response_mode=self.response_config.response_mode,
            verbose=self.response_config.verbose,
            use_async=self.response_config.use_async,
            streaming=self.response_config.streaming,
        )

        # TODO: assemble query engine
        query_engine = RetrieverQueryEngine(
            retriever=retriever,
            response_synthesizer=response_synthesizer,
        )
        tool = QueryEngineTool.from_defaults(
            query_engine=query_engine,
            name="default",
            description="Default tool for retrieval"
        )

        # TODO: call question generator from default
        question_generator = ContextualQuestionGenerator.from_defaults(
            service_context=self.service_context,
            prompt_template_str=DEFAULT_CONTEXTUAL_SUBQUESTION_PROMPT_TMPL
        )

        # TODO: response synthesizer
        response_synthesizer = get_response_synthesizer(
            service_context=self.service_context,
            callback_manager=self.service_context.callback_manager,
            response_mode=self.response_config.response_mode,
            verbose=self.response_config.verbose,
            use_async=self.response_config.use_async,
            streaming=self.response_config.streaming,
        )

        # TODO: call subquestion or from defaults
        subquestion = SubQuestionQueryEngine(
            question_gen=question_generator,
            response_synthesizer=response_synthesizer,
            query_engine_tools=[tool],
            max_subquestions=self.qgen_config.max_subquestions,
            use_async=self.response_config.use_async,
        )

        # TODO: get response
        response = subquestion.query(QueryBundle(query))

        return response

    def get_embed_mode(self, config: EmbeddingConfig) -> HuggingFaceEmbedding:
        # emb_model
        emb_model = HuggingFaceEmbedding(
            model_name=config.model_name,
            tokenizer_name=config.tokenizer_name,
            pooling=config.pooling,
            max_length=config.max_length,
            normalize=config.normalize,
            embed_batch_size=config.embedding_batch_size,
            cache_folder=config.cache_folder,
            trust_remote_code=config.trust_remote_code,
        )
        return emb_model
