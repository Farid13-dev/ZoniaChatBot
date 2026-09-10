import asyncio
import re
import base64
from starlette.websockets import WebSocket


class TTSStreamBuffer:
    END_OF_SENTENCE_REGEX = re.compile(r"[.!?]$")

    # min_chars alto a proposito: cada invocacion de piper recarga el modelo
    # ONNX y cuesta ~2s fijos, asi que sintetizar frase a frase (min_chars=40)
    # pagaba ese arranque una y otra vez. Agrupando ~250 caracteres se hacen
    # ~3x menos llamadas: 3 frases juntas tardan 5.1s frente a 10.7s sueltas.
    def __init__(self, websocket: WebSocket, tts_engine, min_chars: int = 250,
                 delay: float = 0.0, enabled: bool = True,
                 first_chars: int = 80, request_id: str = ""):
        self.websocket = websocket
        self.tts = tts_engine
        self.min_chars = min_chars
        self.request_id = request_id
        # El primer bloque se manda antes (80 caracteres) para que la voz
        # empiece pronto; los siguientes se agrupan a min_chars para pagar
        # menos veces el arranque de piper.
        self.first_chars = first_chars
        self._primer_bloque = True
        self.delay = delay
        self.enabled = enabled
        self.buffer = ""
        self.queue = asyncio.Queue()
        self._flushed = False
        self._consumer_task = None
        self._send_lock = asyncio.Lock()

        if self.enabled:
            self._consumer_task = asyncio.create_task(self._tts_consumer())

    async def process_chunk(self, chunk: str):
        self.buffer += chunk
        await self.websocket.send_json(
            {"type": "chunk", "data": chunk, "request_id": self.request_id}
        )

        if not self.enabled:
            return

        umbral = self.first_chars if self._primer_bloque else self.min_chars
        if (
            len(self.buffer.strip()) >= umbral and
            self.END_OF_SENTENCE_REGEX.search(self.buffer.strip())
        ):
            await self.queue.put(self.buffer.strip())
            self.buffer = ""
            self._primer_bloque = False

        # Antes habia `await asyncio.sleep(self.delay)` (10 ms) por CADA trozo:
        # en una respuesta de varios cientos de tokens son segundos de retraso
        # inventado. Basta con ceder el control al loop.
        await asyncio.sleep(0)

    async def flush(self):
        if self._flushed:
            return
        self._flushed = True

        if not self.enabled:
            return

        if self.buffer.strip():
            await self.queue.put(self.buffer.strip())
            self.buffer = ""

        await self.queue.put(None)  # Señal de finalización

        # NO se espera al consumidor. Antes se hacia `await self._consumer_task`
        # aqui, asi que _serve_question quedaba bloqueado hasta sintetizar TODA
        # la respuesta: ~3.8s por frase, ~76s en una respuesta de 20 frases, y
        # durante ese rato el usuario ya habia terminado de leer pero no le
        # llegaban ni las fuentes ni el "end". El audio sigue generandose en
        # segundo plano y llega por el WebSocket segun esta listo.
        if not self._consumer_task:
            self._consumer_task = asyncio.create_task(self._tts_consumer())

    async def _tts_consumer(self):
        while True:
            text = await self.queue.get()
            if text is None:
                break

            try:
                audio_bytes = await self.tts.generate_audio(text)
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

                # 🚧 Bloquea envíos simultáneos
                async with self._send_lock:
                    if self.websocket.application_state == self.websocket.application_state.CONNECTED:
                        await self.websocket.send_json(
                            {"type": "audio", "data": audio_b64,
                             "request_id": self.request_id}
                        )

            except Exception as e:
                try:
                    await self.websocket.send_json({
                        "type": "warn",
                        "data": f"TTS error: {str(e)}",
                        "request_id": self.request_id,
                    })
                except Exception:
                    # El WebSocket puede estar ya cerrado; no dejar que la
                    # excepcion mate la tarea del consumidor en silencio.
                    break

    async def cancel(self):
        """Cancela cualquier audio pendiente e interrumpe el consumidor."""
        self._flushed = True

        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        await self.queue.put(None)

        # NO se espera al consumidor: cancel() se llama desde el bucle que
        # recibe mensajes del WebSocket, y esperar aqui bloqueaba la llegada
        # de la siguiente pregunta hasta terminar el bloque de audio en curso.
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
