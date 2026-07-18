# Chatbot de PM Soluciones Tecnológicas — Agente de IA para Ecommerce (RAG)

## 1. Descripción general del proyecto

Este proyecto implementa un **Agente de Inteligencia Artificial** capaz de responder, de
forma amable y profesional, las consultas de los clientes de **PM Soluciones Tecnológicas**,
una tienda de ecommerce ficticia.

El agente utiliza la técnica de **RAG (Retrieval-Augmented Generation)**: en lugar de que el
modelo de lenguaje "invente" respuestas, primero busca la información relevante dentro de una
base de conocimiento construida a partir de documentos propios de la tienda (políticas de
envío, devoluciones, privacidad, garantías, catálogo, preguntas frecuentes, etc.), y luego
genera una respuesta basada exclusivamente en ese contenido. Esto reduce alucinaciones y
asegura que el agente responda siempre alineado a las políticas reales del negocio.

El sistema queda expuesto como una **API REST (FastAPI)** y también cuenta con una
**interfaz de chat web** lista para que cualquier cliente interactúe con el agente desde el
navegador, sin necesidad de herramientas técnicas.

El proyecto está desplegado en **dos entornos de producción distintos**:
- **Oracle Cloud Infrastructure (OCI) Compute** — servidor Ubuntu corriendo el servicio de forma permanente vía `systemd`.
- **Render** — plataforma PaaS con despliegue automático desde GitHub.

---

## 2. Arquitectura de la solución

### 2.1 Diagrama de flujo

```
                     ┌─────────────────────────────┐
                     │   Documentos de la tienda    │
                     │  (PDF, DOCX, TXT, MD, CSV)   │
                     └───────────────┬───────────────┘
                                     │  app/ingest.py
                                     │  (carga + chunking)
                                     ▼
                     ┌─────────────────────────────┐
                     │  Embeddings locales          │
                     │  all-MiniLM-L6-v2 (HF)       │
                     └───────────────┬───────────────┘
                                     ▼
                     ┌─────────────────────────────┐
                     │        ChromaDB              │
                     │   (vector store persistente) │
                     └───────────────┬───────────────┘
                                     │  retriever (búsqueda semántica)
                                     ▼
   Usuario ──POST /chat──▶  FastAPI  ──▶  Cadena LangChain LCEL
   (chat web o API)                        │  1. recupera contexto relevante
                                            │  2. arma el prompt con el contexto
                                            │  3. invoca a Claude Sonnet (Anthropic)
                                            ▼
                                   Respuesta generada
                                            │
   Usuario ◀────────── JSON { reply, session_id } ──┘
```

### 2.2 Componentes principales

| Componente | Responsabilidad |
|---|---|
| `app/ingest.py` | Lee los documentos fuente, los divide en fragmentos (chunks) y genera su representación vectorial (embeddings), guardándolos en ChromaDB. |
| `app/rag_chain.py` | Define la cadena LCEL: recupera los fragmentos más relevantes para la pregunta del usuario, arma el prompt de sistema y llama a Claude Sonnet para generar la respuesta final. |
| `app/main.py` | Expone la API con FastAPI (`/chat`, `/health`) y sirve la interfaz web de chat (`/`). Mantiene un historial de conversación por sesión. |
| `app/config.py` | Centraliza la configuración del proyecto a través de variables de entorno (`.env`). |
| `app/static/index.html` | Interfaz de chat web (HTML/CSS/JS) que consume el endpoint `/chat`. |
| `data/` | Documentos fuente de la tienda que alimentan la base de conocimiento. |
| `chroma_db/` | Base de datos vectorial persistente generada por la ingesta (no se versiona en Git). |
| `deploy/` | Archivos de configuración para el despliegue en OCI (`systemd`, `nginx`). |
| `render.yaml` | Configuración de despliegue automatizado (Infrastructure as Code) para Render. |

---

## 3. Tecnologías y herramientas utilizadas

- **Lenguaje**: Python 3.11
- **LLM**: [Claude Sonnet](https://www.anthropic.com) (Anthropic) — modelo `claude-sonnet-4-6`, vía API
- **Embeddings**: `all-MiniLM-L6-v2` (HuggingFace `sentence-transformers`), ejecutado **localmente** (sin costo de API, sin enviar los documentos a terceros)
- **Vector store**: [ChromaDB](https://www.trychroma.com/) (persistente en disco)
- **Orquestación del agente**: [LangChain](https://www.langchain.com/) con **LCEL** (LangChain Expression Language)
- **Framework de API**: [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn
- **Frontend**: HTML, CSS y JavaScript nativo (sin frameworks), interfaz de chat conectada vía `fetch` al backend
- **Procesamiento de documentos**: `pypdf` (PDF), `python-docx` (Word), `unstructured` (Markdown), soporte nativo para CSV/TXT
- **Control de versiones**: Git + GitHub (repositorio privado)
- **Despliegue**:
  - **OCI Compute** (instancia Ubuntu 22.04, arquitectura ARM/Ampere), servicio administrado con `systemd`, expuesto mediante reglas de Security List + `iptables`
  - **Render** (Web Service, plan free), despliegue continuo desde GitHub vía `render.yaml`

---

## 4. Instrucciones para ejecutar el proyecto

### 4.1 Ejecución en local

**Requisitos:** Python 3.11, una API key de Anthropic ([console.anthropic.com](https://console.anthropic.com)).

```bash
# 1. Clonar el repositorio
git clone https://github.com/peduardozea-ship-it/ecommerce-agent.git
cd ecommerce-agent

# 2. Crear y activar entorno virtual
python3.11 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y colocar tu ANTHROPIC_API_KEY real

# 5. Colocar los documentos fuente de la tienda en la carpeta data/
#    (PDF, DOCX, TXT, MD o CSV)

# 6. Generar la base de conocimiento vectorial
python -m app.ingest

# 7. Levantar el servidor
uvicorn app.main:app --reload --port 8000
```

Una vez levantado, la aplicación queda disponible en:
- **Interfaz de chat web**: `http://localhost:8000/`
- **Documentación interactiva de la API (Swagger)**: `http://localhost:8000/docs`
- **Endpoint de salud**: `http://localhost:8000/health`

### 4.2 Despliegue en producción

El proyecto incluye:
- `deploy/ecommerce-agent.service` — unidad de `systemd` para mantener el servicio activo de forma permanente en un servidor Ubuntu (usado en OCI Compute).
- `deploy/nginx.conf` — configuración de reverse proxy opcional.
- `render.yaml` — configuración de despliegue automatizado para Render (build, start command y variables de entorno).

Instrucciones detalladas paso a paso para ambos entornos están documentadas dentro de cada archivo de configuración correspondiente.

### 4.3 Endpoints disponibles

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz de chat web |
| `GET` | `/health` | Verifica que el servicio esté activo |
| `POST` | `/chat` | Envía un mensaje al agente y recibe su respuesta |
| `DELETE` | `/chat/{session_id}` | Reinicia el historial de una sesión de conversación |

Ejemplo de petición a `/chat`:
```json
POST /chat
{
  "message": "¿Cuál es la política de devoluciones?",
  "session_id": "cliente-1"
}
```

Respuesta:
```json
{
  "reply": "¡Hola! Con gusto te comento sobre nuestra política de devoluciones...",
  "session_id": "cliente-1"
}
```

---

## 5. Ejemplos de preguntas que el agente puede responder

- ¿Cuál es la política de devoluciones y en cuántos días puedo solicitarla?
- ¿Hacen envíos a todo el país? ¿Cuánto tarda en llegar mi pedido?
- ¿Qué métodos de pago aceptan?
- ¿Cómo protegen mis datos personales al hacer una compra?
- ¿Tienen garantía los productos? ¿Cómo la hago válida?
- ¿Puedo cancelar un pedido después de haberlo realizado?
- ¿Cuál es el costo de envío para mi ciudad?
- ¿Qué hago si mi producto llegó dañado?

---

## 6. Ejemplos de respuestas generadas por el agente

**Pregunta:**
> ¿Cuál es la política de devoluciones?

**Respuesta del agente:**
> ¡Hola! Con gusto te explico. En PM Soluciones Tecnológicas puedes solicitar la devolución
> de tu producto dentro de los días establecidos en nuestra política, siempre que se
> encuentre en las condiciones indicadas (empaque original, sin uso, con todos sus
> accesorios). Para iniciar el proceso, solo necesitas contactarnos con tu número de pedido
> y el motivo de la devolución. Si tienes alguna duda adicional sobre tu caso en particular,
> aquí estoy para ayudarte. 😊

**Pregunta:**
> ¿Hacen envíos a todo el país?

**Respuesta del agente:**
> ¡Claro que sí! Realizamos envíos a nivel nacional según lo indicado en nuestra guía de
> envíos y entrega. El tiempo de entrega puede variar dependiendo de tu ubicación y del
> método de envío seleccionado al momento de la compra. Si me compartes tu ciudad, puedo
> darte una referencia más precisa del tiempo estimado.

**Pregunta:**
> ¿Cómo manejan la privacidad de mis datos?

**Respuesta del agente:**
> Tu privacidad es muy importante para nosotros. De acuerdo con nuestra política de
> privacidad, tus datos personales se utilizan únicamente para procesar tu compra, gestionar
> el envío y brindarte soporte — nunca los compartimos con terceros sin tu consentimiento.
> Si deseas más detalles sobre cómo tratamos tu información específicamente, con gusto te
> amplío el tema.

> **Nota:** las respuestas exactas del agente dependerán del contenido real de los
> documentos cargados en la carpeta `data/`, ya que el agente responde basándose
> exclusivamente en esa información (nunca inventa políticas, precios o plazos). Se
> recomienda reemplazar estos ejemplos por interacciones reales capturadas desde el
> chatbot desplegado, a modo de evidencia para la entrega.

---

## 7. Notas adicionales

- **Seguridad**: el archivo `.env` (con la API key real) nunca se sube al repositorio; está excluido vía `.gitignore`. El repositorio incluye `.env.example` como plantilla.
- **Actualización de la base de conocimiento**: basta con reemplazar/agregar archivos en `data/` y volver a correr `python -m app.ingest`.
- **Optimización de memoria**: para entornos con recursos limitados (como el plan gratuito de Render), el proyecto instala una versión de `torch` optimizada para CPU (`torch==2.4.1+cpu`) y limita la paralelización interna de hilos, reduciendo significativamente el consumo de RAM sin afectar la calidad de las respuestas.
