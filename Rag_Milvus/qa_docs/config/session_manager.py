# session_manager.py
from datetime import datetime, timedelta
from sqlalchemy import delete, select

from qa_docs.db_relational.lite_relational import Session as SessionModel


# ─────────── umbral único (1 min) ───────────
FINAL_SECONDS = 600
EXPIRATION    = timedelta(seconds=FINAL_SECONDS)


class SessionManager:
    def __init__(self, db):
        self.db = db

    async def manage_session_activity(
        self,
        session_uuid: str,
        document_id : int
    ) -> dict:
        """Devuelve info de la sesión o avisa si ya expiró."""
        now       = datetime.utcnow()
        cut_off   = now - EXPIRATION           # ← 60 s exactos

        # ¿existe la sesión?
        stmt   = select(SessionModel).where(SessionModel.session_id == session_uuid)
        result = await self.db.execute(stmt)
        session = result.scalars().first()

        if session:
            # ── comprobar expiración ──
            if session.last_activity < cut_off:
                print(f"🛑 Sesión expirada: {session.session_id}")

                # borra memoria + registro de sesión

                await self.db.execute(delete(SessionModel)
                                      .where(SessionModel.id == session.id))
                await self.db.commit()
                return {
                    "expired": True,
                    "error"  : "⚠️ Tu sesión ha finalizado por inactividad."
                }

            # actualización normal
            session.last_activity = now
            await self.db.commit()

        else:
            # ── crear nueva sesión ──
            session = SessionModel(
                session_id    = session_uuid,
                document_id   = document_id,
                started_at    = now,
                last_activity = now
            )
            self.db.add(session)
            await self.db.commit()

        # duración que se envía al front
        duration_seconds   = int((now - session.started_at).total_seconds())
        formatted_duration = f"{duration_seconds // 60}m {duration_seconds % 60:02d}s"

        return {
            "session_id" : session.id,
            "started_at" : session.started_at,
            "duration"   : formatted_duration,
            "expired"    : False
        }

    # # utilidades
    # async def delete_all_sessions(self):
    #     """Vacía sesiones y memorias (útil para pruebas)."""
    #     await self.db.execute(delete(ChatMemory))
    #     #await self.db.execute(delete(SessionModel))
    #     await self.db.commit()
