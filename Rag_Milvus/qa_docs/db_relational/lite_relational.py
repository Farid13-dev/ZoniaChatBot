from qa_docs import r_db
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
import asyncio
from qa_docs import app, context, r_db, DB_FOLDER
import os
from sqlalchemy import LargeBinary


class Document(r_db):
  __tablename__ = 'document'
  id = Column(Integer, primary_key=True)
  name = Column(String, nullable=False)
  categoria = Column(String, nullable=False)
  descripcion = Column(String, nullable=False)
  file_hash = Column(String, unique=True, nullable=False)  # 📌 Agregamos el hash
  timestamp = Column(DateTime, default=datetime.utcnow)
  file_data = Column(LargeBinary, nullable=True)


class Question(r_db):
  __tablename__ = 'question'
  id = Column(Integer, primary_key=True)
  question = Column(String, nullable=False)


class Answer(r_db):
  __tablename__ = 'answer'
  id = Column(Integer, primary_key=True)
  answer = Column(String, nullable=False)


class Response(r_db):
  __tablename__ = 'response'
  id = Column(Integer, primary_key=True)
  likes = Column(Integer, default=0)
  dislikes = Column(Integer, default=0)
  timestamp = Column(DateTime, default=datetime.utcnow)
  question_id = Column(Integer, ForeignKey("question.id"), nullable=False)
  answer_id = Column(Integer, ForeignKey("answer.id"), nullable=False)
  document_id = Column(Integer, ForeignKey("document.id"), nullable=False)

  question = relationship("Question")
  answer = relationship("Answer")
  document = relationship("Document")


class Session(r_db):
  __tablename__ = 'session'
  id = Column(Integer, primary_key=True)
  timestamp = Column(DateTime, default=datetime.utcnow)
  started_at = Column(DateTime, default=datetime.utcnow)  # Nunca cambia
  last_activity = Column(DateTime, default=datetime.utcnow)  # Se actualiza en cada mensaje
  session_id = Column(String, unique=True, nullable=False)  # UUID u otro identificador
  document_id = Column(Integer, ForeignKey("document.id"), nullable=True)

  document = relationship("Document")

class ResponseVote(r_db):
    __tablename__ = "response_vote"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("session.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False)
    answer_id = Column(Integer, ForeignKey("answer.id"), nullable=False)
    is_like = Column(Integer, nullable=False)  # 1 para like, 0 para dislike
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session")
    question = relationship("Question")
    answer = relationship("Answer")

