# Atribución y licencias de terceros

ZONIA se distribuye bajo licencia [MIT](LICENSE), pero esa licencia cubre **únicamente el código
propio de este repositorio**. El proyecto incorpora, enlaza o empaqueta software, modelos
preentrenados y datos de terceros que conservan sus propias licencias.

Este documento existe para que cualquiera pueda saber **qué puede y qué no puede hacer** con el
proyecto completo antes de desplegarlo.

> **Verifica antes de desplegar.** Las licencias de los modelos alojados en Hugging Face cambian
> entre versiones y revisiones. Las indicadas aquí corresponden a las versiones usadas durante el
> desarrollo. Confirma la licencia vigente en la tarjeta de cada modelo antes de un uso comercial.

---

## ⚠️ Restricciones que debes conocer

Tres componentes imponen condiciones que **no son permisivas**. Si vas a hacer un despliegue
comercial o público, léelas primero.

### 1. `jina-reranker-v2-base-multilingual` — CC BY-NC 4.0 (no comercial)

Es el reranker por defecto del pipeline. Su licencia **prohíbe el uso comercial**. Para un
prototipo académico o de portafolio no hay problema; para un servicio comercial hay dos salidas:

- Contratar licencia comercial con [Jina AI](https://jina.ai/).
- Cambiar el reranker en `config_process.yaml` por una alternativa permisiva ya cableada:
  `BAAI/bge-reranker-v2-m3` (Apache-2.0) o `cross-encoder/ms-marco-MiniLM-L6-v2` (Apache-2.0,
  solo inglés).

El mismo aviso aplica a `jinaai/jina-embeddings-v3`, presente en `models/` y listado como
alternativa: también es CC BY-NC 4.0. El modelo de embeddings **actualmente en uso**
(`jina-embeddings-v2-base-es`) es Apache-2.0 y no tiene esa restricción.

### 2. `pymupdf` — AGPL-3.0

Está en `requirements.txt` como lector de PDF. La AGPL-3.0 es copyleft de red: si distribuyes la
obra combinada o la ofreces como servicio, la AGPL exige publicar el código fuente completo bajo
la misma licencia.

**Salida limpia:** el proyecto ya incluye `pypdf` (BSD-3-Clause) y `pdfminer.six` (MIT). Si tu caso
de uso no necesita PyMuPDF, retíralo de `requirements.txt` y el conflicto desaparece. La otra
opción es adquirir la licencia comercial de [Artifex](https://artifex.com/).

### 3. `espeak-ng` — GPL-3.0

Los datos y binarios de espeak-ng van empaquetados en `Rag_Milvus/piper/` porque Piper los usa para
la fonemización. Piper en sí es MIT, pero espeak-ng es GPL-3.0 y viaja dentro del repositorio.

---

## Motor RAG vendorizado

### LlamaIndex — MIT

El directorio **`rag/`** es un fork modificado de [LlamaIndex](https://github.com/run-llama/llama_index),
copiado al repositorio en lugar de instalarse desde PyPI. Incluye código derivado de sus módulos de
pipeline, retrievers, reranking, síntesis de respuestas, vector stores, node parsers y memoria.

```
Copyright (c) Jerry Liu and LlamaIndex contributors
Licensed under the MIT License.
https://github.com/run-llama/llama_index/blob/main/LICENSE
```

Las modificaciones sobre el código original son responsabilidad de los autores de ZONIA y no están
respaldadas por el proyecto LlamaIndex.

---

## Modelos de inteligencia artificial

| Modelo | Uso en ZONIA | Autor | Licencia |
|---|---|---|---|
| `jinaai/jina-embeddings-v2-base-es` | Embeddings (en uso) | Jina AI | Apache-2.0 |
| `jinaai/jina-reranker-v2-base-multilingual` | Reranker (en uso) | Jina AI | **CC BY-NC 4.0** ⚠️ |
| `jinaai/jina-embeddings-v3` | Alternativa disponible | Jina AI | **CC BY-NC 4.0** ⚠️ |
| `BAAI/bge-m3` | Alternativa de embeddings | BAAI | MIT |
| `BAAI/bge-reranker-v2-m3` | Alternativa de reranker | BAAI | Apache-2.0 |
| `cross-encoder/ms-marco-MiniLM-L6-v2` | Alternativa de reranker | UKP Lab / SBERT | Apache-2.0 |
| `openai/whisper-*` | ASR (base del modelo) | OpenAI | MIT |
| `whisper-small-es` (ajuste en español) | ASR (en uso) | Autores del fine-tune en Hugging Face | Revisar tarjeta del modelo |
| `openai/gpt-oss-20b` (vía Groq) | LLM generador | OpenAI | Apache-2.0 |
| `es-mx-laurav2` (voz Piper) | TTS | Proyecto Piper / Rhasspy | MIT |
| `es_core_news_sm` | Modelo lingüístico spaCy | Explosion AI | MIT |

**Modelos de referencia evaluados y descartados** (BERT, RoBERTa, MarianMT, Mistral, T5, Flan-T5):
no forman parte de la distribución. Se probaron durante la fase de selección; sus licencias
respectivas aplican solo si decides reintroducirlos.

---

## Servicios externos

| Servicio | Uso | Condiciones |
|---|---|---|
| [Groq](https://groq.com/) | Inferencia del LLM (endpoint compatible con la API de OpenAI) | Términos de servicio de Groq. Requiere `GROQ_API_KEY` |
| [OpenAI API](https://openai.com/) | Alternativa de LLM y embeddings (cableada, desactivada) | Términos de servicio de OpenAI |
| [Hugging Face Hub](https://huggingface.co/) | Descarga de modelos | Términos del Hub + licencia de cada modelo |

El proyecto **no envía datos a ningún servicio externo** salvo el prompt enriquecido al proveedor
de LLM configurado. Embeddings, reranking, ASR, OCR y TTS se ejecutan localmente.

---

## Dependencias de Python

Lista de los componentes principales. La relación completa con versiones exactas está en
[`requirements.txt`](requirements.txt).

| Paquete | Uso | Licencia |
|---|---|---|
| `fastapi`, `starlette` | Framework web y ASGI | MIT · BSD-3-Clause |
| `uvicorn` | Servidor ASGI | BSD-3-Clause |
| `pydantic` | Validación de esquemas | MIT |
| `torch`, `torchvision` | Runtime de deep learning | BSD-3-Clause |
| `transformers`, `tokenizers` | Carga de modelos e inferencia | Apache-2.0 |
| `sentence-transformers` | Embeddings y cross-encoders | Apache-2.0 |
| `accelerate`, `safetensors`, `huggingface_hub` | Utilidades de modelos | Apache-2.0 |
| `pymilvus` | Cliente de Milvus | Apache-2.0 |
| `sqlalchemy`, `aiosqlite` | ORM async y driver SQLite | MIT |
| `spacy`, `thinc`, `blis` | Procesamiento de lenguaje natural | MIT · BSD-3-Clause |
| `nltk` | Utilidades de NLP | Apache-2.0 |
| `rank-bm25` | Retriever léxico BM25 | Apache-2.0 |
| `tiktoken` | Tokenizador `cl100k_base` | MIT |
| `easyocr` | Reconocimiento óptico de caracteres | Apache-2.0 |
| `opencv-python-headless` | Preprocesamiento de imagen | Apache-2.0 |
| `scikit-image`, `scikit-learn`, `scipy`, `numpy` | Cómputo científico | BSD-3-Clause |
| `pillow` | Manipulación de imágenes | MIT-CMU |
| `soundfile` | E/S de audio (sustituye a `torchaudio`) | BSD-3-Clause |
| `pydub` | Manipulación de audio | MIT |
| `pypdf` | Lectura de PDF | BSD-3-Clause |
| `pdfminer.six` | Extracción de texto de PDF | MIT |
| **`pymupdf`** | Lectura de PDF | **AGPL-3.0** ⚠️ |
| `docx2txt` | Extracción de texto de DOCX | MIT |
| `omegaconf` | Configuración YAML jerárquica | BSD-3-Clause |
| `python-dotenv` | Carga de variables de entorno | BSD-3-Clause |
| `openai` | Cliente HTTP para endpoints compatibles | Apache-2.0 |
| `pandas` | Análisis de datos | BSD-3-Clause |

---

## Dependencias de JavaScript / TypeScript

Relación completa con versiones exactas en [`package.json`](package.json).

| Paquete | Uso | Licencia |
|---|---|---|
| `@angular/*` | Framework del frontend | MIT |
| `rxjs` | Programación reactiva | Apache-2.0 |
| `zone.js` | Detección de cambios de Angular | MIT |
| `express` | Servidor SSR | MIT |
| `quill`, `ngx-quill` | Editor de texto enriquecido | BSD-3-Clause · MIT |
| `recordrtc` | Grabación de audio en el navegador | MIT |
| `moment` | Manejo de fechas | MIT |
| `@fortawesome/fontawesome-free` | Iconografía | Iconos: CC BY 4.0 · Fuentes: SIL OFL 1.1 · Código: MIT |
| `typescript` | Lenguaje y compilador | Apache-2.0 |
| `karma`, `jasmine` | Testing | MIT |

---

## Infraestructura y binarios empaquetados

| Componente | Uso | Licencia |
|---|---|---|
| [Milvus](https://milvus.io/) | Base de datos vectorial | Apache-2.0 |
| [Attu](https://github.com/zilliztech/attu) | GUI de Milvus | Apache-2.0 |
| [etcd](https://etcd.io/) | Metadatos de Milvus | Apache-2.0 |
| [MinIO](https://min.io/) | Almacenamiento de objetos de Milvus | AGPL-3.0 (imagen upstream) |
| [Docker](https://www.docker.com/) | Contenerización | Apache-2.0 |
| [SQLite](https://sqlite.org/) | Base de datos relacional | Dominio público |
| [PDF.js](https://mozilla.github.io/pdf.js/) — `Rag_Milvus/static/pdfjs/` | Visor de PDF embebido | Apache-2.0 |
| [Piper](https://github.com/rhasspy/piper) — `Rag_Milvus/piper/` | Motor TTS | MIT |
| [espeak-ng](https://github.com/espeak-ng/espeak-ng) — `Rag_Milvus/piper/espeak-ng-data/` | Fonemización para Piper | **GPL-3.0** ⚠️ |
| [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | Reducción de ruido (deshabilitado) | MIT / Apache-2.0 |

---

## Corpus documental

Los PDFs de `corpus_emb/` (estatuto estudiantil de pregrado y posgrado) **no están versionados en
este repositorio** ni forman parte de la distribución. Son documentos normativos institucionales
cuya propiedad corresponde a la entidad que los emite. Se usaron con fines académicos y de
investigación.

Quien reutilice este proyecto debe aportar su propio corpus y respetar los derechos que lo
amparen.

---

## Cómo reportar un problema de atribución

Si detectas una licencia mal declarada, una atribución faltante o un componente cuyo uso aquí no
cumple sus términos, abre un issue en
<https://github.com/Farid13-dev/ZoniaChatBot/issues> y se corrige.

---

*Última revisión: septiembre de 2026.*
