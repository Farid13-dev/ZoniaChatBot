import pyaudio
import wave
import librosa
import torch
import numpy as np
import keyboard
import noisereduce as nr
from scipy.signal import butter, lfilter
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
from df.enhance import enhance, init_df, load_audio, save_audio  # DeepFilterNet

# 📌 Inicializar modelos globalmente
device = "cuda" if torch.cuda.is_available() else "cpu"

# DeepFilterNet
model_df, df_state, _ = init_df()

# Whisper
model_id = "../openai/whisper-medium"
processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id).to(device)

# 🎤 Parámetros de grabación
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 4096

# 📁 Rutas de archivos
archivo_original = "grabacion_w.wav"
archivo_filtrado = "grabacion_limpio.wav"


def butter_bandpass(lowcut, highcut, fs, order=5):
    """ Crea un filtro paso banda para voz humana """
    nyquist = 0.5 * fs
    low, high = lowcut / nyquist, highcut / nyquist
    return butter(order, [low, high], btype='band')


def apply_bandpass_filter(audio, lowcut=300, highcut=3400, fs=RATE, order=5):
    """ Aplica un filtro paso banda al audio """
    b, a = butter_bandpass(lowcut, highcut, fs, order)
    return lfilter(b, a, audio)


def iniciar_grabacion():
    """ Captura audio en vivo y guarda el archivo WAV """
    print("🎤 Grabando... Presiona 's' para detener.")
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []

    while not keyboard.is_pressed('s'):
        frames.append(stream.read(CHUNK))

    # Finalizar grabación
    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Guardar el audio original
    with wave.open(archivo_original, 'wb') as waveFile:
        waveFile.setnchannels(CHANNELS)
        waveFile.setsampwidth(audio.get_sample_size(FORMAT))
        waveFile.setframerate(RATE)
        waveFile.writeframes(b''.join(frames))

    print(f"📁 Audio guardado: {archivo_original}")

    # Aplicar DeepFilterNet y convertir a texto
    aplicar_filtro_deepfilternet()
    convertir_audio_a_texto()


def aplicar_filtro_deepfilternet():
    """ Aplica DeepFilterNet para limpiar el audio grabado """
    print("🎛️ Aplicando DeepFilterNet...")
    audio, _ = load_audio(archivo_original, sr=df_state.sr())
    enhanced_audio = enhance(model_df, df_state, audio)
    save_audio(archivo_filtrado, enhanced_audio, df_state.sr())
    print(f"✅ Audio mejorado guardado en: {archivo_filtrado}")


def convertir_audio_a_texto():
    """ Convierte el audio procesado en texto con Whisper """
    print("📝 Convirtiendo a texto...")

    # Cargar y procesar audio
    audio, _ = librosa.load(archivo_filtrado, sr=RATE)
    audio_filtrado = apply_bandpass_filter(audio)  # Filtro de voz

    # Resampleo a 16 kHz para Whisper
    audio_16k = librosa.resample(audio_filtrado, orig_sr=RATE, target_sr=16000)
    audio_norm = librosa.util.normalize(audio_16k)

    # Transcripción con Whisper
    input_features = processor(audio_norm, sampling_rate=16000, return_tensors="pt").input_features.to(device)
    predicted_ids = model.generate(input_features)
    transcripcion = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

    print("📜 Texto transcrito:", transcripcion)
    repetir_proceso()


def repetir_proceso():
    """ Permite repetir la grabación sin reiniciar el programa """
    print("\n🔄 ¿Grabar otro audio? (Presiona 'g' para grabar o 'q' para salir)")
    while True:
        if keyboard.is_pressed('g'):
            iniciar_grabacion()
            break
        elif keyboard.is_pressed('q'):
            print("👋 Saliendo...")
            break


def mostrar_menu():
    """ Muestra el menú inicial """
    print("\n📌 --- Menú de Grabación y Transcripción ---")
    print("🎤 Presiona 'g' para grabar audio")
    print("❌ Presiona 'q' para salir")

    while True:
        if keyboard.is_pressed('g'):
            iniciar_grabacion()
        elif keyboard.is_pressed('q'):
            print("👋 Saliendo del programa.")
            break


if __name__ == "__main__":
    mostrar_menu()
