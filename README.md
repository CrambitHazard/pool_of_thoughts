# Laguna

Laguna is a persistent AI cognition system. It provides a modular backend for memory, reasoning, and orchestration, with a Next.js frontend for interaction.

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

Set the backend URL for the UI:

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Use **Load Demo** in the UI to populate working memory without Ollama. Use **Inject** for LLM-backed thought extraction.

## Tech stack

| Layer    | Technology              |
|----------|-------------------------|
| Backend  | Python, FastAPI         |
| Frontend | Next.js, TypeScript     |
| Database | SQLite                  |
| LLMs     | Ollama (`gemma:2b` default) |

## Ollama configuration

Install [Ollama](https://ollama.com/) and pull the default model:

```bash
ollama pull gemma:2b
```

Optional environment variables (prefix `LAGUNA_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `LAGUNA_OLLAMA_MODEL` | `gemma:2b` | Model name |
| `LAGUNA_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `LAGUNA_OLLAMA_TEMPERATURE` | `0.0` | Sampling temperature |
| `LAGUNA_OLLAMA_MAX_RELATED_THOUGHTS` | `3` | Related thoughts cap |
| `LAGUNA_REFLECTION_INTERVAL_MINUTES` | `60.0` | Reflection loop interval |
| `LAGUNA_REFLECTION_LOOKBACK_HOURS` | `168.0` | Consolidation lookback window |

Extract thoughts from raw input:

```bash
curl -X POST http://localhost:8000/api/cognition/extract \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"I need to finish the memory model draft\"}"
```

## Internal agents

Laguna uses two LLM-backed internal agents:

| Agent | Module | Purpose |
|-------|--------|---------|
| Thought Extraction | `app/cognitive/prompts.py` | Parse raw input into structured thought objects |
| Consolidation | `app/cognitive/reflection_prompts.py` | Compress recurring episodic traces into semantic memory |

Shared prompt constraints live in `app/cognitive/prompt_context.py`.

## Development notes

- No authentication in the initial scaffold.
- Keep modules focused: `cognitive`, `memory`, `models`, `api`, `services`.
- Backend CORS is configured for `http://localhost:3000`.
