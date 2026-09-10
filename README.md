# ZoniaChatBot

Chatbot RAG sobre documentos institucionales, con voz y visión: recuperación
híbrida sobre **Milvus**, transcripción con **Whisper** (ASR), lectura de
imágenes con **EasyOCR** y respuesta hablada con **Piper** (TTS).

## Arquitectura

```
Angular 22 (workspace multi-proyecto)        FastAPI (Rag_Milvus/qa_docs)
├─ projects/user-chat   → :4202             ├─ web  :8000  RAG + WebSocket /ws/chat + TTS
└─ projects/admin-chat  → :4203             ├─ asr  :8001  Whisper
                                            └─ ocr  :8002  EasyOCR
                                                  ↓
   rag/            fork vendorizado de LlamaIndex (pipeline, retrievers,
                   rerank, synthesizer, vector_stores) — sin dependencia externa
   Milvus 3.0      base vectorial (Docker: + etcd + MinIO)
   SQLite (WAL)    sesiones, preguntas, respuestas, votos
```

## Requisitos

| Componente | Versión | Por qué esa |
|---|---|---|
| Python | **3.12** | `numpy`/`easyocr`/`scikit-image` aún no cubren bien 3.13 |
| Node.js | **≥ 24.15** | lo exigen los `engines` de Angular 22 |
| Docker Desktop | cualquiera | solo para Milvus + Attu |
| GPU (opcional) | CUDA 13.2 | probado en GTX 1650 (sm_75) |

## Puesta en marcha

### 1. Milvus + Attu (Docker)

```bash
docker compose -f docker-compose.milvus.yml up -d
```

Levanta Milvus 3.0 en `localhost:19530` junto a etcd y MinIO (Milvus standalone
**necesita** los tres), más la GUI **Attu** en <http://localhost:3000>.

### 2. Backend (Python)

```bash
python -m venv zoniaenv
zoniaenv\Scripts\activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python -m spacy download es_core_news_sm
pip install -e .
```

Y en tres terminales:

```bash
cd Rag_Milvus              && python main.py                # :8000
cd Rag_Milvus/qa_docs/asr  && python asr_whisper.py         # :8001
cd Rag_Milvus/qa_docs/ocr  && python ocr_easy.py            # :8002
```

### 3. Frontends (Angular)

```bash
npm install
npm run start:user     # http://localhost:4202
npm run start:admin    # http://localhost:4203
```

> **Los puertos 4202 y 4203 son obligatorios.** Son los únicos orígenes que
> el backend permite por CORS (`Rag_Milvus/qa_docs/__init__.py`). En el 4200
> por defecto, la interfaz carga pero *todas* las llamadas al backend fallan.

### Todo en Docker (alternativa)

```bash
docker compose -f docker-compose.milvus.yml -f docker-compose.yml up -d
```

Ambos archivos deben ir juntos para que compartan red. Si no tienes el runtime
NVIDIA configurado, elimina los bloques `deploy:` de `web`, `asr` y `ocr`.

## Configuración

- `Rag_Milvus/configuration/config_process.yaml` — splitter, embeddings,
  reranker, LLM, retriever. El host de Milvus se puede sobreescribir con la
  variable de entorno `MILVUS_HOST` (por defecto `localhost`).
- `models/` — modelos descargados de HuggingFace (~18 GB). No se copian a las
  imágenes Docker: van montados como volumen.

## Limitaciones conocidas

- **DeepFilterNet (reducción de ruido del ASR) está deshabilitado.**
  `deepfilterlib` solo publica wheels hasta cp311 y el proyecto corre en 3.12.
  El ASR funciona igual, sin esa etapa. Ver `qa_docs/asr/asr_whisper.py`.
- **`torchaudio` no existe para CUDA 13.2** (se quedó en la 2.11). Se sustituyó
  por `soundfile` + `scipy.signal.resample_poly`.
- El token de administrador está embebido en el bundle del frontend
  (`projects/*/src/environments/environment.ts`). No usar tal cual en producción.

## Carpetas

| Ruta | Qué es |
|---|---|
| `Rag_Milvus/qa_docs/` | aplicación FastAPI (views, routers, asr, ocr, tts, db) |
| `rag/` | motor RAG (fork de LlamaIndex, autocontenido) |
| `projects/` | los dos frontends Angular |
| `corpus_emb/` | PDFs del corpus |
| `legacy/` | scripts y carpetas anteriores a la migración, sin uso |
