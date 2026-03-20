# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

This is an LLM API Gateway toolkit (`llm_gateways`) — scripts and infrastructure for testing and benchmarking **NewAPI**, an OpenAI-compatible LLM gateway. See `README.md` and `benchmark/OPERATIONS.md` for full details.

### Development environment

- **Python 3.13** managed via `uv` (lockfile: `uv.lock`, config: `pyproject.toml`)
- Install/sync deps: `uv sync`
- Run scripts with: `uv run python <script.py>`

### Services

| Service | How to run | Port | Notes |
|---------|-----------|------|-------|
| Mock OpenAI server | `cd benchmark/mock && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000` | 8000 | Requires `fastapi` and `uvicorn` (`pip install -r benchmark/mock/requirements.txt`) |
| NewAPI + PostgreSQL + Redis | `docker run` commands (see below) | 3000 | Docker Compose `deploy` resource limits cause cgroup errors in nested containers |
| Locust load testing | `pip install -r benchmark/locust/requirements.txt && locust -f benchmark/locust/locustfile.py` | 8089 | Optional |

### Running NewAPI in Cloud Agent VMs (important gotcha)

The `benchmark/newapi/docker-compose.yml` uses `deploy.resources.limits` which fail in nested Docker (cgroup v2 errors). Run containers individually without resource limits:

```bash
docker network create new-api-network 2>/dev/null || true
docker run -d --name newapi-redis --network new-api-network redis:latest
docker run -d --name newapi-postgres --network new-api-network \
  -e POSTGRES_USER=root -e POSTGRES_PASSWORD=123456 -e POSTGRES_DB=new-api postgres:15
sleep 5
docker run -d --name new-api --network new-api-network -p 3000:3000 \
  -e "SQL_DSN=postgresql://root:123456@newapi-postgres:5432/new-api" \
  -e "REDIS_CONN_STRING=redis://newapi-redis" \
  -e "TZ=Asia/Shanghai" -e "ERROR_LOG_ENABLED=true" -e "BATCH_UPDATE_ENABLED=true" \
  calciumion/new-api:latest
```

Do **not** use `--log-dir /app/logs` flag — the directory doesn't exist in the container by default and causes a crash.

### NewAPI initial setup

- First registered user gets role=1 (normal). Promote to admin: `docker exec newapi-postgres psql -U root -d new-api -c "UPDATE users SET role=100 WHERE username='root';"`
- After login, the admin API requires a `New-Api-User: <user_id>` header alongside the session cookie.
- Enable self-use mode to bypass model pricing: `PUT /api/option/` with `{"key":"SelfUseModeEnabled","value":"true"}`.
- The mock server is reachable from Docker containers at `http://<docker-gateway-ip>:8000`. Get the gateway IP: `docker network inspect new-api-network -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}'`.

### Testing the gateway end-to-end

```bash
uv run python test_chat.py \
  --base-url http://localhost:3000/v1 \
  --api-key "sk-<your-token>" \
  --models mock-model \
  --max-tokens 16
```

### No lint or automated test suite

This repository has no linter config, no test framework, and no CI pipeline. Validation is done by running the scripts against live/mock services.
