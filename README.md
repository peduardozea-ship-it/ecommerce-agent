# Agente de IA para Ecommerce (RAG) — Claude + ChromaDB + LangChain LCEL + FastAPI

Agente conversacional que responde consultas de una tienda de ecommerce ficticia,
basándose en documentos propios (catálogo, políticas, FAQ) mediante RAG
(Retrieval-Augmented Generation).

**Stack:**
- LLM: Claude Sonnet (Anthropic), model ID `claude-sonnet-4-6`
- Embeddings: `all-MiniLM-L6-v2` (HuggingFace, corre localmente, sin costo de API)
- Vector store: ChromaDB (persistente en disco)
- Orquestación: LangChain LCEL
- API: FastAPI
- Despliegue: OCI Compute (Ubuntu)

---

## 1. Estructura del proyecto

```
ecommerce-agent/
├── app/
│   ├── __init__.py
│   ├── config.py        # Configuración (variables de entorno)
│   ├── ingest.py         # Script de ingesta de documentos -> ChromaDB
│   ├── rag_chain.py      # Cadena LCEL: retriever + prompt + Claude
│   └── main.py            # API FastAPI (endpoint /chat)
├── data/                  # <- aquí van tus documentos fuente (pdf, docx, txt, md)
├── chroma_db/             # (se genera automáticamente al correr ingest.py)
├── deploy/
│   ├── ecommerce-agent.service   # systemd para producción en OCI
│   └── nginx.conf                 # reverse proxy opcional
├── requirements.txt
└── .env.example
```

---

## 2. Preparación local (antes de subir a OCI)

### 2.1 Requisitos
- Python 3.11 (recomendado)
- Cuenta de Anthropic con API key (https://console.anthropic.com)

### 2.2 Crear entorno virtual e instalar dependencias

```bash
cd ecommerce-agent
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.3 Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y coloca tu `ANTHROPIC_API_KEY` real. El resto de valores por defecto
funcionan bien para empezar.

### 2.4 Cargar tus documentos

Coloca en la carpeta `data/` los documentos de tu tienda ficticia:
- Catálogo de productos
- Política de envíos
- Política de devoluciones/cambios
- Preguntas frecuentes (FAQ)
- Cualquier otro documento relevante (PDF, DOCX, TXT o MD)

### 2.5 Ejecutar la ingesta (crea el índice vectorial)

```bash
python -m app.ingest
```

Esto:
1. Carga y divide los documentos en fragmentos.
2. Genera embeddings localmente con `all-MiniLM-L6-v2` (la primera vez descarga
   el modelo desde HuggingFace, ~90 MB; luego queda cacheado).
3. Guarda todo en ChromaDB dentro de `chroma_db/`.

Debes volver a correr este script cada vez que cambies los documentos en `data/`.

### 2.6 Probar la API localmente

```bash
uvicorn app.main:app --reload --port 8000
```

Abre `http://localhost:8000/docs` para probar el endpoint `/chat` desde Swagger,
o con curl:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Cuánto tarda el envío a Guadalajara?", "session_id": "cliente-1"}'
```

---

## 3. Despliegue en OCI Compute (Ubuntu)

### 3.1 Crear la instancia
1. En la consola de OCI: **Compute > Instances > Create Instance**.
2. Imagen: **Canonical Ubuntu 22.04** (o 24.04).
3. Forma (shape): `VM.Standard.E4.Flex` con al menos 2 OCPU / 8 GB RAM
   (los embeddings locales usan CPU, no necesitas GPU).
4. Configura una clave SSH (o genera un par nuevo) para poder conectarte.
5. En **Networking**, asegúrate de que la instancia tenga una IP pública.

### 3.2 Abrir el puerto en el Security List / NSG de OCI
En la VCN de tu instancia, agrega una regla de ingreso:
- Protocolo: TCP
- Puerto: 80 (si usarás Nginx) y/o 8000 (si expones FastAPI directo, solo para pruebas)
- Origen: 0.0.0.0/0 (o restringe a IPs conocidas si es solo para pruebas del curso)

### 3.3 Conectarte por SSH

```bash
ssh -i tu-clave.pem ubuntu@IP_PUBLICA_DE_LA_INSTANCIA
```

### 3.4 Instalar dependencias del sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip git nginx
```

### 3.5 Subir tu proyecto a la instancia

Opción A (recomendada): sube tu proyecto a un repo de GitHub y clónalo:

```bash
git clone https://github.com/tu-usuario/ecommerce-agent.git
cd ecommerce-agent
```

Opción B: copia los archivos directamente desde tu máquina con `scp`:

```bash
scp -i tu-clave.pem -r ecommerce-agent ubuntu@IP_PUBLICA:/home/ubuntu/
```

### 3.6 Configurar entorno en la instancia

```bash
cd /home/ubuntu/ecommerce-agent
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env   # coloca tu ANTHROPIC_API_KEY real
```

Sube también la carpeta `data/` con tus documentos (o clónala si va en el repo),
y corre la ingesta ya en el servidor:

```bash
python -m app.ingest
```

### 3.7 Probar manualmente antes de dejarlo como servicio

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Desde tu máquina local: `curl http://IP_PUBLICA:8000/health` (requiere el puerto 8000 abierto).
Si responde, detén el proceso (Ctrl+C) y continúa para dejarlo corriendo de forma permanente.

### 3.8 Configurar el servicio systemd (para que corra siempre en segundo plano)

```bash
sudo cp deploy/ecommerce-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ecommerce-agent
sudo systemctl start ecommerce-agent
sudo systemctl status ecommerce-agent
```

Revisa el archivo `deploy/ecommerce-agent.service` antes: confirma que el `User`,
`WorkingDirectory` y la ruta de `venv/bin/uvicorn` coincidan con tu instancia.

Para ver logs en vivo:

```bash
sudo journalctl -u ecommerce-agent -f
```

### 3.9 (Recomendado) Configurar Nginx como reverse proxy

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/ecommerce-agent
sudo nano /etc/nginx/sites-available/ecommerce-agent   # ajusta server_name a tu IP o dominio
sudo ln -s /etc/nginx/sites-available/ecommerce-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Con esto tu API queda accesible en `http://IP_PUBLICA/chat` (puerto 80),
sin necesitar exponer el 8000 públicamente.

### 3.10 (Opcional) HTTPS con Let's Encrypt

Si tienes un dominio apuntando a la IP de tu instancia:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tu-dominio.com
```

---

## 4. Probar el agente ya desplegado

```bash
curl -X POST http://IP_PUBLICA_O_DOMINIO/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Tienen la política de devoluciones?", "session_id": "cliente-1"}'
```

---

## 5. Notas y buenas prácticas para la entrega del curso

- **Costos de API**: cada llamada a `/chat` consume tokens de Claude. Los embeddings
  son gratis porque corren localmente.
- **Actualizar la base de conocimiento**: solo vuelve a correr `python -m app.ingest`
  cada vez que cambien los documentos en `data/`.
- **Memoria de conversación**: el ejemplo guarda el historial en memoria del proceso
  (`_session_history` en `main.py`). Es suficiente para una demo/entrega de curso;
  para producción real conviene mover esto a Redis o una base de datos.
- **Seguridad**: nunca subas tu `.env` (con la API key real) a un repositorio público.
  Asegúrate de tener `.env` en tu `.gitignore`.
- **Escalado**: si tu curso pide manejar más carga, puedes aumentar `--workers` en
  el `ExecStart` del servicio systemd (cada worker carga su propio modelo de
  embeddings en memoria, así que vigila el RAM disponible).
