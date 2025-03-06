from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel


# Función avanzada para ajustar brillo y contraste adaptativamente
def adjust_brightness_contrast(image):
  gray_image = image.convert("L")
  histogram = gray_image.histogram()
  brightness = sum(i * histogram[i] for i in range(256)) / sum(histogram)

  if brightness > 180:
    contrast_factor = 1.2
    brightness_factor = 0.9
  elif brightness > 140:
    contrast_factor = 1.5
    brightness_factor = 1.0
  elif brightness > 100:
    contrast_factor = 2.0
    brightness_factor = 1.1
  else:
    contrast_factor = 2.5
    brightness_factor = 1.2

  enhancer_contrast = ImageEnhance.Contrast(image)
  enhanced_image = enhancer_contrast.enhance(contrast_factor)

  enhancer_brightness = ImageEnhance.Brightness(enhanced_image)
  bright_image = enhancer_brightness.enhance(brightness_factor)
  bright_image = bright_image.filter(ImageFilter.MedianFilter(size=3))

  return bright_image


# Función para corrección de perspectiva y alineación
def correct_perspective(image):
  gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
  edges = cv2.Canny(gray, 50, 150, apertureSize=3)
  contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]

  for cnt in contours:
    epsilon = 0.02 * cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, epsilon, True)
    if len(approx) == 4:
      pts = approx
      break
  else:
    return image  # Si no se encuentra cuadrilátero, retornar la imagen sin modificar

  pts = pts.reshape(4, 2)
  rect = np.zeros((4, 2), dtype="float32")
  s = pts.sum(axis=1)
  rect[0] = pts[np.argmin(s)]
  rect[2] = pts[np.argmax(s)]
  diff = np.diff(pts, axis=1)
  rect[1] = pts[np.argmin(diff)]
  rect[3] = pts[np.argmax(diff)]
  (tl, tr, br, bl) = rect
  widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
  widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
  maxWidth = max(int(widthA), int(widthB))
  heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
  heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
  maxHeight = max(int(heightA), int(heightB))
  dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
  M = cv2.getPerspectiveTransform(rect, dst)
  return Image.fromarray(cv2.warpPerspective(np.array(image), M, (maxWidth, maxHeight)))


# Procesar imagen y convertir a blanco y negro con limpieza de ruido
def preprocess_image_for_ocr(image):
  open_cv_image = np.array(image.convert("L"))

  clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
  clahe_image = clahe.apply(open_cv_image)

  binary_image = cv2.adaptiveThreshold(clahe_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 10)
  kernel = np.ones((1, 1), np.uint8)
  morph_image = cv2.morphologyEx(binary_image, cv2.MORPH_OPEN, kernel, iterations=1)
  clean_image = cv2.morphologyEx(morph_image, cv2.MORPH_CLOSE, kernel, iterations=2)
  final_image = cv2.bitwise_not(clean_image)
  final_image_rgb = cv2.cvtColor(final_image, cv2.COLOR_GRAY2RGB)

  return Image.fromarray(final_image_rgb)


# Configurar el dispositivo y cargar el modelo OCR
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Dispositivo: {device}")
model_id = "qantev/trocr-small-spanish"
processor = TrOCRProcessor.from_pretrained(model_id)
model = VisionEncoderDecoderModel.from_pretrained(model_id).to(device)


# Función para procesar múltiples imágenes y realizar OCR
def ocr_multiple_images(image_array):
  results = {}
  for i, image in enumerate(image_array):
    # Corrección de perspectiva y ajuste de brillo y contraste
    corrected_image = correct_perspective(image)
    bright_image = adjust_brightness_contrast(corrected_image)
    processed_image = preprocess_image_for_ocr(bright_image)

    # Generar texto a partir de la imagen procesada
    pixel_values = processor(images=processed_image, return_tensors="pt").pixel_values.to(device)
    generated_ids = model.generate(pixel_values, max_new_tokens=150, num_beams=5, temperature=0.7)
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # Guardar resultado
    results[f"Imagen_{i + 1}"] = generated_text
    print(f"Imagen_{i + 1}", generated_text)
  return results


# Ejemplo de uso: cargar imágenes en un array y pasarlas a la función
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
]

image_array = [Image.open(path) for path in image_paths]
results = ocr_multiple_images(image_array)
print(results)
