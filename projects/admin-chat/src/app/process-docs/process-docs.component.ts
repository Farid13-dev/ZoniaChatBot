import {Component, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {HttpClient} from '@angular/common/http';
import {SourceService} from '../services/source.service';

@Component({
    selector: 'app-process-docs',
    imports: [CommonModule, FormsModule],
    templateUrl: './process-docs.component.html',
    changeDetection: ChangeDetectionStrategy.Eager,
    styleUrls: ['./process-docs.component.css']
})
export class ProcessDocsComponent implements OnInit {
  // 📂 Documentos en SQLite
  sqliteDocuments: { id: number, categoria: string }[] = [];
  selectedSqliteDocument: string = "";
  loadingDocuments: boolean = false;

  // 📄 Processing
  document_id: number = 1;

  // ✂️ Splitter
  splitterAvailableModes: string[] = [];
  splitterAvailableTokenizers: string[] = [];
  selectedSplitterMode: string = 'sentence';
  selectedSplitterTokenizer: string = 'sentence-transformers/all-MiniLM-L6-v2';
  chunkSize: number = 3080;
  chunkOverlap: number = 50;
  includeMetadata: boolean = true;
  includePrevNextRel: boolean = true;
  separator: string = " ";
  backupSeparators: string[] = ["\n", "\n\n"];
  paragraphSeparator: string = "\n\n";
  secondaryChunkingRegex: string = "[.!?](?!\\d)";
  windowSize: number = 3;
  chunkSizes: number[] = [2048, 1024, 512];

  // 🧠 Embeddings
  embeddingAvailableModels: { [provider: string]: string[] } = {};
  selectedEmbeddingProvider: string = "openai";
  embeddingApiKey: string = "";
  embeddingModelPath: string = "text-embedding-ada-002";
  embeddingTokenizerPath: string = "text-embedding-ada-002";
  pooling: string = "cls";
  maxLength: number = 512;
  stride: number = 256;
  slidingWindow: boolean = true;
  normalize: boolean = true;
  embeddingBatchSize: number = 32;
  embeddingDevice: string = "cuda";
  cacheFolder: string = "";
  trustRemoteCode: boolean = false;
  useAsyncEmbedding: boolean = false;
  showProgressEmbedding: boolean = false;

  // 📊 Reranking
  rerankingAvailableModels: { [provider: string]: string[] } = {};
  selectedRerankingProvider: string = "local";
  rerankingModelPath: string = "../models/mixedbread-ai/mxbai-rerank-base-v2";
  rerankingTokenizerPath: string = "../models/mixedbread-ai/mxbai-rerank-base-v2";
  rerankingDevice: string = "cuda";
  topN: number = 2;
  rerankingMaxLength: number = 1024;
  rerankingStride: number = 256;
  rerankingSlidingWindow: boolean = true;
  scoreAggregation: string = "max";
  rerankingBatchSize: number = 8;
  rerankingToken: string = "10";
  rerankingTrustRemoteCode: boolean = true;

  // Mostrar configuraciones avanzadas
  showSplitterAdvanced: boolean = false;
  showEmbeddingAdvanced: boolean = false;
  showRerankingAdvanced: boolean = false;

  // 🧩 Campos para retriever
  retrieverMode: string = "bm25";
  hybridMode: string = "or";
  similarityTopK: number = 10;
  sparseTopK: number = 10;
  alpha: number | null = null;
  useAsyncRetriever: boolean = false;
  showProgressRetriever: boolean = false;
  listQueryMode: string = "default";
  choiceBatchSize: number = 10;
  vectorStoreQueryMode: string = "default";


  constructor(private http: HttpClient, private sourceService: SourceService) {
  }

  ngOnInit() {
    this.loadSqliteDocuments();
    this.loadConfig();
    this.loadModelOptions();
  }

  parseJsonSafe(jsonStr: string): any {
    try {
      return JSON.parse(jsonStr);
    } catch {
      return {};
    }
  }

  loadSqliteDocuments() {
    this.loadingDocuments = true;
    this.http.get<{ id: number, categoria: string }[]>('http://127.0.0.1:8000/list_sqlite_documents')
      .subscribe({
        next: (response) => {
          this.sqliteDocuments = response;
          this.loadingDocuments = false;
        },
        error: (error) => {
          console.error("Error al cargar documentos desde SQLite:", error);
          this.sqliteDocuments = [];
          this.loadingDocuments = false;
        }
      });
  }

  onDocumentSelect() {
    if (!this.selectedSqliteDocument) return;

    const documentId = Number(this.selectedSqliteDocument);
    this.http.post<{ message: string }>(`http://127.0.0.1:8000/select_sqlite_document/${documentId}`, {})
      .subscribe({
        next: (response) => {
          alert(`✅ Documento seleccionado: ${documentId}`);
        },
        error: (error) => {
          console.error("❌ Error en la API:", error);
        }
      });
  }

  saveConfig() {
    const errors: string[] = [];

    // 🔎 Validación de selección de documento
    if (!this.selectedSqliteDocument) {
      errors.push("⚠️ Debes seleccionar un documento.");
    }

    // 🔎 Validación de Splitter
    if (!this.selectedSplitterTokenizer) {
      errors.push("⚠️ Debes seleccionar un tokenizer para el splitter.");
    }
    if (this.chunkSize <= 0) {
      errors.push("⚠️ Chunk size debe ser mayor a 0.");
    }
    if (this.chunkOverlap < 0) {
      errors.push("⚠️ Chunk overlap no puede ser negativo.");
    }

    // 🔎 Validación de Embedding
    if (!this.embeddingModelPath) {
      errors.push("⚠️ Debes ingresar un modelo de embedding.");
    }
    if (this.embeddingBatchSize <= 0) {
      errors.push("⚠️ El batch size para embedding debe ser mayor a 0.");
    }

    // 🔎 Validación de Reranking
    if (!this.rerankingModelPath) {
      errors.push("⚠️ Debes ingresar un modelo para reranking.");
    }
    if (this.topN <= 0) {
      errors.push("⚠️ topN para reranking debe ser mayor a 0.");
    }

    // 🔎 Validación de Retriever
    if (this.similarityTopK <= 0 || this.sparseTopK <= 0) {
      errors.push("⚠️ Top-K debe ser mayor a 0 en Retriever.");
    }

    if (errors.length > 0) {
      alert("❌ Errores en la configuración:\n\n" + errors.join("\n"));
      return;
    }
    const splitterConfig = {
      splitter_mode: this.selectedSplitterMode,
      model_name_tokenizer: this.selectedSplitterTokenizer,
      chunk_size: this.chunkSize,
      chunk_overlap: this.chunkOverlap,
      include_metadata: this.includeMetadata,
      include_prev_next_rel: this.includePrevNextRel,
      separator: this.separator,
      backup_separators: this.backupSeparators,
      paragraph_separator: this.paragraphSeparator,
      secondary_chunking_regex: this.secondaryChunkingRegex,
      window_size: this.windowSize,
      chunk_sizes: this.chunkSizes
    };
    this.http.patch('http://127.0.0.1:8000/save_splitter_config', splitterConfig).subscribe();

    const embeddingConfig = {
      provider: this.selectedEmbeddingProvider,
      model_name: this.embeddingModelPath,
      tokenizer_name: this.embeddingModelPath,
      api_key: this.embeddingApiKey,
      pooling: this.pooling,
      max_length: this.maxLength,
      normalize: this.normalize,
      embedding_batch_size: this.embeddingBatchSize,
      device: this.embeddingDevice,
      cache_folder: this.cacheFolder,
      trust_remote_code: this.trustRemoteCode,
      use_async: this.useAsyncEmbedding,
      show_progress: this.showProgressEmbedding
    };
    this.http.patch('http://127.0.0.1:8000/save_embedding_config', embeddingConfig).subscribe();

    const rerankingConfig = {
      provider: this.selectedRerankingProvider,
      model_name: this.rerankingModelPath,
      tokenizer_name: this.rerankingModelPath,
      device: this.rerankingDevice,
      top_n: this.topN,
      max_length: this.rerankingMaxLength,
      batch_size: this.rerankingBatchSize,
      token: this.rerankingToken,
      trust_remote_code: this.rerankingTrustRemoteCode,
    };
    this.http.patch('http://127.0.0.1:8000/save_reranking_config', rerankingConfig).subscribe();
// 🔥 Guardar configuración de Retriever
    const retrieverConfig = {
      retriever_mode: this.retrieverMode,
      hybrid_mode: this.hybridMode,
      similarity_top_k: this.similarityTopK,
      use_async: this.useAsyncRetriever,
      show_progress: this.showProgressRetriever,
      vector_store_query_mode: this.vectorStoreQueryMode,
      sparse_top_k: this.sparseTopK,
      alpha: this.alpha,
      list_query_mode: this.listQueryMode,
      choice_batch_size: this.choiceBatchSize,
    };

    this.http.patch('http://127.0.0.1:8000/save_retriever_config', retrieverConfig).subscribe();


    alert("✅ Configuración guardada correctamente.");
  }

  loadConfig() {
    this.http.get<any>('http://127.0.0.1:8000/get_config')
      .subscribe({
        next: (response) => {
          console.log("📋 Configuración cargada:", response);

          if (response.processing) {
            this.document_id = response.processing.document_id || 1;
            this.selectedSqliteDocument = String(this.document_id); // 👈 CORRECTO
          }


          if (response.splitter?.selected) {
            const s = response.splitter.selected;
            this.selectedSplitterMode = s.splitter_mode;
            this.selectedSplitterTokenizer = s.model_name_tokenizer;
            this.chunkSize = s.chunk_size;
            this.chunkOverlap = s.chunk_overlap;
            this.separator = s.separator || " ";
            this.backupSeparators = s.backup_separators || ["\n", "\n\n"];
            this.paragraphSeparator = s.paragraph_separator;
            this.secondaryChunkingRegex = s.secondary_chunking_regex;
            this.windowSize = s.window_size;
            this.chunkSizes = s.chunk_sizes || [2048, 1024, 512];
          }

          if (response.embedding?.selected) {
            const e = response.embedding.selected;
            this.selectedEmbeddingProvider = response.embedding.provider;
            this.embeddingModelPath = e.model_name;
            this.embeddingTokenizerPath = e.tokenizer_name;
            this.embeddingApiKey = e.api_key;
            this.pooling = e.pooling;
            this.maxLength = e.max_length;
            this.stride = e.stride;
            this.slidingWindow = e.sliding_window;
            this.normalize = e.normalize;
            this.embeddingBatchSize = e.embedding_batch_size;
            this.embeddingDevice = e.device;
            this.cacheFolder = e.cache_folder;
            this.trustRemoteCode = e.trust_remote_code;
            this.useAsyncEmbedding = e.use_async;
            this.showProgressEmbedding = e.show_progress;
          }

          if (response.rerank?.selected) {
            const r = response.rerank.selected;
            this.selectedRerankingProvider = response.rerank.provider;
            this.rerankingModelPath = r.model_name;
            this.rerankingTokenizerPath = r.tokenizer_name;
            this.rerankingDevice = r.device;
            this.topN = r.top_n;
            this.rerankingMaxLength = r.max_length;
            this.rerankingStride = r.stride;
            this.rerankingSlidingWindow = r.sliding_window;
            this.scoreAggregation = r.score_aggregation;
            this.rerankingBatchSize = r.batch_size;
          }
          if (response.retriever) {
            const r = response.retriever;
            this.retrieverMode = r.retriever_mode || "bm25";
            this.hybridMode = r.hybrid_mode || "or";
            this.similarityTopK = r.similarity_top_k ?? 10;
            this.useAsyncRetriever = r.use_async ?? false;
            this.showProgressRetriever = r.show_progress ?? false;
            this.vectorStoreQueryMode = r.vector_store_query_mode || "default";
            this.sparseTopK = r.sparse_top_k ?? 10;
            this.alpha = r.alpha ?? null;
            this.listQueryMode = r.list_query_mode || "default";
            this.choiceBatchSize = r.choice_batch_size ?? 10;
          }

        },
        error: (error) => {
          console.error("❌ Error al cargar configuración:", error);
        }
      });
  }


  loadModelOptions() {
    // Splitter disponibles
    this.http.get<any>('http://127.0.0.1:8000/splitter/available').subscribe(splitterAvailable => {
      this.splitterAvailableModes = splitterAvailable.splitter_mode || [];
      this.splitterAvailableTokenizers = splitterAvailable.model_name_tokenizer || [];
    });

    // Embedding disponibles
    this.http.get<any>('http://127.0.0.1:8000/embedding/available').subscribe(models => {
      this.embeddingAvailableModels = models;
    });

    // Reranking disponibles
    this.http.get<any>('http://127.0.0.1:8000/rerank/available').subscribe(models => {
      this.rerankingAvailableModels = models;
    });

    // Modelo splitter seleccionado
    this.http.get<any>('http://127.0.0.1:8000/splitter/selected').subscribe(selected => {
      this.selectedSplitterMode = selected.splitter_mode || '';
    });

    // Modelo embedding seleccionado
    this.http.get<any>('http://127.0.0.1:8000/embedding/selected').subscribe(selected => {
      this.embeddingModelPath = selected.model_name || '';
    });

    // Modelo reranking seleccionado
    this.http.get<any>('http://127.0.0.1:8000/rerank/selected').subscribe(selected => {
      this.rerankingModelPath = selected.model_name || '';
    });
  }

  onProviderChange() {
    this.http.get<any>('http://127.0.0.1:8000/embedding/selected').subscribe(selected => {
      this.embeddingModelPath = selected.model_path || '';
    });
  }

  onRerankingProviderChange() {
    this.http.get<any>('http://127.0.0.1:8000/rerank/selected').subscribe(selected => {
      this.rerankingModelPath = selected.model_path || '';
    });
  }

  get embeddingProviders(): string[] {
    return Object.keys(this.embeddingAvailableModels);
  }

  get rerankingProviders(): string[] {
    return Object.keys(this.rerankingAvailableModels);
  }
}
