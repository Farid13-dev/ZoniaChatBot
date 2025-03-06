import os
import gc
import torch
import torchaudio
import librosa
import io
import subprocess
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
from df.enhance import enhance, init_df, load_audio, save_audio
from scipy.signal import butter, lfilter

# 📌 Inicialización de modelos globales
device = "cuda" if torch.cuda.is_available() else "cpu"
RATE = 44100  # Frecuencia esperada de muestreo
TARGET_RATE = 16000  # Frecuencia requerida por Whisper

app = FastAPI()

# Configuración de CORS
app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:4200"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Variables de estado
whisper_model = None
processor = None
model_df = None
df_state = None

asr_active = True  # Control para activar/desactivar ASR

english_active = False
spanish_active = True

# 📁 Rutas de archivos importantes para DeepFilterNet
archivo_filtrado = "temp_audio_16k.wav"
audio_path = "grabacion_limpio.wav"


class ASRState(BaseModel):
  """Modelo para activar o desactivar ASR."""
  state: bool


def butter_bandpass(lowcut, highcut, fs, order=5):
  """Crea un filtro paso banda para voz humana."""
  nyquist = 0.5 * fs
  low, high = lowcut / nyquist, highcut / nyquist
  return butter(order, [low, high], btype='band')


def apply_bandpass_filter(audio, lowcut=300, highcut=3400, fs=16000, order=5):
  """Aplica un filtro paso banda al audio."""
  b, a = butter_bandpass(lowcut, highcut, fs, order)
  return lfilter(b, a, audio)


def convertir_a_wav(input_bytes, output_file):
  """Convierte cualquier formato de audio recibido en WAV PCM 16-bit."""
  try:
    process = subprocess.run(
      ["ffmpeg", "-y", "-i", "pipe:0", "-ac", "1", "-ar", str(TARGET_RATE),
       "-sample_fmt", "s16", output_file],
      input=input_bytes,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      check=True
    )
    print(f"✅ Archivo convertido a WAV PCM 16-bit: {output_file}")
  except subprocess.CalledProcessError as e:
    print(f"❌ Error en conversión de audio: {str(e.stderr)}")
    raise HTTPException(status_code=500, detail="Error en conversión de audio.")


@app.post("/toggle-asr")
async def toggle_asr(data: ASRState):
  """Endpoint para activar o desactivar el ASR."""
  global asr_active
  asr_active = data.state
  return {"asr_active": asr_active}

@app.post("/toogle-lenguage")
async def toggle_lenguage(data: ASRState):
  """Endpoint para spanish o english."""
  global spanish_active
  spanish_active = data.state
  return {"spanish_active": spanish_active}

@app.post("/transcribe-audio")
async def transcribir_audio(file: UploadFile = File(...)):
  """Endpoint para transcribir audio en tiempo real si ASR está activo."""
  global asr_active, whisper_model, processor, model_df, df_state

  if not asr_active:
    raise HTTPException(status_code=400, detail="ASR está desactivado.")

  # Cargar modelos si no están inicializados
  if whisper_model is None:
    print("🔄 Cargando Whisper...")
    model_id = "openai/whisper-medium"
    processor = AutoProcessor.from_pretrained(model_id)
    whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id).to(device)

  if model_df is None or df_state is None:
    print("🔄 Cargando DeepFilterNet...")
    model_df, df_state, _ = init_df()

  torch.cuda.empty_cache()

  # Leer el archivo en memoria
  audio_bytes = await file.read()

  # Convertir audio a WAV PCM 16-bit en archivo (requerido por DeepFilterNet)
  convertir_a_wav(audio_bytes, archivo_filtrado)
  # Cargar el archivo de audio
  #audio, sr = librosa.load(archivo_original, sr=16000, mono=True)

  # Guardar el audio en formato WAV con 16kHz y mono
  #sf.write(archivo_original, audio, 16000)

  # Validar archivo
  if not os.path.exists(archivo_filtrado) or os.path.getsize(archivo_filtrado) == 0:
    raise HTTPException(status_code=400, detail="Archivo de audio inválido.")

  print("📌 Archivo guardado correctamente.")

  try:
    # 🔹 **DeepFilterNet (NO SE MODIFICA)**
    print("🎛️ Aplicando DeepFilterNet...")
    audio, _ = load_audio(archivo_filtrado, sr=df_state.sr())
    enhanced_audio = enhance(model_df, df_state, audio)
    save_audio(audio_path, enhanced_audio, df_state.sr())

    # Cargar y procesar audio mejorado
    audio, _ = torchaudio.load(audio_path)
    if audio.shape[0] > 1:  # Convertir a mono si es estéreo
      audio = torch.mean(audio, dim=0, keepdim=True)

    # Resampleo en GPU si es posible
    if _ != TARGET_RATE:
      audio = torchaudio.transforms.Resample(orig_freq=_, new_freq=TARGET_RATE)(audio)

    # Convertir tensor a numpy
    audio_np = audio.squeeze().numpy()

    # Aplicar filtro de voz
    audio_filtrado = apply_bandpass_filter(audio_np)

    # Normalizar audio
    audio_norm = librosa.util.normalize(audio_filtrado)

    # Transcripción en tiempo real con Whisper
    input_features = processor(audio_norm, sampling_rate=TARGET_RATE, return_tensors="pt").input_features.to(device)

    with torch.no_grad():
      predicted_ids = whisper_model.generate(input_features)
      transcripcion = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

    # Liberar caché
    torch.cuda.empty_cache()
    gc.collect()

  except Exception as e:
    print("❌ Error:", str(e))
    raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

  finally:
    # Mantener los archivos que requiere DeepFilterNet, eliminar solo los innecesarios
    os.remove(archivo_filtrado)

  return {"transcription": transcripcion}
