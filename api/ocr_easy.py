from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import easyocr
import numpy as np
import io
import re

app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar el lector OCR
reader = easyocr.Reader(['es','en'], gpu=True)

# Función para unir fragmentos de texto de OCR de manera limpia
def clean_text_fragments(fragments):
    cleaned_text = " ".join(fragments)
    #cleaned_text = re.sub(r'\s+([.,;:!?])', r'\1', cleaned_text)  # Elimina espacios antes de signos de puntuación
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Elimina espacios dobles
    return cleaned_text.strip()

# Endpoint para procesar una sola imagen y extraer el texto con EasyOCR
@app.post("/ocr")
async def perform_ocr(file: UploadFile = File(...)):
    image = Image.open(io.BytesIO(await file.read()))
    image_np = np.array(image)
    raw_text = reader.readtext(image_np, detail=0)
    cleaned_text = clean_text_fragments(raw_text)
    print("Texto extraído:", cleaned_text)
    return {"text": cleaned_text}
