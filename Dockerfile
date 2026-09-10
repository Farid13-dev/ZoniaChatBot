# ZoniaChatBot - backend Python (RAG + ASR + OCR + TTS)
#
# Python 3.12: es el techo real del proyecto.
#   - numpy/easyocr/scikit-image aun no cubren bien 3.13
#   - deepfilterlib se quedo en cp311, asi que el denoiser del ASR
#     queda deshabilitado por codigo (ver qa_docs/asr/asr_whisper.py)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias del sistema:
#   libgl1 + libglib2.0-0 -> opencv (easyocr)
#   ffmpeg                -> pydub / audio
#   libsndfile1           -> soundfile
#   curl                  -> healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ffmpeg \
      libgl1 \
      libglib2.0-0 \
      libsndfile1 \
      curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

# requirements primero: aprovecha la cache de capas en builds sucesivos.
# torch/torchvision salen del indice CUDA 13.2, el resto de PyPI.
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Modelo de spaCy en espanol (el splitter lo usa)
RUN python -m spacy download es_core_news_sm

# Codigo + instalacion editable del paquete `rag`
COPY setup.py /app/
COPY rag /app/rag
COPY Rag_Milvus /app/Rag_Milvus
RUN pip install -e .

# models/ y corpus_emb/ NO se copian: van montados como volumen
# (son 18 GB, ver .dockerignore)

EXPOSE 8000 8001 8002

# Cada servicio del docker-compose sobreescribe este comando
CMD ["python", "-c", "import torch; print('torch', torch.__version__, '| cuda', torch.cuda.is_available())"]
