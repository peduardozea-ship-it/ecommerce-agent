"""
Configuración centralizada del proyecto.
Lee variables desde el archivo .env usando pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Anthropic / Claude
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"

    # Documentos y vector store
    docs_path: str = "./data"
    chroma_persist_dir: str = "./chroma_db"
    chroma_collection_name: str = "ecommerce_kb"
    embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Identidad de la tienda
    store_name: str = "TiendaEjemplo"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
