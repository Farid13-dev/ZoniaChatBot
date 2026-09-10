import os
import io
import json
import subprocess
import uuid
import requests
import re
from pydub import AudioSegment


# Raiz de Rag_Milvus calculada desde este archivo: os.getcwd() dependia del
# directorio desde el que arrancaras el servicio.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PyPiper:
    def __init__(self):
        self.voices_dir = os.path.join(BASE_DIR, "voices")
        os.makedirs(self.voices_dir, exist_ok=True)

        voices_json_path = os.path.join(self.voices_dir, "voices.json")
        if not os.path.isfile(voices_json_path):
            voice_file = requests.get("https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json")
            with open(voices_json_path, 'wb') as w:
                w.write(voice_file.content)

        with open(voices_json_path, "rb") as file:
            voice_main = json.loads(file.read())

        self.key_list = list(voice_main.keys())
        self.loaded_model_name = None
        self.json_ob = None

    def load_mod(self, instr="es-mx-laurav2"):
        if self.loaded_model_name == instr:
            return  # Ya está cargado

        lang = instr.split("_")[0]
        dia, name, style = instr.split("-")
        file = f'{instr}.onnx'
        model_path = os.path.join(self.voices_dir, file)
        json_path = f"{model_path}.json"

        if not os.path.isfile(model_path):
            print(f"📥 Descargando modelo: {file}")
            m_path = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang}/{dia}/{name}/{style}/{file}"
            json_file = requests.get(f"{m_path}.json")
            mod_file = requests.get(m_path)
            with open(model_path, 'wb') as m:
                m.write(mod_file.content)
            with open(json_path, 'wb') as j:
                j.write(json_file.content)

        self.loaded_model_name = instr
        self.json_ob = json_path
        print(f"✅ Modelo '{instr}' cargado correctamente.")

    def generate_audio_chunk(self, text: str):
        if not self.loaded_model_name:
            raise RuntimeError("❌ No hay modelo cargado para TTS.")

        model_path = os.path.join(self.voices_dir, f"{self.loaded_model_name}.onnx")
        json_path = f"{model_path}.json"
        piper_exe = os.path.join(BASE_DIR, "piper", "piper.exe")

        # Sin shell=True: lanzaba cmd.exe ademas de piper.
        command = [
            piper_exe,
            "--model", model_path,
            "--config", json_path,
            "--output-raw",
            "--length_scale", "1.0",
            "--noise_scale", "0.3",
            "--noise_w", "0.3",
            "--sentence_silence", "0.3",
        ]

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            raw_audio_data, stderr = process.communicate(input=text.encode("utf-8"))

            if process.returncode != 0:
                raise RuntimeError("Piper error: " + stderr.decode(errors="replace"))

            if not raw_audio_data:
                raise RuntimeError("❌ No se generó audio válido.")

            buffer = io.BytesIO()
            audio_segment = AudioSegment(
                data=raw_audio_data,
                sample_width=2,
                frame_rate=22050,
                channels=1
            )
            audio_segment.export(buffer, format="wav")
            return buffer.getvalue()

        except Exception as e:
            raise RuntimeError("Error interno al ejecutar Piper: " + str(e))
