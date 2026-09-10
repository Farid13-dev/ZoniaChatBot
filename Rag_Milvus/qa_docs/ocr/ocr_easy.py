import os
import sys

# Consola Windows en cp1252 + emojis en los logs = UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
import io
import re
import asyncio
import numpy as np
import logging
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import easyocr
from pydantic import BaseModel

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Cargar .env
load_dotenv()
# Sin ADMIN_TOKEN en el entorno no hay token valido: los endpoints de
# administracion quedan cerrados en vez de aceptar un default conocido.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4203", "http://localhost:4202"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

reader = None
executor = ThreadPoolExecutor(max_workers=1)
ocr_active = True
connected_clients: list[WebSocket] = []  # 🧠 Lista de clientes WebSocket conectados


class OCRToggleRequest(BaseModel):
    state: bool
    token: str


@app.on_event("startup")
def load_ocr_model():
    global reader
    logging.info("🔍 Cargando modelo OCR...")
    reader = easyocr.Reader(['es', 'en'], gpu=False)
    logging.info("✅ OCR listo.")


def clean_text_fragments(fragments):
    cleaned_text = " ".join(fragments)
    return re.sub(r'\s+', ' ', cleaned_text).strip()


def process_image_with_timeout(image_np):
    if reader is None:
        raise RuntimeError("OCR no disponible")
    raw_text = reader.readtext(image_np, detail=0)
    raw_text = [t for t in raw_text if len(t.strip()) > 2]
    return clean_text_fragments(raw_text)


# 📡 WebSocket endpoint
@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logging.info(f"🟢 Cliente WebSocket conectado. Total: {len(connected_clients)}")
    try:
        while True:
            await websocket.receive_text()  # Para mantener viva la conexión
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logging.info(f"🔴 Cliente WebSocket desconectado. Total: {len(connected_clients)}")


# 🔔 Notificar a todos los clientes WebSocket conectados
async def notify_clients():
    living_clients = []
    for client in connected_clients:
        try:
            await client.send_json({"event": "ocr_changed"})
            living_clients.append(client)
        except Exception as e:
            logging.warning(f"❌ Error enviando a cliente WebSocket: {e}")
    connected_clients[:] = living_clients  # mantener solo clientes activos


@app.post("/toggle-ocr")
async def toggle_ocr(data: OCRToggleRequest):
    global ocr_active, reader

    if not ADMIN_TOKEN or data.token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="No autorizado")

    ocr_active = data.state

    if not ocr_active:
        logging.info("❌ OCR desactivado")
        reader = None
    else:
        if reader is None:
            logging.info("🔄 OCR activado y modelo recargado")
            reader = easyocr.Reader(['es', 'en'], gpu=False)

    # ✅ Notificar cambio a través de WebSocket
    await notify_clients()

    return {"ocr_active": ocr_active}


@app.get("/ocr-status")
async def get_ocr_status():
    return {"ocr_active": ocr_active}


@app.post("/ocr")
async def perform_ocr(file: UploadFile = File(...)):
    global ocr_active, reader

    if not ocr_active or reader is None:
        raise HTTPException(status_code=403, detail="OCR está desactivado por el administrador.")

    if not file.content_type.startswith("image/"):
        return {"text": ""}

    try:
        image = Image.open(io.BytesIO(await file.read()))
        image_np = np.array(image)
    except Exception:
        return {"text": ""}

    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, process_image_with_timeout, image_np),
            timeout=20.0
        )
        return {"text": result}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="El procesamiento de la imagen tomó demasiado tiempo")
    except Exception as e:
        logging.error(f"Error en OCR: {str(e)}")
        return {"text": ""}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ocr_easy:app", host="0.0.0.0", port=8002, reload=True)
