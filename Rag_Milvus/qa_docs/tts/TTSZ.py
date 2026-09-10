# 📁 qa_docs/services/tts_responder.py
import asyncio
import io
from qa_docs.tts.pypipertts import  PyPiper # Asegúrate que este import sea correcto según tu estructura

class TTSResponder:
    def __init__(self, model: str = "es-mx-laurav2"):
        self.tts = PyPiper()
        self.tts.load_mod(model)
        self.lock = asyncio.Lock()

    async def generate_audio(self, text: str) -> bytes:
        async with self.lock:
            return await asyncio.to_thread(self.tts.generate_audio_chunk, text)
