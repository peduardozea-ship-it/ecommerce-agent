"""
Script de ingesta de documentos.

Uso:
    python -m app.ingest

Qué hace:
1. Carga todos los documentos soportados dentro de DOCS_PATH (pdf, docx, txt, md).
2. Los divide en fragmentos (chunks) manejables para el modelo.
3. Genera embeddings locales con HuggingFace (all-MiniLM-L6-v2, corre en CPU).
4. Los guarda de forma persistente en ChromaDB.

Puedes volver a correr este script cada vez que agregues o cambies documentos
en la carpeta data/. Por simplicidad, este script reconstruye la colección
desde cero en cada corrida (borra y vuelve a crear).
"""
import os
import shutil

from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from app.config import settings

# Mapeo de extensión -> loader de LangChain
LOADERS = {
    "*.pdf": PyPDFLoader,
    "*.docx": Docx2txtLoader,
    "*.txt": TextLoader,
    "*.md": UnstructuredMarkdownLoader,
}


def load_documents(docs_path: str):
    all_docs = []
    for pattern, loader_cls in LOADERS.items():
        loader = DirectoryLoader(
            docs_path,
            glob=pattern,
            loader_cls=loader_cls,
            show_progress=True,
            use_multithreading=True,
        )
        docs = loader.load()
        print(f"  {pattern}: {len(docs)} documento(s) cargado(s)")
        all_docs.extend(docs)
    return all_docs


def main():
    print(f"1) Cargando documentos desde: {settings.docs_path}")
    if not os.path.isdir(settings.docs_path) or not os.listdir(settings.docs_path):
        raise SystemExit(
            f"No se encontraron documentos en '{settings.docs_path}'. "
            "Coloca ahí tus PDFs/DOCX/TXT/MD antes de correr la ingesta."
        )

    raw_docs = load_documents(settings.docs_path)
    if not raw_docs:
        raise SystemExit("No se pudo cargar ningún documento soportado (pdf, docx, txt, md).")

    print(f"2) Dividiendo {len(raw_docs)} documento(s) en fragmentos (chunks)...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)
    print(f"   Total de fragmentos generados: {len(chunks)}")

    print(f"3) Cargando modelo de embeddings local: {settings.embeddings_model}")
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.embeddings_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # Reiniciar la colección para evitar duplicados en corridas repetidas
    if os.path.isdir(settings.chroma_persist_dir):
        print(f"4) Limpiando índice previo en {settings.chroma_persist_dir}...")
        shutil.rmtree(settings.chroma_persist_dir)

    print("5) Generando embeddings y guardando en ChromaDB (puede tardar unos minutos)...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=settings.chroma_collection_name,
        persist_directory=settings.chroma_persist_dir,
    )

    print("Listo. La base de conocimiento quedó indexada en:", settings.chroma_persist_dir)


if __name__ == "__main__":
    main()
