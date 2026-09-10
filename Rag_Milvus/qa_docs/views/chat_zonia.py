# 📁 Rag_Milvus/qa_docs/views/chat_zonia.py
from __future__ import annotations

import asyncio
import os
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any

import orjson
from fastapi import (
  APIRouter,
  Depends,
  HTTPException,
  Request,
  WebSocket,
  WebSocketDisconnect,
  status,
)
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from rag.synthesizer.simple_stream import SimpleStreamResponse
from rag.synthesizer.types import StreamingResponse

from qa_docs import get_db
from qa_docs.db_relational import lite_relational
from qa_docs.db_relational.lite_relational import Session as SessionModel
from qa_docs.messages.message_zonia import Answer, Question
from qa_docs.tts.tts_stream_buffer import TTSStreamBuffer
from qa_docs.views.model_llm import (
  get_pipeline as get_pipeline_instance,
  get_qgen as get_qgen_pipeline_instance,
)

router_chat = APIRouter()

# ─────────────────────────────
# 🔧 Configuración y helpers
# ─────────────────────────────

MAX_QUERY_LEN = 1024  # bytes/caracteres por simplicidad

# Concurrencia del modelo – ajustable por entorno o núcleos CPU
LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", max(1, os.cpu_count() // 2)))
llm_sem = asyncio.Semaphore(LLM_CONCURRENCY)

# Cache para minimizar escrituras de keep‑alive
_ACTIVITY_CACHE: Dict[str, float] = {}
ACTIVITY_FLUSH_SECS = 30  # segundos


def oj(obj: Any) -> str:
  """Serializa a JSON rápido (orjson) y devuelve str."""
  return orjson.dumps(obj).decode()


# ─────────────────────────────
# Pydantic models
# ─────────────────────────────

from pydantic import BaseModel


class UserInput(BaseModel):
  session_uuid: str
  user_input: str
  document_id: int


class InitSessionInput(BaseModel):
  session_uuid: str


class FeedbackInput(BaseModel):
  question_id: int
  answer_id: int
  session_uuid: str


# ─────────────────────────────
# Listar documentos
# ─────────────────────────────


@router_chat.get("/list_documents")
async def list_documents(request: Request, db: AsyncSession = Depends(get_db)):
  pipeline = await get_pipeline_instance(request)
  docs = (await db.execute(select(lite_relational.Document))).scalars().all()
  return [
    {
      "id": d.id,
      "nombre": d.name,
      "categoria": d.categoria,
      "descripcion": d.descripcion,
      "indexado_en_milvus": pipeline.is_document_indexed(str(d.id)),
    }
    for d in docs
  ]


# ═════════════════════════════
# WebSocket principal
# ═════════════════════════════


@router_chat.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket, db: AsyncSession = Depends(get_db)):
  await ws.accept()
  ws.state.tts_buffer = None  # type: ignore[attr-defined]
  ws.state.tts_enabled = True  # type: ignore[attr-defined]
  ws.state.tarea_actual = None  # type: ignore[attr-defined]

  while ws.client_state == WebSocketState.CONNECTED:
    try:
      data = await ws.receive_json()
    except WebSocketDisconnect:
      break
    except Exception as e:
      await ws.send_text(oj({"type": "error", "data": f"JSON inválido: {e}"}))
      continue

    sid: str | None = data.get("session_uuid")
    did: int | None = data.get("document_id")
    q: str = (data.get("query") or "").strip()
    app_flags = ws.app.state.feature_flags
    tts_on: bool = data.get("tts_enabled", True) and app_flags.get("tts_active", True)
    generate_subqs: bool = data.get("generate_subquestions", True) and app_flags.get("subq_active", True)

    if not (sid and q and did is not None):
      await ws.send_text(oj({"type": "error", "data": "❌ Faltan datos."}))
      continue

    if len(q) > MAX_QUERY_LEN:
      await ws.send_text(oj({"type": "error", "data": "Consulta muy larga (+1 kB)"}))
      continue

    asyncio.create_task(_touch_session(db, sid, did))

    # UNA respuesta en vuelo por conexion. Antes se lanzaba la tarea sin mas y
    # dos preguntas solapadas escribian a la vez en el mismo WebSocket: los
    # trozos se entrelazaban y la respuesta salia cortada o mezclada.
    anterior = ws.state.tarea_actual
    if anterior and not anterior.done():
      anterior.cancel()
      await asyncio.gather(anterior, return_exceptions=True)

    if ws.state.tts_buffer:
      await ws.state.tts_buffer.cancel()
      ws.state.tts_buffer = None

    # Identifica la pregunta: el cliente descarta lo que llegue tarde de una
    # pregunta anterior en vez de pegarlo en la respuesta nueva.
    rid = str(data.get("request_id") or "").strip() or uuid.uuid4().hex
    ws.state.tarea_actual = asyncio.create_task(
      _serve_question(ws, sid, did, q, tts_on, generate_subqs, db, rid)
    )


# ─────────────────────────────
#  Lógica principal de respuesta
# ─────────────────────────────


async def _serve_question(
  ws: WebSocket,
  sid: str,
  did: int,
  query: str,
  tts_on: bool,
  generate_subqs: bool,
  db: AsyncSession,
  rid: str = "",
):
  app = ws.app.state
  async with llm_sem:
    try:
      resp, nodes = await asyncio.to_thread(
        app.runtime_pipeline.query_one, query, document_id=str(did)
      )
      is_blocked = isinstance(resp, SimpleStreamResponse)
    except Exception as e:
      await ws.send_text(oj({"type": "error", "data": str(e), "request_id": rid}))
      return

  ts = TTSStreamBuffer(ws, app.tts, enabled=tts_on, request_id=rid)
  ws.state.tts_buffer = ts
  texto_respuesta = await _stream_chunks(ws, resp, ts)
  qgen = await get_qgen_pipeline_instance(ws)
  asyncio.create_task(
    _log_to_sqlite(
      db,
      sid,
      query,
      texto_respuesta,
      did,
      nodes,
      qgen,
      ws,
      is_blocked,
      generate_subqs,
      rid,
    )
  )


async def _aiter_en_hilo(gen):
  """Consume un generador SINCRONO en un hilo y entrega los chunks al loop.

  Iterar `resp.response_gen` directamente dentro de la corrutina bloqueaba el
  event-loop en cada next() (lectura HTTP a Groq token a token). Con el loop
  bloqueado uvicorn no puede vaciar el buffer del WebSocket, asi que el texto
  se acumulaba y llegaba de golpe al final: parecia que no habia streaming.
  """
  cola: asyncio.Queue = asyncio.Queue()
  loop = asyncio.get_running_loop()
  FIN = object()

  def _bombear():
    try:
      for trozo in gen:
        loop.call_soon_threadsafe(cola.put_nowait, trozo)
    except Exception as exc:  # se re-lanza en el loop
      loop.call_soon_threadsafe(cola.put_nowait, exc)
    finally:
      loop.call_soon_threadsafe(cola.put_nowait, FIN)

  tarea = asyncio.create_task(asyncio.to_thread(_bombear))
  try:
    while True:
      item = await cola.get()
      if item is FIN:
        break
      if isinstance(item, Exception):
        raise item
      yield item
  finally:
    await tarea


async def _stream_chunks(ws: WebSocket, resp: Any, ts: TTSStreamBuffer) -> str:
  """Envía el stream al cliente y DEVUELVE el texto completo.

  Devolverlo es imprescindible: `str(resp)` sobre un StreamingResponse ya
  consumido recorre un generador agotado y acaba devolviendo la cadena
  literal "None" (ver StreamingResponse.__str__), asi que en SQLite se
  guardaba "None" como respuesta de cada pregunta.
  """
  partes: List[str] = []

  if isinstance(resp, (StreamingResponse, SimpleStreamResponse)):
    async for chunk in _aiter_en_hilo(resp.response_gen):
      if ws.application_state != WebSocketState.CONNECTED:
        break
      partes.append(chunk)
      await ts.process_chunk(chunk)
    await ts.flush()
  elif hasattr(resp, "__aiter__"):
    async for chunk in resp:
      if ws.application_state != WebSocketState.CONNECTED:
        break
      partes.append(chunk)
      await ws.send_text(chunk)
  elif isinstance(resp, str):
    partes.append(resp)
    await ws.send_text(resp)
  else:
    await ws.send_text(oj({"type": "error", "data": "⚠️ Respuesta no soportada."}))

  texto = "".join(partes)
  # Deja el texto cacheado en el propio objeto por si alguien hace str(resp).
  try:
    if getattr(resp, "response_txt", None) is None:
      resp.response_txt = texto
  except Exception:
    pass
  return texto


# ─────────────────────────────
#  Keep‑alive optimizado
# ─────────────────────────────


async def _touch_session(db: AsyncSession, sid: str, did: int):
  """Actualiza last_activity cada ACTIVITY_FLUSH_SECS segundos."""

  now = time.time()
  if now - _ACTIVITY_CACHE.get(sid, 0) < ACTIVITY_FLUSH_SECS:
    return
  _ACTIVITY_CACHE[sid] = now

  await db.execute(
    text(
      "UPDATE session "
      "SET last_activity = CURRENT_TIMESTAMP, document_id = :d "
      "WHERE session_id   = :s"
    ),
    {"s": sid, "d": did},
  )
  await db.commit()


# ─────────────────────────────
#  Logging y subpreguntas
# ─────────────────────────────

async def _log_to_sqlite(
  db: AsyncSession,
  sid: str,
  q: str,
  ans: str,
  did: int,
  nodes: List[Any],
  qgen,
  ws: WebSocket,
  is_blocked: bool,
  generate_subqs: bool,
  rid: str = "",
):
  async with db.begin():
    q_obj = lite_relational.Question(question=q)
    db.add(q_obj)
    await db.flush()
    a_obj = lite_relational.Answer(answer=ans)
    db.add(a_obj)
    await db.flush()
    db.add(
      lite_relational.Response(
        question_id=q_obj.id, answer_id=a_obj.id, document_id=did
      )
    )

  try:
    # Las fuentes ya estan listas: dependen de `nodes`, no del LLM. Antes se
    # enviaban DESPUES de generar las subpreguntas (otra llamada al LLM), asi
    # que el usuario terminaba de leer la respuesta y seguia esperando sin
    # fuentes y con el boton bloqueado. Se mandan de inmediato, junto con
    # "end" para liberar la interfaz.
    fuentes = Answer(message=ans, nodes=nodes).sources
    await ws.send_text(
      oj({"type": "metadata", "request_id": rid,
          "data": {"sources": fuentes, "subquestions": []}})
    )
    await ws.send_text(oj({"type": "end", "request_id": rid}))

    # Las subpreguntas llegan despues y actualizan el mismo mensaje. Se
    # reenvian las fuentes porque el frontend reescribe ambos campos.
    subqs: List[str] = []
    if generate_subqs and not is_blocked:
      subqs = await asyncio.to_thread(qgen.run, q, nodes)
      await ws.send_text(
        oj({"type": "metadata", "request_id": rid,
            "data": {"sources": fuentes, "subquestions": subqs}})
      )
    await ws.send_text(
      oj(
        {
          "type": "response_ids",
          "request_id": rid,
          "data": {"question_id": q_obj.id, "answer_id": a_obj.id},
        }
      )
    )
  except RuntimeError:
    pass


# ─────────────────────────────
#  REST endpoints (likes, etc.)
# ─────────────────────────────
@router_chat.post("/like_answer")
async def like_answer(data: FeedbackInput, db: AsyncSession = Depends(get_db)):
  stmt = select(lite_relational.Session).where(
    lite_relational.Session.session_id == data.session_uuid
  )
  session_obj = (await db.execute(stmt)).scalars().first()
  if not session_obj:
    raise HTTPException(status_code=404, detail="Sesión no encontrada")

  stmt = select(lite_relational.ResponseVote).where(
    lite_relational.ResponseVote.session_id == session_obj.id,
    lite_relational.ResponseVote.question_id == data.question_id,
    lite_relational.ResponseVote.answer_id == data.answer_id
  )
  if (await db.execute(stmt)).scalars().first():
    return {"status": "ok", "message": "Ya votaste por esta respuesta."}

  vote = lite_relational.ResponseVote(
    session_id=session_obj.id,
    question_id=data.question_id,
    answer_id=data.answer_id,
    is_like=True
  )
  resp = (await db.execute(select(lite_relational.Response).where(
    lite_relational.Response.question_id == data.question_id,
    lite_relational.Response.answer_id == data.answer_id
  ))).scalars().first()
  if not resp:
    raise HTTPException(status_code=404, detail="Respuesta no encontrada")

  db.add(vote)
  resp.likes += 1
  await db.commit()
  return {"status": "ok", "message": "👍 Like registrado"}


@router_chat.post("/dislike_answer")
async def dislike_answer(data: FeedbackInput, db: AsyncSession = Depends(get_db)):
  stmt = select(lite_relational.Session).where(
    lite_relational.Session.session_id == data.session_uuid
  )
  session_obj = (await db.execute(stmt)).scalars().first()
  if not session_obj:
    raise HTTPException(status_code=404, detail="Sesión no encontrada")

  stmt = select(lite_relational.ResponseVote).where(
    lite_relational.ResponseVote.session_id == session_obj.id,
    lite_relational.ResponseVote.question_id == data.question_id,
    lite_relational.ResponseVote.answer_id == data.answer_id
  )
  if (await db.execute(stmt)).scalars().first():
    return {"status": "ok", "message": "Ya votaste por esta respuesta."}

  resp = (await db.execute(select(lite_relational.Response).where(
    lite_relational.Response.question_id == data.question_id,
    lite_relational.Response.answer_id == data.answer_id
  ))).scalars().first()
  if not resp:
    raise HTTPException(status_code=404, detail="Respuesta no encontrada")

  vote = lite_relational.ResponseVote(
    session_id=session_obj.id,
    question_id=data.question_id,
    answer_id=data.answer_id,
    is_like=False
  )
  db.add(vote)
  resp.dislikes += 1
  await db.commit()
  return {"status": "ok", "message": "👎 Dislike registrado"}


@router_chat.post("/init_session")
async def init_session(payload: InitSessionInput, db: AsyncSession = Depends(get_db)):
  session_uuid = payload.session_uuid

  # Verificar si ya existe
  stmt = select(SessionModel).where(SessionModel.session_id == session_uuid)
  result = await db.execute(stmt)
  existing = result.scalars().first()
  if existing:
    return {
      "session_id": existing.id,
      "started_at": existing.started_at.isoformat(),
      "is_new": False
    }

  # Crear sesión sin documento aún
  new_session = SessionModel(
    session_id=session_uuid,
    document_id=None,
    started_at=datetime.utcnow(),
    last_activity=datetime.utcnow()
  )
  db.add(new_session)
  await db.commit()
  await db.refresh(new_session)

  return {
    "session_id": new_session.id,
    "started_at": new_session.started_at.isoformat(),
    "is_new": True
  }


class DocumentSelection(BaseModel):
  session_uuid: str
  document_id: int


@router_chat.post("/asociar_documento")
async def asociar_documento(payload: DocumentSelection, db: AsyncSession = Depends(get_db)):
  stmt = select(SessionModel).where(SessionModel.session_id == payload.session_uuid)
  result = await db.execute(stmt)
  session = result.scalars().first()

  if not session:
    raise HTTPException(status_code=404, detail="Sesión no encontrada")

  session.document_id = payload.document_id
  await db.commit()
  return {"status": "ok", "message": "Documento asociado a la sesión."}


@router_chat.post("/end_session")
async def end_session(payload: InitSessionInput, db: AsyncSession = Depends(get_db)):
  session_uuid = payload.session_uuid
  stmt = select(SessionModel).where(SessionModel.session_id == session_uuid)
  result = await db.execute(stmt)
  session = result.scalars().first()

  if not session:
    return {"status": "not_found", "message": "Sesión no encontrada."}

  return {
    "status": "deleted",
    "message": f"Sesión {session_uuid} finalizada y eliminada correctamente."
  }


@router_chat.get("/estado_sesion")
async def estado_sesion(session_uuid: str, db: AsyncSession = Depends(get_db)):
  stmt = select(SessionModel).where(SessionModel.session_id == session_uuid)
  result = await db.execute(stmt)
  session = result.scalars().first()

  if not session:
    return {"exists": False}

  return {
    "exists": True,
    "documento_seleccionado": session.document_id is not None,
    "document_id": session.document_id
  }


@router_chat.post("/keep_alive", status_code=status.HTTP_200_OK)
async def keep_alive(payload: InitSessionInput,
                     db: AsyncSession = Depends(get_db)) -> JSONResponse:
  stmt = select(SessionModel).where(SessionModel.session_id == payload.session_uuid)
  res = await db.execute(stmt)
  sess = res.scalar_one_or_none()
  if not sess:
    raise HTTPException(status_code=404, detail="Sesión no encontrada")

  sess.last_activity = datetime.utcnow()
  await db.commit()
  return JSONResponse({"status": "alive"})
