# AttentionOS

AttentionOS is a persistent AI cognition system. It provides a modular backend for memory, reasoning, and orchestration, with a Next.js frontend for interaction.

## Repository structure

```
pool_of_thoughts/
├── backend/          # Python + FastAPI API
├── frontend/         # Next.js UI
└── docs/             # Architecture and design docs
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm

## Backend setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs  
Health check: http://localhost:8000/api/health

### Run backend tests

```bash
cd backend
pytest
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

## Tech stack

| Layer    | Technology              |
|----------|-------------------------|
| Backend  | Python, FastAPI         |
| Frontend | Next.js, TypeScript     |
| Database | SQLite (planned)        |
| LLMs     | Ollama (`gemma:2b` default) |

## Ollama configuration

Install [Ollama](https://ollama.com/) and pull the default model:

```bash
ollama pull gemma:2b
```

Optional environment variables (prefix `ATTENTIONOS_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ATTENTIONOS_OLLAMA_MODEL` | `gemma:2b` | Model name |
| `ATTENTIONOS_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `ATTENTIONOS_OLLAMA_TEMPERATURE` | `0.0` | Sampling temperature |
| `ATTENTIONOS_OLLAMA_MAX_RELATED_THOUGHTS` | `3` | Related thoughts cap |

Extract thoughts from raw input:

```bash
curl -X POST http://localhost:8000/api/cognition/extract \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"I need to finish the memory model draft\"}"
```

## Development notes

- No authentication in the initial scaffold.
- Keep modules focused: `cognitive`, `memory`, `models`, `api`, `services`.
- Backend CORS is configured for `http://localhost:3000`.
