# LLM Inference Gateway

A cloud-native LLM inference API backed by Google Gemini. Runs on Kubernetes with full observability, CI/CD, and autoscaling — reproducible locally with `kind` in under 10 minutes.

![CI](https://github.com/hassanpro9/llm-inference-gateway/actions/workflows/ci.yaml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)

---

## Architecture

```
┌─────────────┐     POST /v1/chat      ┌──────────────────────┐
│   Client    │ ─────────────────────► │  FastAPI Gateway     │
└─────────────┘                        │  (llm-gateway pod)   │
                                       └──────────┬───────────┘
                                                  │
                              ┌───────────────────▼──────────────────────┐
                              │         Google Gemini 1.5 Flash API       │
                              └───────────────────────────────────────────┘
                                                  │
                         ┌────────────────────────▼──────────────────────┐
                         │              Observability                     │
                         │   Prometheus (/metrics)  →  Grafana Dashboard  │
                         └───────────────────────────────────────────────┘

Kubernetes (kind):
  Namespace: llm-gateway
  ├── Deployment (2 replicas, HPA up to 5)
  ├── Service (ClusterIP)
  ├── ConfigMap + Secret
  └── HorizontalPodAutoscaler

CI/CD (GitHub Actions):
  Push → lint → test → build → push to GHCR
```

---

## Features

- **OpenAI-compatible API** — `POST /v1/chat` with the same request/response shape as the OpenAI SDK
- **Google Gemini 1.5 Flash** — free tier, no credit card required
- **Multi-stage Dockerfile** — non-root user, minimal image (~200 MB)
- **Kubernetes-ready** — health probes, resource limits, pod anti-affinity, HPA
- **Prometheus metrics** — request rate, latency histograms, token usage counters
- **Grafana dashboard** — importable JSON, 5 panels covering the full observability story
- **GitHub Actions CI** — lint (ruff), pytest with mocked Gemini, build + push to GHCR
- **Fully local** — runs on `kind` with zero cloud cost

---

## Tech Stack

`Python 3.12` · `FastAPI` · `Docker` · `Kubernetes` · `kind` · `GitHub Actions` · `GHCR` · `Prometheus` · `Grafana` · `Google Gemini 1.5 Flash`

---

## Quickstart

See **[KIND_CLUSTER.md](KIND_CLUSTER.md)** for the full Kubernetes deployment guide.

### Local dev (docker compose)

```bash
git clone https://github.com/hassanpro9/llm-inference-gateway
cd llm-inference-gateway
cp .env.example .env          # add your GEMINI_API_KEY
docker compose up
```

The API, Prometheus, and Grafana all start together. Once the containers are up, verify everything is working:

**1. Check containers are running**
```bash
docker compose ps
# Should show: api, prometheus, grafana — all running
```

**2. Liveness probe**
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

**3. Readiness probe (confirms your API key is configured)**
```bash
curl http://localhost:8000/ready
# {"status":"ok","gemini_key_configured":true}
# Returns 503 if GEMINI_API_KEY is missing from .env
```

**4. Send a real chat request**
```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is Kubernetes in one sentence?"}]}'
```

**5. Check Prometheus is scraping**

Open http://localhost:9090 → **Status → Targets** — the `llm-gateway` job should show as UP.

**6. Check raw metrics**
```bash
curl http://localhost:8000/metrics
# Returns Prometheus text with llm_requests_total, llm_request_duration_seconds, etc.
```

**7. Grafana**

Open http://localhost:3000 — login `admin` / `admin`. Import `monitoring/grafana-dashboard.json` to get the full dashboard (+ → Import → upload file → select Prometheus datasource).

> Hot reload is enabled in docker compose — any change to `app/` is picked up instantly without restarting containers.

---

## API Reference

### `POST /v1/chat`

Request a completion from Gemini. Uses an OpenAI-compatible schema.

**Request**

```json
{
  "model": "gemini-2.5-flash",
  "messages": [
    { "role": "user", "content": "Explain Kubernetes in one sentence." }
  ],
  "max_tokens": 256
}
```

**Response**

```json
{
  "id": "a3f1c2d4-...",
  "object": "chat.completion",
  "model": "gemini-2.5-flash",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Kubernetes is a container orchestration platform..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 34,
    "total_tokens": 46
  }
}
```

**Other endpoints**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe — always 200 |
| `GET` | `/ready` | Readiness probe — 503 if no API key |
| `GET` | `/metrics` | Prometheus scrape endpoint |
| `GET` | `/docs` | Auto-generated Swagger UI |

**Example curl**

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

---

## Observability

Three Prometheus metrics tell the full inference story:

| Metric | Type | Labels |
|--------|------|--------|
| `llm_requests_total` | Counter | `model`, `status_code` |
| `llm_request_duration_seconds` | Histogram | `model` |
| `llm_tokens_used_total` | Counter | `model`, `type` (prompt / completion) |

Import `monitoring/grafana-dashboard.json` into Grafana to get:
- Requests per second
- Error rate (5xx)
- P50 / P95 / P99 latency
- Token usage rate
- Pod count

---

## Running Tests

```bash
pip install -r requirements.txt pytest pytest-asyncio
pytest tests/ -v
```

Tests mock all Gemini API calls — no real key needed.

---

## CI/CD Pipeline

Every push triggers:

1. **Lint** — `ruff check app/ tests/`
2. **Test** — `pytest tests/ -v`
3. **Build & push** — Docker image pushed to `ghcr.io/hassanpro9/llm-inference-gateway` on merge to `main`

See `.github/workflows/ci.yaml` and `cd.yaml`.

---

## What I Would Add in Production

- **Rate limiting per API key** — Redis-backed `slowapi` middleware
- **Authentication** — JWT or API key validation as a FastAPI dependency
- **Request/response caching** — semantic cache for repeated prompts
- **Multi-provider fallback** — Gemini → OpenAI → local model with circuit breaker
- **Cost tracking per tenant** — token usage aggregated by API key in a time-series store
- **Structured JSON logging** — with correlation IDs for distributed tracing
- **Helm chart** — parameterised multi-environment deployment
- **mTLS between pods** — via a service mesh (Istio / Linkerd)

---

## License

MIT
