import pyaudio
import torch
import numpy as np
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
from threading import Thread
from time import sleep

model_id = "../facebook/wav2vec2-large-xlsr-53-spanish"
# Cargar el procesador y el modelo preentrenado en español
processor = Wav2Vec2Processor.from_pretrained(model_id)
model = Wav2Vec2ForCTC.from_pretrained(model_id).to(
    "cuda" if torch.cuda.is_available() else "cpu")

# Parámetros de grabación
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # El modelo Wav2Vec2 requiere audio a 16kHz
CHUNK = 1024  # Tamaño del fragmento (64 ms de audio por fragmento)
audio_interface = pyaudio.PyAudio()

# Función para transcribir en stream continuo
def stream_transcripcion():
    stream = audio_interface.open(format=FORMAT, channels=CHANNELS,
                                  rate=RATE, input=True,
                                  frames_per_buffer=CHUNK)
    print("Grabando... Presiona Ctrl+C para detener.")
    audio_acumulado = np.array([], dtype=np.float32)  # Acumular los datos de audio

    def transcribir_audio():
        while True:
            sleep(1)  # Transcribir cada segundo
            if len(audio_acumulado) > RATE:  # Solo si hay más de un segundo de audio
                input_values = processor(audio_acumulado, sampling_rate=RATE, return_tensors="pt").input_values
                input_values = input_values.to("cuda" if torch.cuda.is_available() else "cpu")

                with torch.no_grad():
                    logits = model(input_values).logits

                predicted_ids = torch.argmax(logits, dim=-1)
                transcripcion = processor.batch_decode(predicted_ids)[0]

                print("Transcripción parcial:", transcripcion)

    # Hilo separado para procesar y transcribir el audio
    transcribir_thread = Thread(target=transcribir_audio)
    transcribir_thread.start()

    try:
        while True:
            # Leer fragmento de audio
            data = stream.read(CHUNK)
            audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0  # Normalizar el audio
            audio_acumulado = np.concatenate((audio_acumulado, audio_np))  # Acumular fragmentos

            if len(audio_acumulado) > RATE * 5:  # Acumular solo 5 segundos máximo
                audio_acumulado = audio_acumulado[-RATE:]  # Mantener solo el último segundo de audio

    except KeyboardInterrupt:
        print("Grabación detenida.")

    stream.stop_stream()
    stream.close()

# Ejecutar la transcripción en stream
if __name__ == "__main__":
    stream_transcripcion()
