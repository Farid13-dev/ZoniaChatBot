import whisper
import os

# 📌 Crear carpeta para guardar los modelos
model_dir = "whisper_models"
os.makedirs(model_dir, exist_ok=True)

# 📌 Descargar el modelo y guardarlo localmente
model_name = "medium"  # Puedes usar: "tiny", "base", "small", "medium", "large"
model = whisper.load_model(model_name, download_root=model_dir)

print(f"✅ Modelo {model_name} guardado en {model_dir}")
