# AGENTS.md

This file provides practical guidance for coding agents working in this repository.

## Project overview

- Repo name: `llm_gateways`
- Primary language: Python (requires Python `>=3.13`)
- Package/dependency management: `uv` (preferred) or `pip`
- Main focus:
  - LLM gateway utility scripts
  - NewAPI gateway validation scripts
  - Benchmark stack under `benchmark/` (Mock upstream + NewAPI + Locust)

## Repository layout

- `test_chat.py`  
  Validates NewAPI `chat/completions` compatibility via OpenAI SDK.
- `openrouter.py`  
  Fetches OpenRouter model metadata filtered by provider.
- `max_latency_gemini.py` + `long_prompt_generator.py`  
  Builds huge prompts and measures Gemini high-thinking latency.
- `scripts/newapi_batch_accounts/`  
  Batch NewAPI account creation tooling.
- `docs/newapi-pricing-and-models.md`  
  NewAPI 模型计费、配额、渠道模型列表/映射与补全倍率说明（中文）。
- `benchmark/`  
  End-to-end load testing assets and operation docs.

## Environment setup

From repo root:

```bash
uv sync
```

If `uv` is unavailable:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Common run commands

### 1) Test NewAPI chat endpoint

```bash
python test_chat.py \
  --base-url https://your-newapi.example.com/v1 \
  --api-key "$NEWAPI_API_KEY" \
  --models your-model-name
```

Notes:
- You must provide at least one model (`--models` / `-m`).
- API key can also come from `NEWAPI_API_KEY` or `OPENAI_API_KEY`.

### 2) Fetch OpenRouter models by provider

```bash
export OPENROUTER_API_KEY=...
python openrouter.py "google,anthropic" --output models.json
```

### 3) Gemini latency probe with long prompt

```bash
export GEMINI_API_KEY=...
python max_latency_gemini.py
```

### 4) NewAPI batch account script

```bash
cd scripts/newapi_batch_accounts
python create_account.py --amount 10
```

Requires `NEWAPI_BASE_URL`, `NEWAPI_ADMIN_USERNAME`, `NEWAPI_ADMIN_PASSWORD`.

### 5) Benchmark docs

Start with:

- `benchmark/README.md`
- `benchmark/OPERATIONS.md`

## Validation guidance for agents

- For small changes, run the most relevant script directly (for example, `python test_chat.py ...`).
- For benchmarking-related changes, validate commands and configuration paths in docs:
  - `benchmark/mock/README.md`
  - `benchmark/locust/README.md`
  - `benchmark/OPERATIONS.md`
- If no automated test suite is present for your modified area, explicitly state what was manually verified.

## Coding and safety conventions

- Keep edits minimal and scoped to the task.
- Do not commit real API keys, tokens, passwords, or `.env` secrets.
- Prefer environment variables for credentials.
- Avoid unnecessary high-cost external API calls during validation unless required by the task.
- Preserve existing Chinese documentation style when editing files that are already Chinese-first.

## Agent workflow expectations

1. Read relevant files before editing.
2. Make focused changes.
3. Run targeted validation commands.
4. Summarize:
   - what changed,
   - how it was validated,
   - any remaining risks or assumptions.
