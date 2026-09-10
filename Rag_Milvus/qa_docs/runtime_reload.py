import asyncio
import inspect
from functools import wraps
from fastapi import Request
from qa_docs.views.model_llm import preload_models
import logging
logger = logging.getLogger(__name__)

_reload_lock = asyncio.Lock()
_reload_task = None
_reload_pending = False

# ✅ NUEVO: Invalidación manual del pipeline y hash en app.state
def _invalidate_pipeline(app):
  from qa_docs.db_relational.db_manager import DatabaseManager
  from qa_docs.views.model_llm import model_llm

  # 💥 Forzar recarga desde cero del manager + pipeline
  app.state.db_manager = DatabaseManager()  # ← fuerza nueva config
  app.state.runtime_pipeline = None
  app.state.qgen_pipeline = None
  app.state.pipeline_cfg_hash = None

  # 💥 También limpia globales
  model_llm._pipeline = None
  model_llm._cfg_hash = None


# ✅ Recarga consolidada con debounce
async def _debounced_reload(app, delay: float = 0.3):
    global _reload_task, _reload_pending

    if _reload_task and not _reload_task.done():
        _reload_pending = True
        return

    async def _run():
        await asyncio.sleep(delay)

        async with _reload_lock:
            _invalidate_pipeline(app)
            await preload_models(app)
            logger.info("♻️ Recarga consolidada ejecutada.")

        global _reload_pending
        _reload_pending = False

    _reload_task = asyncio.create_task(_run())

# ✅ Decorador auto_reload con recarga dinámica
def auto_reload(fn):
    sig = inspect.signature(fn)

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        response = await fn(*args, **kwargs)

        req = next((a for a in args if isinstance(a, Request)),
                   kwargs.get("request"))
        if req is None:
            raise RuntimeError("Request no encontrado")

        await _debounced_reload(req.app)
        return response

    wrapper.__signature__ = sig
    return wrapper
