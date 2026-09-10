import os
import sys

# Consola Windows en cp1252 + emojis en los logs = UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
import tempfile
import gc
import asyncio
import torch
import logging
import numpy as np
from pathlib import Path
import soundfile as sf
from scipy.signal import resample_poly
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
from dotenv import load_dotenv

# DeepFilterNet (denoiser) es OPCIONAL: deepfilterlib solo publica wheels
# hasta cp311, asi que en Python 3.12+ no se puede instalar. Si falta, el
# ASR sigue funcionando, simplemente sin la etapa de reduccion de ruido.
try:
    from df.enhance import enhance, init_df, load_audio, save_audio
    DF_AVAILABLE = True
except ImportError:
    DF_AVAILABLE = False

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Cargar variables del entorno
load_dotenv()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "supersecreto123")

# Raiz del proyecto calculada desde ESTE archivo, no desde el directorio de
# arranque:  .../ZoniaChatBot/Rag_Milvus/qa_docs/asr/asr_whisper.py
#            parents[0]=asr  [1]=qa_docs  [2]=Rag_Milvus  [3]=ZoniaChatBot
# Las rutas relativas ("models/..." o "../models/...") fallaban al lanzar
# el servicio desde qa_docs/asr/: HuggingFace las tomaba por un repo id
# remoto y reventaba con HFValidationError.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = PROJECT_ROOT / "models"

# Un unico modelo para el arranque y para el toggle: antes cargaban modelos
# distintos (marianogonzalezgomez al arrancar, gonznm al reactivar).
WHISPER_MODEL = os.getenv(
    "WHISPER_MODEL",
    str(MODELS_DIR / "marianogonzalezgomez" / "whisper-small-es"),
)

device = "cuda" if torch.cuda.is_available() else "cpu"
TARGET_RATE = 16000

app = FastAPI()

app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:4203", "http://localhost:4202"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

whisper_model = None
processor = None
model_df = None
df_state = None
asr_active = True

# Lista de clientes WebSocket conectados para ASR
connected_asr_clients: list[WebSocket] = []


class ASRToggleRequest(BaseModel):
    state: bool
    token: str


@app.on_event("startup")
def cargar_modelos():
    global model_df, df_state, whisper_model, processor

    if DF_AVAILABLE:
        logging.info("🔄 Cargando DeepFilterNet...")
        model_df, df_state, _ = init_df()
        logging.info("✅ DeepFilterNet listo.")
    else:
        logging.warning(
            "⚠️ DeepFilterNet no instalado (sin wheels para Python 3.12+). "
            "El ASR funcionara sin reduccion de ruido."
        )

    if asr_active:
        logging.info("🔄 Cargando modelo Whisper por defecto...")
        model_id = WHISPER_MODEL
        processor = AutoProcessor.from_pretrained(model_id)
        whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id).to(device)
        logging.info("✅ Whisper cargado por defecto.")


# WebSocket para notificar estado ASR
@app.websocket("/ws/asr")
async def websocket_asr(websocket: WebSocket):
    await websocket.accept()
    connected_asr_clients.append(websocket)
    logging.info(f"🟢 Cliente WebSocket ASR conectado. Total: {len(connected_asr_clients)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_asr_clients.remove(websocket)
        logging.info(f"🔴 Cliente ASR desconectado. Total: {len(connected_asr_clients)}")


# Notificar a todos los clientes conectados
async def notify_asr_clients():
    living_clients = []
    for client in connected_asr_clients:
        try:
            await client.send_json({"event": "asr_changed"})
            living_clients.append(client)
        except Exception as e:
            logging.warning(f"❌ Error enviando a cliente ASR: {e}")
    connected_asr_clients[:] = living_clients


@app.post("/toggle-asr")
async def toggle_asr(data: ASRToggleRequest):
    global asr_active, whisper_model, processor

    if data.token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="No autorizado para cambiar el estado del ASR.")

    asr_active = data.state

    if not asr_active:
        logging.info("🧹 Desactivando ASR...")
        whisper_model = None
        processor = None
        torch.cuda.empty_cache()
        gc.collect()
        logging.info("✅ ASR desactivado y memoria liberada.")
    else:
        if whisper_model is None or processor is None:
            logging.info("🔄 Activando ASR y cargando Whisper...")
            model_id = WHISPER_MODEL
            processor = AutoProcessor.from_pretrained(model_id)
            whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id).to(device)
            logging.info("✅ Whisper cargado.")

    # 🔔 Notificar a los clientes conectados
    await notify_asr_clients()

    return {"asr_active": asr_active}


@app.get("/asr-status")
def get_asr_status():
    return {"asr_active": asr_active}


async def run_transcription(audio_np):
    input_features = processor(audio_np, sampling_rate=TARGET_RATE, return_tensors="pt").input_features.to(device)
    with torch.no_grad():
        predicted_ids = whisper_model.generate(input_features)
        return processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]


@app.post("/transcribe-audio")
async def transcribir_audio(file: UploadFile = File(...)):
    global asr_active, whisper_model, processor

    if not asr_active or whisper_model is None or processor is None:
        raise HTTPException(status_code=400, detail="ASR no está disponible en este momento.")

    archivo_entrada = None
    archivo_mejorado = None

    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Archivo de audio vacío.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_input:
            temp_input.write(audio_bytes)
            archivo_entrada = temp_input.name

        archivo_mejorado = archivo_entrada.replace(".wav", "_mejorado.wav")

        if DF_AVAILABLE and model_df is not None:
            logging.info("🎛️ Aplicando DeepFilterNet...")
            audio, _ = load_audio(archivo_entrada, sr=df_state.sr())
            enhanced_audio = enhance(model_df, df_state, audio)
            save_audio(archivo_mejorado, enhanced_audio, df_state.sr())
            archivo_a_leer = archivo_mejorado
        else:
            archivo_a_leer = archivo_entrada

        # soundfile devuelve (frames, canales); torchaudio usaba (canales, frames)
        audio_np_raw, sr = sf.read(archivo_a_leer, dtype="float32", always_2d=True)
        audio_tensor = torch.from_numpy(audio_np_raw.T.copy())
        if audio_tensor.shape[1] == 0:
            raise ValueError("El archivo de audio no contiene datos válidos.")

        if audio_tensor.shape[0] > 1:
            audio_tensor = torch.mean(audio_tensor, dim=0, keepdim=True)

        energy = torch.mean(torch.abs(audio_tensor)).item()
        logging.info(f"🔍 Energía del audio: {energy:.6f}")
        if energy < 0.005:
            raise HTTPException(status_code=400, detail="Audio silencioso detectado.")

        if sr != TARGET_RATE:
            from math import gcd
            g = gcd(int(sr), TARGET_RATE)
            audio_tensor = torch.from_numpy(
                resample_poly(audio_tensor.numpy(), TARGET_RATE // g, int(sr) // g, axis=-1)
                .astype("float32")
            )

        audio_np = audio_tensor.squeeze().numpy()

        loop = asyncio.get_running_loop()
        transcripcion = await asyncio.wait_for(
            run_transcription(audio_np),
            timeout=20.0
        )

    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="La transcripción tomó demasiado tiempo")
    except Exception as e:
        logging.error(f"❌ Error en transcripción: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        torch.cuda.empty_cache()
        gc.collect()
        for f in [archivo_entrada, archivo_mejorado]:
            if f and os.path.exists(f):
                os.remove(f)

    return {"transcription": transcripcion}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("asr_whisper:app", host="0.0.0.0", port=8001, reload=True)
