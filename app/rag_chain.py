"""
Cadena RAG (Retrieval-Augmented Generation) construida con LangChain LCEL.

import os

# Limita hilos de torch/tokenizers ANTES de importarlos: reduce picos de RAM,
# clave en entornos con memoria limitada como el plan free de Render.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

Flujo:
  pregunta del usuario
      -> retriever (ChromaDB + embeddings locales) busca los fragmentos relevantes
      -> se arma el prompt con el contexto recuperado + historial breve
      -> Claude Sonnet genera la respuesta amable y basada en los documentos
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_anthropic import ChatAnthropic

from app.config import settings

SYSTEM_PROMPT = f"""Eres el asistente virtual de atención al cliente de "{settings.store_name}",
una tienda de ecommerce. Tu trabajo es responder de forma amable, cercana y profesional
a las consultas de los clientes (pedidos, envíos, devoluciones, productos, políticas, etc.).

Reglas importantes:
- Responde SIEMPRE basándote en el CONTEXTO recuperado de la base de conocimiento a continuación.
- Si la información no está en el contexto, dilo con honestidad y ofrece derivar el caso
  a un agente humano; nunca inventes políticas, precios, plazos ni datos de productos.
- Usa un tono cálido, cordial y resolutivo, como lo haría un buen agente de soporte.
- Sé breve y claro; usa listas si ayuda a la comprensión.
- Responde en el mismo idioma en el que escribe el cliente.

CONTEXTO RECUPERADO:
{{context}}
"""


def _format_docs(docs) -> str:
    """Convierte los documentos recuperados en un bloque de texto legible para el prompt."""
    if not docs:
        return "No se encontró información relevante en la base de conocimiento."
    partes = []
    for i, d in enumerate(docs, start=1):
        fuente = d.metadata.get("source", "desconocida")
        partes.append(f"[Fragmento {i} - fuente: {fuente}]\n{d.page_content}")
    return "\n\n".join(partes)


def build_vectorstore() -> Chroma:
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.embeddings_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return Chroma(
        collection_name=settings.chroma_collection_name,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=embeddings,
    )


def build_rag_chain():
    """Construye y retorna la cadena LCEL completa, lista para invocar."""
    vectorstore = build_vectorstore()
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 4, "fetch_k": 10})

    llm = ChatAnthropic(
        model=settings.claude_model,
        api_key=settings.anthropic_api_key,
        temperature=0.3,
        max_tokens=1024,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{question}"),
        ]
    )

    # Cadena LCEL: recupera contexto en paralelo, arma el prompt, llama al LLM, parsea texto
    chain = (
        {
            "context": (lambda x: x["question"]) | retriever | RunnableLambda(_format_docs),
            "question": lambda x: x["question"],
            "chat_history": lambda x: x.get("chat_history", []),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain


# Instancia única (lazy) reutilizada por la API para no recargar el modelo en cada request
_rag_chain = None


def get_rag_chain():
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = build_rag_chain()
    return _rag_chain
