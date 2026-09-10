# 📁 sources.py
import os
import shutil
import hashlib
import asyncio
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from sqlalchemy import text
from werkzeug.utils import secure_filename

from qa_docs import (
  engine, r_db, get_db, save_context, context,
  DB_FOLDER, UPLOAD_FOLDER, CONTEXT_FILE, ALLOWED_EXTENSIONS
)
from qa_docs.db_relational import lite_relational
from qa_docs.db_relational.db_manager import DatabaseManager
import logging
logger = logging.getLogger(__name__)
router_sources = APIRouter()


@router_sources.post("/create_database")
async def create_database(request: Request):
  """
  • Crea (o valida) la colección Milvus
  • Crea las tablas SQLite
  • NO carga embeddings, LLM ni reranker
  • Idempotente – devuelve 200 aunque todo exista
  """
  db_manager = request.app.state.db_manager  # singleton creado en startup

  try:
    # Storage ya se preparó en startup; lo repetimos por seguridad.
    await asyncio.to_thread(db_manager.init_milvus_storage)

    context["collection_exists"] = True
    save_context()

    return JSONResponse(
      status_code=200,
      content={"message": "Bases de datos listas ✅"},
    )

  except Exception as exc:
    return JSONResponse(
      content={"error": f"❌ Error creando bases de datos: {exc}"},
      status_code=500,
    )


# ----------------------  LIST DOCUMENTS  ----------------------
@router_sources.get("/milvus/list_documents")
async def list_indexed_documents(request: Request):
    try:
        raw = request.app.state.db_manager.list_documents()
        uniq = {}
        for item in raw:
            doc_id = item.get("document_id")
            metadata = item.get("metadata", {})
            if doc_id and doc_id not in uniq:
                uniq[doc_id] = {"document_id": doc_id, "metadata": metadata}
        return {"documents": list(uniq.values())}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error listando documentos: {e}")

# ----------------------  DELETE DOCUMENT  ----------------------
@router_sources.delete("/milvus/delete_document/{document_id}")
async def delete_document_from_milvus(document_id: str, request: Request):
    try:
        request.app.state.db_manager.delete_document(document_id)
        return {"message": f"✅ Documento '{document_id}' eliminado de Milvus."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Error eliminando documento: {e}")


def allowed_file(filename: str) -> bool:
  return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@router_sources.post("/include_source")
async def include_source(file: UploadFile = File(None), include_url: str = Form(None)):
  if file is None and not include_url:
    return JSONResponse(status_code=200, content={"message": "Debe proporcionar un archivo o una URL."})

  if include_url:
    context["sources_to_add"].append(include_url)

  if file and allowed_file(file.filename):
    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)

    if os.path.exists(path):
      return JSONResponse(status_code=200,
                          content={"message": f"El archivo '{filename}' ya existe en la carpeta de carga."})

    with open(path, "wb") as buffer:
      buffer.write(await file.read())

    context["sources_to_add"].append(filename)
    save_context()

  return JSONResponse(content={"message": "Fuente incluida correctamente", "sources_to_add": context["sources_to_add"]})


@router_sources.get("/list_uploaded_files")
async def list_uploaded_files():
  if not os.path.exists(UPLOAD_FOLDER):
    return JSONResponse(content={"message": "No hay archivos en la carpeta."}, status_code=200)

  files = [f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]

  if not files:
    return JSONResponse(content={"message": "No hay archivos en la carpeta."}, status_code=200)

  return {"files": files}


@router_sources.delete("/delete_uploaded_file/{filename}")
async def delete_uploaded_file(filename: str):
  file_path = os.path.join(UPLOAD_FOLDER, filename)
  if not os.path.exists(file_path):
    raise HTTPException(status_code=404, detail="Archivo no encontrado.")

  try:
    os.remove(file_path)
    save_context()
    return JSONResponse(content={"message": f"Archivo '{filename}' eliminado correctamente"}, status_code=200)
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error al eliminar el archivo: {str(e)}")


def calculate_file_hash(file_path: str) -> str:
  hasher = hashlib.sha256()
  with open(file_path, "rb") as f:
    while chunk := f.read(8192):
      hasher.update(chunk)
  return hasher.hexdigest()


@router_sources.post("/upload_source_to_sqlite")
async def upload_source_to_sqlite(filename: str = Form(...), categoria: str = Form(...), descripcion: str = Form(...),
                                  db: AsyncSession = Depends(get_db)):
  file_path = os.path.join(UPLOAD_FOLDER, filename)
  if not os.path.exists(file_path):
    raise HTTPException(status_code=404, detail="Archivo no encontrado en la carpeta 'uploads'.")

  file_hash = calculate_file_hash(file_path)

  stmt = select(lite_relational.Document).where(lite_relational.Document.file_hash == file_hash)
  result = await db.execute(stmt)
  existing_doc = result.scalars().first()

  if existing_doc:
    return JSONResponse(status_code=200,
                        content={"message": f"⚠️ El archivo '{filename}' ya existe en la base de datos."})

  with open(file_path, "rb") as f:
    file_content = f.read()

  new_doc = lite_relational.Document(
    name=filename,
    categoria=categoria,
    descripcion=descripcion,
    file_hash=file_hash,
    file_data=file_content
  )

  db.add(new_doc)
  await db.commit()
  await db.refresh(new_doc)
  return {"message": "✅ Archivo agregado a SQLite exitosamente con BLOB", "file_id": new_doc.id}


@router_sources.get("/list_sqlite_files")
async def list_sqlite_files(db: AsyncSession = Depends(get_db)):
  try:
    check_table_stmt = text("SELECT name FROM sqlite_master WHERE type='table' AND name='document'")
    result = await db.execute(check_table_stmt)
    table_exists = result.scalar_one_or_none()

    if not table_exists:
      return []

    stmt = select(lite_relational.Document)
    result = await db.execute(stmt)
    documents = result.scalars().all()

    return [
      {"id": doc.id, "name": doc.name, "categoria": doc.categoria, "timestamp": doc.timestamp}
      for doc in documents
    ]
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error al consultar la base de datos: {str(e)}")


@router_sources.delete("/delete_sqlite_file/{file_id}")
async def delete_sqlite_file(file_id: int, db: AsyncSession = Depends(get_db)):
  stmt = select(lite_relational.Document).where(lite_relational.Document.id == file_id)
  result = await db.execute(stmt)
  document = result.scalars().first()

  if not document:
    raise HTTPException(status_code=404, detail="Archivo no encontrado en la base de datos.")

  await db.delete(document)
  await db.commit()

  return JSONResponse(content={"message": "Archivo eliminado correctamente"})


@router_sources.get("/get_sqlite_file/{file_id}")
async def get_sqlite_file(file_id: int, db: AsyncSession = Depends(get_db)):
  stmt = select(lite_relational.Document).where(lite_relational.Document.id == file_id)
  result = await db.execute(stmt)
  document = result.scalars().first()

  if not document:
    raise HTTPException(status_code=404, detail="Documento no encontrado")

  return {
    "id": document.id,
    "name": document.name,
    "categoria": document.categoria,
    "descripcion": document.descripcion,
    "timestamp": str(document.timestamp)
  }


@router_sources.put("/update_sqlite_file/{file_id}")
async def update_sqlite_file(
  file_id: int,
  nombre: Optional[str] = Form(None),
  categoria: Optional[str] = Form(None),
  descripcion: Optional[str] = Form(None),
  db: AsyncSession = Depends(get_db),
):
  stmt = select(lite_relational.Document).where(lite_relational.Document.id == file_id)
  result = await db.execute(stmt)
  document = result.scalars().first()

  if not document:
    raise HTTPException(status_code=404, detail="Archivo no encontrado en la base de datos.")

  # Actualiza solo los campos que se reciben
  if nombre is not None:
    document.name = nombre
  if categoria is not None:
    document.categoria = categoria
  if descripcion is not None:
    document.descripcion = descripcion

  await db.commit()
  await db.refresh(document)

  return JSONResponse(content={
    "message": "Documento actualizado correctamente",
    "document": {
      "id": document.id,
      "name": document.name,
      "categoria": document.categoria,
      "descripcion": document.descripcion,
      "timestamp": str(document.timestamp)
    }
  })


@router_sources.post("/delete_databases")
async def delete_databases(request: Request):
  try:
    # Usa el manager de la app, NO uno nuevo: creando otro se borraba la
    # coleccion pero app.state.db_manager seguia con el ID viejo cacheado.
    manager = getattr(request.app.state, "db_manager", None) or DatabaseManager()

    manager.delete_milvus_collection()
    await manager.close_sqlalchemy_engine()
    manager.delete_sqlite_database()
    manager.delete_context_files()

    # Reconstruye manager y pipelines. NO se pueden dejar en None:
    # chat_zonia._serve_question lee app.state.runtime_pipeline directamente,
    # sin pasar por get_pipeline, y el chat reventaria con NoneType.
    from qa_docs.views.model_llm import preload_models
    request.app.state.db_manager = DatabaseManager()
    request.app.state.pipeline_cfg_hash = None
    await preload_models(request.app)

    context["collection_exists"] = False
    context["sources"] = []
    context["time_intervals"] = {}
    context["chat_items"] = []

    save_context()
    return JSONResponse(content={"message": "Bases de datos eliminadas exitosamente"}, status_code=200)

  except Exception as e:
    logger.info(f"❌ Error: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Error al eliminar bases de datos: {str(e)}")


@router_sources.post("/clear_sources_to_add")
def clear_sources_to_add():
  context["sources_to_add"] = []
  try:
    shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error al limpiar la carpeta: {str(e)}")

  return JSONResponse(
    content={"message": "Fuentes eliminadas correctamente", "sources_to_add": context["sources_to_add"]})


@router_sources.post("/restore_context_backup")
async def restore_context_backup():
  backup_file = CONTEXT_FILE.replace(".json", "_backup.json")

  if not os.path.exists(backup_file):
    raise HTTPException(status_code=404, detail="No se encontró backup disponible.")

  try:
    shutil.copy(backup_file, CONTEXT_FILE)
    return {"message": "✅ Context restaurado exitosamente desde backup."}
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"❌ Error restaurando backup: {str(e)}")
