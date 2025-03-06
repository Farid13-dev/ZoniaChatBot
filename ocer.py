from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import torch

# Configurar el dispositivo y cargar el modelo OCR
device = "cuda" if torch.cuda.is_available() else "cpu"

# Lista de rutas de imágenes locales
# image_paths = ["image/ocr_1.png", "image/ocr_2.png", "image/ocr_3.png", "image/ocr_4.png","image/ocr_6.png","image/ocr_7.png","image/ocr_8.png","image/ocr_9.png","image/ocr_10.jpg","image/ocr_11.jpg", "image/example_3.jpeg"]  # Agrega más imágenes si es necesario

image_paths = [
  './image/ocr_1.png',
  './image/ocr_2.jpg',
  './image/ocr_3.png',
  './image/ocr_4.png',
  './image/ocr_5.png',
  './image/ocr_6.png',
  './image/ocr_7.png',
  './image/ocr_8.jpg',
  './image/ocr_9.jpg',
  './image/ocr_10.jpeg',
  './image/ocr_11.jpg',
  './image/ocr_12.jpg',
  './image/ocr_13.png',
  './image/ocr_14.png',
  './image/ocr_15.png',
  './image/ocr_16.png',
]
# Cargar el modelo y el procesador
processor = TrOCRProcessor.from_pretrained("qantev/trocr-small-spanish")
model = VisionEncoderDecoderModel.from_pretrained("qantev/trocr-small-spanish").to(device)

# Cargar imágenes en formato RGB
images = [Image.open(img_path).convert("RGB") for img_path in image_paths]

# Preprocesar las imágenes
pixel_values = processor(images=images, return_tensors="pt").pixel_values.to(device)

# Generar texto para todas las imágenes
generated_ids = model.generate(pixel_values)
generated_texts = processor.batch_decode(generated_ids, skip_special_tokens=True)

# Mostrar resultados
for i, text in enumerate(generated_texts):
  print(f"Imagen {i + 1}: {text}")
