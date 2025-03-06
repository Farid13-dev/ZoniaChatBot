from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import io
import torch
import os
import soundfile as sf
from script.chatpdf import Rag  # Ajusta la ruta según tu estructura de archivos
from similarities import BertSimilarity
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import librosa
import gc  # Para la recolección de basura
import requests

# Inicializar FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


# Definir la clase de entrada esperada por FastAPI
class QueryRequest(BaseModel):
  query: str


# Inicialización global del modelo (será inicializado en startup)
rag_model = None
whisper_model = None
processor = None
device = None


@app.on_event("startup")
async def startup_event():
  global rag_model
  device = "cuda" if torch.cuda.is_available() else "cpu"

  # Liberar memoria de GPU antes de cargar un nuevo modelo
  torch.cuda.empty_cache()

  # Configuración de los parámetros del modelo
  sim_model_name = "prudant/lsg_4096_sentence_similarity_spanish"
  gen_model_type = "auto"
  gen_model_name = "Qwen/Qwen2.5-0.5B-Instruct"
  lora_model = None
  rerank_model_name = "BAAI/bge-reranker-base"
  corpus_files = "Acuerdo009.pdf"

  int4 = False
  int8 = False
  chunk_size = 220
  chunk_overlap = 0
  num_expand_context_chunk = 0

  # Inicializar el modelo de similitud y RAG
  similarity_model = BertSimilarity(model_name_or_path=sim_model_name, device=device)
  rag_model = Rag(
    similarity_model=similarity_model,
    generate_model_type=gen_model_type,
    generate_model_name_or_path=gen_model_name,
    lora_model_name_or_path=lora_model,
    device=device,
    int4=int4,
    int8=int8,
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
    corpus_files=[corpus_files],
    num_expand_context_chunk=num_expand_context_chunk,
    rerank_model_name_or_path=rerank_model_name,
  )

  # Comprobar si existen incrustaciones guardadas
  dir_name = rag_model.get_file_hash([corpus_files])
  save_dir = os.path.join(rag_model.save_corpus_emb_dir, dir_name)

  if os.path.exists(save_dir):
    rag_model.load_corpus_emb(save_dir)
  else:
    rag_model.add_corpus([corpus_files])
    rag_model.save_corpus_emb()


# Endpoint de FastAPI para recibir la consulta y devolver la respuesta del modelo
@app.get("/")
async def root():
  return {"message": "API de ZoniaChatBot está funcionando"}


# Define el endpoint predict-stream
@app.post("/predict-stream")
async def predict_stream(request: QueryRequest):
  try:
    global rag_model
    if rag_model is None:
      raise HTTPException(status_code=500, detail="El modelo no está inicializado")

    # Función que genera la respuesta en streaming
    def generate_response():
      for chunk in rag_model.predict_stream(request.query):
        yield chunk
      # Liberar memoria de GPU después de cada generación de respuesta
      torch.cuda.empty_cache()

      # Eliminar variables innecesarias y recolectar basura
      gc.collect()

    return StreamingResponse(generate_response(), media_type="text/plain")

  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error procesando la solicitud: {str(e)}")


