import {Component, OnInit, ChangeDetectionStrategy} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {HttpClient} from '@angular/common/http';

@Component({
    selector: 'app-initialize-qa',
    imports: [CommonModule, FormsModule],
    templateUrl: './initialize-qa.component.html',
    changeDetection: ChangeDetectionStrategy.Eager,
    styleUrls: ['./initialize-qa.component.css']
})
export class InitializeQaComponent implements OnInit {
  selectedLLM: string = 'openai';
  modelPath: string = '';
  apiKey: string = '';
  contextWindow: number = 3900;
  maxTokens: number = 512;
  topP: number = 0.9;
  topK: number = 10;
  temperature: number = 0.7;
  numBeams: number = 3;
  doSample: boolean | null = true;
  useCache: boolean = true;
  deviceMap: string | null = null;
  torchType: string = 'float32';
  device: string = 'cuda';

  llmAvailableModels: { [provider: string]: string[] } = {};

  procesando: boolean = false;
  guardando: boolean = false;
  configGuardada: boolean = false;


  constructor(private http: HttpClient) {
  }

  ngOnInit() {
    this.loadLLMAvailableModels();
    this.loadLLMSelected();
    this.loadConfig();
  }

  get llmProviders(): string[] {
    return Object.keys(this.llmAvailableModels);
  }

  onLLMChange() {
    this.loadLLMSelected();
  }

  loadLLMAvailableModels() {
    this.http.get<any>('http://127.0.0.1:8000/llm/available').subscribe(
      res => this.llmAvailableModels = res,
      err => console.error("❌ Error al cargar modelos disponibles:", err)
    );
  }

  loadLLMSelected() {
    this.http.get<any>('http://127.0.0.1:8000/llm/selected').subscribe(
      res => {
        this.apiKey = res.api_key || '';
        this.modelPath = res.model_name || '';
        this.modelPath = res.tokenizer_name || '';
        this.temperature = res.temperature ?? 0.7;
        this.maxTokens = res.max_new_tokens ?? 512;
        this.topP = res.top_p ?? 1.0;
        this.topK = res.top_k ?? 10;
        this.numBeams = res.num_beams ?? 3;
        this.doSample = res.do_sample ?? null;
        this.useCache = res.use_cache ?? true;
        this.deviceMap = res.device_map ?? null;
        this.torchType = res.torch_dtype ?? 'float32';
        this.device = res.device || 'cuda';
      },
      err => console.error("❌ Error al cargar configuración del LLM:", err)
    );
  }

  saveLLMConfig() {
    const errors = [];

    if (!this.modelPath.trim()) {
      errors.push("📁 La ruta del modelo es obligatoria.");
    }

    if (this.selectedLLM !== "local" && !this.apiKey.trim()) {
      errors.push("🔑 La API Key es obligatoria.");
    }

    if (errors.length > 0) {
      alert("❌ Errores en la configuración:\n" + errors.join("\n"));
      return;
    }

    this.guardando = true;

    const config = {
      provider: this.selectedLLM,
      model_name: this.modelPath,
      tokenizer_name: this.modelPath,
      api_key: this.selectedLLM !== 'local' ? this.apiKey : null,
      context_window: this.contextWindow,
      max_tokens: this.maxTokens,
      temperature: this.temperature,
      top_p: this.topP,
      top_k: this.topK,
      num_beams: this.numBeams,
      do_sample: this.doSample,
      use_cache: this.useCache,
      device_map: this.deviceMap,
      torch_dtype: this.torchType,
      device: this.device
    };

    this.http.patch('http://127.0.0.1:8000/save_llm_config', config).subscribe({
      next: () => {
        alert("✅ Configuración del LLM guardada correctamente.");
        this.configGuardada = true;
        this.guardando = false;
      },
      error: (err) => {
        console.error("❌ Error al guardar configuración:", err);
        alert("❌ No se pudo guardar la configuración.");
        this.guardando = false;
      }
    });
  }


  loadConfig() {
    this.http.get<any>('http://127.0.0.1:8000/get_config')
      .subscribe(response => {
        console.log("📋 Configuración cargada:", response);

        if (response.llm) {
          this.llmAvailableModels = response.llm.available || {};

          const provider = response.llm.provider || Object.keys(this.llmAvailableModels)[0];
          this.selectedLLM = provider;

          const selected = response.llm.selected || {};
          this.modelPath = selected.model_name || '';
          this.modelPath = selected.tokenizer_name || '';
          this.apiKey = selected.api_key || '';
          this.contextWindow = selected.context_window ?? 3900;
          this.maxTokens = selected.max_new_tokens ?? 512;
          this.temperature = selected.temperature ?? 0.7;
          this.topP = selected.top_p ?? 0.9;
          this.topK = selected.top_k ?? 10;
          this.numBeams = selected.num_beams ?? 3;
          this.doSample = selected.do_sample ?? null;
          this.useCache = selected.use_cache ?? true;
          this.deviceMap = selected.device_map ?? null;
          this.torchType = selected.torch_dtype ?? 'float32';
          this.device = selected.device || 'cuda';
        }

      }, error => {
        console.error("❌ Error al cargar configuración:", error);
      });
  }

  processDocument() {
    if (!this.configGuardada) {
      alert("⚠️ Debes guardar la configuración del LLM antes de procesar.");
      return;
    }

    this.procesando = true;

    this.http.post('http://127.0.0.1:8000/llm/process_document', {}).subscribe({
      next: (res: any) => {
        this.procesando = false;
        if (res.status === 'warning') {
          alert("⚠️ Documento ya procesado en Milvus.\n" + (res.message || ""));
        } else {
          alert("✅ Documento procesado exitosamente.\n" + (res.message || ""));
        }
      },
      error: (err) => {
        this.procesando = false;
        console.error("❌ Error al procesar documento:", err);
        alert("❌ Falló el procesamiento del documento.");
      }
    });
  }

}
