import numpy as np
from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import torch
import torchaudio
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
import warnings
import os
import io
import time

warnings.filterwarnings("ignore")

app = FastAPI()

XTTS_MODEL = None
SAMPLE_RATE = 24000  # Assuming the model outputs at 24kHz


class TTSRequest(BaseModel):
  lang: str
  tts_text: str
  temperature: float = 0.6
  length_penalty: float = 0.9
  repetition_penalty: float = 1.5
  top_k: int = 50
  top_p: float = 0.75
  sentence_split: bool = True
  use_config: bool = False


def clear_gpu_cache():
  if torch.cuda.is_available():
    torch.cuda.empty_cache()


def load_model(xtts_checkpoint: str, xtts_config: str, xtts_vocab: str, xtts_speaker: str):
  global XTTS_MODEL
  clear_gpu_cache()
  config = XttsConfig()
  config.load_json(xtts_config)
  XTTS_MODEL = Xtts.init_from_config(config)
  XTTS_MODEL.load_checkpoint(config, checkpoint_path=xtts_checkpoint, vocab_path=xtts_vocab,
                             speaker_file_path=xtts_speaker, use_deepspeed=False)
  if torch.cuda.is_available():
    XTTS_MODEL.cuda()
  print("Model Loaded!")


@app.on_event("startup")
async def startup_event():
  xtts_checkpoint = "XTTS-v2/model.pth"
  xtts_config = "XTTS-v2/config.json"
  xtts_vocab = "XTTS-v2/vocab.json"
  xtts_speaker = "XTTS-v2/speakers_xtts.pth"
  load_model(xtts_checkpoint, xtts_config, xtts_vocab, xtts_speaker)


def generate_audio(tts_request: TTSRequest):
  if XTTS_MODEL is None:
    raise HTTPException(status_code=400, detail="Model not loaded")

  reference_audio = "audio/female_voice_sample_10.wav"

  gpt_cond_latent, speaker_embedding = XTTS_MODEL.get_conditioning_latents(
    audio_path=reference_audio,
    gpt_cond_len=XTTS_MODEL.config.gpt_cond_len,
    max_ref_length=XTTS_MODEL.config.max_ref_len,
    sound_norm_refs=XTTS_MODEL.config.sound_norm_refs
  )

  if tts_request.use_config:
    out = XTTS_MODEL.inference(
      text=tts_request.tts_text,
      language=tts_request.lang,
      gpt_cond_latent=gpt_cond_latent,
      speaker_embedding=speaker_embedding,
      temperature=XTTS_MODEL.config.temperature,
      length_penalty=XTTS_MODEL.config.length_penalty,
      repetition_penalty=XTTS_MODEL.config.repetition_penalty,
      top_k=XTTS_MODEL.config.top_k,
      top_p=XTTS_MODEL.config.top_p,
      enable_text_splitting=True
    )
  else:
    out = XTTS_MODEL.inference(
      text=tts_request.tts_text,
      language=tts_request.lang,
      gpt_cond_latent=gpt_cond_latent,
      speaker_embedding=speaker_embedding,
      temperature=tts_request.temperature,
      length_penalty=tts_request.length_penalty,
      repetition_penalty=float(tts_request.repetition_penalty),
      top_k=tts_request.top_k,
      top_p=tts_request.top_p,
      enable_text_splitting=tts_request.sentence_split
    )

  return out["wav"].cpu().numpy() if torch.is_tensor(out["wav"]) else out["wav"]

def convert_float_to_int16(audio):
  """Convert float32 audio data to int16 format."""
  audio = np.clip(audio, -1.0, 1.0)  # Asegurarse de que los valores estén dentro de [-1, 1]
  audio = (audio * 32767).astype(np.int16)  # Convertir a int16
  return audio

@app.post("/tts_stream")
async def tts_stream(tts_request: TTSRequest):
  audio_numpy = generate_audio(tts_request)
  segment_int16 = convert_float_to_int16(audio_numpy)  # Convertir a int16
  def iterfile():
    with io.BytesIO() as buffer:
      # Convert numpy array to torch tensor
      audio_tensor = torch.from_numpy(segment_int16).unsqueeze(0)
      torchaudio.save(buffer, audio_tensor, SAMPLE_RATE, format="wav")
      buffer.seek(0)
      yield from buffer

  return StreamingResponse(iterfile(), media_type="audio/wav")


if __name__ == "__main__":
  import uvicorn

  uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
