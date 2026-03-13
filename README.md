# LLM Gateways

> 这是一个构建 LLM API gateway 的工具集仓库，在这里你能找到操作和管理各类原厂模型并进行转发用于计费和管理的工具。

A **Python / FastAPI** toolset for building your own LLM API gateway.
Forward requests to multiple upstream LLM providers (OpenAI, Anthropic, …),
track usage, manage API keys, and attribute costs — all from a single endpoint.

---

## Features

| Feature | Description |
|---|---|
| **Unified endpoint** | One `POST /v1/chat/completions` speaks to every supported provider |
| **Provider adapters** | OpenAI and Anthropic out of the box; easily extensible |
| **API-key management** | Create, list, and revoke gateway keys via `/admin/keys` |
| **Usage & billing** | Per-key token and cost tracking stored in SQLite |
| **Streaming** | Full SSE streaming pass-through supported |
| **OpenAPI docs** | Auto-generated at `/docs` |

---

## Quick start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# edit .env — set ADMIN_API_KEY and optionally OPENAI_API_KEY / ANTHROPIC_API_KEY

# 3. Run
llm-gateway
# or:  uvicorn gateway.main:app --reload
```

The gateway listens on **http://0.0.0.0:8000** by default.

---

## Configuration

All settings are controlled via environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_HOST` | `0.0.0.0` | Bind address |
| `GATEWAY_PORT` | `8000` | Bind port |
| `ADMIN_API_KEY` | `change-me-admin-key` | Secret for `/admin/*` endpoints |
| `DATABASE_URL` | `./gateway.db` | Path to the SQLite file |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for local mocks |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Override for local mocks |
| `OPENAI_API_KEY` | _(empty)_ | Fallback key when caller doesn't supply one |
| `ANTHROPIC_API_KEY` | _(empty)_ | Fallback key when caller doesn't supply one |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## API

### Chat completions (OpenAI-compatible)

```http
POST /v1/chat/completions
Authorization: Bearer <gateway-key>
Content-Type: application/json

{
  "model": "gpt-4o-mini",
  "messages": [{"role": "user", "content": "Hello!"}]
}
```

To route to a specific provider, either:

* use the provider-scoped path: `POST /v1/anthropic/chat/completions`
* add `"provider": "anthropic"` to the JSON body
* use the `?provider=anthropic` query parameter

### Admin – key management

```bash
# Create a key
curl -X POST http://localhost:8000/admin/keys \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label": "my-service", "owner": "alice"}'

# List all keys
curl http://localhost:8000/admin/keys \
  -H "Authorization: Bearer $ADMIN_API_KEY"

# Revoke key #3
curl -X DELETE http://localhost:8000/admin/keys/3 \
  -H "Authorization: Bearer $ADMIN_API_KEY"
```

### Admin – usage

```bash
# All recent usage records
curl http://localhost:8000/admin/usage \
  -H "Authorization: Bearer $ADMIN_API_KEY"

# Usage summary for a specific key hash
curl http://localhost:8000/admin/usage/<key_hash> \
  -H "Authorization: Bearer $ADMIN_API_KEY"
```

---

## Supported providers

| Name | Chat | Completions | Embeddings | Models |
|---|---|---|---|---|
| `openai` | ✅ | ✅ | ✅ | ✅ |
| `anthropic` | ✅ (translated) | — | — | — |

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
ruff format --check .
```

---

## Project structure

```
gateway/
├── main.py            # FastAPI app & entrypoint
├── config.py          # Settings (pydantic-settings)
├── database.py        # SQLite schema & connection helpers
├── billing/
│   └── tracker.py     # Usage recording & cost calculation
├── middleware/
│   └── auth.py        # Gateway API-key auth
├── models/
│   ├── billing.py     # Pydantic models for usage/cost
│   └── keys.py        # Pydantic models for API keys
├── providers/
│   ├── base.py        # Abstract provider interface
│   ├── openai.py      # OpenAI adapter
│   ├── anthropic.py   # Anthropic adapter (with format translation)
│   └── registry.py    # Provider name → adapter mapping
└── routers/
    ├── admin.py        # /admin/* endpoints
    ├── chat.py         # /v1/chat/completions
    └── completions.py  # /v1/completions, /v1/embeddings, /v1/models
```

