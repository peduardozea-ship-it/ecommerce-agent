"""
API FastAPI que expone el Agente de IA de atención al cliente.

Endpoints:
  GET  /health         -> chequeo de salud del servicio
  POST /chat           -> envía un mensaje y recibe la respuesta del agente
"""
from collections import defaultdict
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field

from app.config import settings
from app.rag_chain import get_rag_chain

app = FastAPI(
    title=f"Agente de Atención al Cliente - {settings.store_name}",
    description="Agente de IA (RAG) para responder consultas de una tienda de ecommerce.",
    version="1.0.0",
)

# Ajusta esto en producción a los dominios reales de tu frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Historial en memoria por sesión (simple; para producción real usar Redis/DB)
_session_history: dict[str, List] = defaultdict(list)
MAX_HISTORY_TURNS = 6  # cuántos turnos previos se envían como contexto


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Mensaje del cliente")
    session_id: str = Field(default="default", description="Identificador de conversación")


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.get("/health")
def health():
    return {"status": "ok", "store": settings.store_name, "model": settings.claude_model}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    try:
        chain = get_rag_chain()
        history = _session_history[payload.session_id][-MAX_HISTORY_TURNS * 2 :]

        result = chain.invoke({"question": payload.message, "chat_history": history})

        # Actualiza el historial de la sesión
        _session_history[payload.session_id].append(HumanMessage(content=payload.message))
        _session_history[payload.session_id].append(AIMessage(content=result))

        return ChatResponse(reply=result, session_id=payload.session_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando respuesta: {e}")


@app.delete("/chat/{session_id}")
def reset_session(session_id: str):
    _session_history.pop(session_id, None)
    return {"status": "sesión reiniciada", "session_id": session_id}
