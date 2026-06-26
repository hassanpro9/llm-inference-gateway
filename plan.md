# LLM Inference Gateway — Portfolio Project Plan

A cloud-native LLM inference API, fully containerized and orchestrated on Kubernetes,
with CI/CD and observability. Designed to run locally and be reproducible by anyone
who clones the repo. No live infrastructure required after the demo.

---

## Goals

- Demonstrate AI workload deployment skills in a space that is actively hiring
- Produce three portfolio artifacts: a GitHub repo, a LinkedIn post, and a portfolio section
- Keep cost at zero, using local Kubernetes and free API tiers only
- Make the repo reproducible by anyone in under 10 minutes

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI (Python) | Industry standard for ML/AI APIs, async support, auto docs |
| LLM provider | Google Gemini 1.5 Flash | Free tier, no credit card, 15 RPM / 1M tokens per day |
| Containerization | Docker (multi-stage build) | Non-root user, minimal image size |
| Local Kubernetes | `kind` (Kubernetes in Docker) | Zero cost, runs anywhere Docker runs |
| Image registry | GitHub Container Registry (GHCR) | Free for public repos, no rate limits |
| CI/CD | GitHub Actions | Free for public repos |
| Monitoring | Prometheus + Grafana via Helm | Industry standard observability stack |
| Load testing | `k6` | Generate real-looking metrics for screenshots |

---

## Repository Structure

```
llm-inference-gateway/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── routers/
│   │   └── inference.py         # POST /v1/chat endpoint
│   ├── services/
│   │   └── gemini.py            # Gemini API client wrapper
│   ├── middleware/
│   │   └── metrics.py           # Prometheus instrumentation middleware
│   └── models/
│       └── schemas.py           # Pydantic request/response models
├── tests/
│   ├── test_inference.py        # Endpoint tests with mocked Gemini calls
│   └── conftest.py              # Pytest fixtures
├── k8s/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml              # Template only, values injected at deploy time
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── hpa.yaml                 # Horizontal Pod Autoscaler
├── monitoring/
│   ├── prometheus-values.yaml   # Helm values for kube-prometheus-stack
│   └── grafana-dashboard.json   # Importable dashboard definition
├── load-test/
│   └── smoke.js                 # k6 script for generating demo traffic
├── .github/
│   └── workflows/
│       ├── ci.yaml              # Lint, test, build, push image
│       └── cd.yaml              # kubectl apply on merge to main (optional/documented)
├── docker-compose.yml           # Local dev without Kubernetes
├── Dockerfile
├── requirements.txt
├── .env.example                 # Documents required env vars, no real values
├── KIND_CLUSTER.md              # Step-by-step: spin up local cluster and deploy
└── README.md
```

---

## Part 1 — The FastAPI Application

### 1.1 Endpoints

```
POST  /v1/chat      Request a completion from the LLM
GET   /health       Liveness probe (returns 200 immediately)
GET   /ready        Readiness probe (checks Gemini key is configured)
GET   /metrics      Prometheus scrape endpoint
GET   /docs         Auto-generated Swagger UI (FastAPI built-in)
```

The `/v1/chat` endpoint uses an OpenAI-compatible request/response shape.
This is intentional: it signals awareness of API design standards and makes
the gateway easy to swap with other providers.

### 1.2 Request / Response Schema

```json
// POST /v1/chat
// Request body
{
  "model": "gemini-1.5-flash",
  "messages": [
    { "role": "user", "content": "Explain Kubernetes in one sentence." }
  ],
  "max_tokens": 256
}

// Response
{
  "id": "a3f1c2d4-...",
  "model": "gemini-1.5-flash",
  "choices": [
    {
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

### 1.3 Prometheus Metrics to Expose

```python
# These three metrics tell the whole observability story for an inference API

llm_requests_total          # Counter, labels: model, status_code
llm_request_duration_seconds # Histogram, labels: model
llm_tokens_used_total       # Counter, labels: model, type (prompt / completion)
```

Expose these on `GET /metrics` using the `prometheus-client` Python library
via a middleware that wraps every request.

### 1.4 Environment Variables

```bash
# .env.example
GEMINI_API_KEY=your_key_here        # Required. Get from aistudio.google.com
DEFAULT_MODEL=gemini-1.5-flash      # Optional, defaults to this value
MAX_TOKENS=1024                      # Optional, defaults to 1024
LOG_LEVEL=info                       # Optional: debug | info | warning | error
```

---

## Part 2 — Dockerfile

Multi-stage build. Small final image. Non-root user. These three things matter
for a portfolio because they show you have thought about production concerns.

```dockerfile
# ---- Build stage ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN useradd -m -u 1001 appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY app/ ./app/

USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.1 docker-compose.yml (local dev, no Kubernetes)

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    env_file:
      - .env

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  grafana-data:
```

---

## Part 3 — Kubernetes Manifests

### 3.1 namespace.yaml

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: llm-gateway
```

### 3.2 secret.yaml (template, values injected at deploy time)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: llm-gateway-secrets
  namespace: llm-gateway
type: Opaque
stringData:
  GEMINI_API_KEY: "REPLACE_ME"   # kubectl create secret or CI injection
```

The README should instruct users to run:
```bash
kubectl create secret generic llm-gateway-secrets \
  --from-literal=GEMINI_API_KEY=your_key_here \
  -n llm-gateway
```

### 3.3 deployment.yaml

Key production-ready details to include:

- 2 replicas
- Resource requests and limits
- Liveness and readiness probes
- Secret injected as env var (never hardcoded)
- Pod anti-affinity (spread across nodes)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-gateway
  namespace: llm-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: llm-gateway
  template:
    metadata:
      labels:
        app: llm-gateway
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values: [llm-gateway]
                topologyKey: kubernetes.io/hostname
      containers:
        - name: llm-gateway
          image: ghcr.io/YOUR_GITHUB_USERNAME/llm-inference-gateway:latest
          ports:
            - containerPort: 8000
          env:
            - name: GEMINI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: llm-gateway-secrets
                  key: GEMINI_API_KEY
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "250m"
              memory: "256Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
```

### 3.4 hpa.yaml

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-gateway-hpa
  namespace: llm-gateway
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: llm-gateway
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
```

### 3.5 service.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: llm-gateway
  namespace: llm-gateway
spec:
  selector:
    app: llm-gateway
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

### 3.6 ingress.yaml

For a local `kind` cluster, use `kubectl port-forward` instead of a real ingress.
Include the ingress manifest anyway to show you know how it works in a real cluster.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: llm-gateway
  namespace: llm-gateway
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: llm-gateway.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: llm-gateway
                port:
                  number: 80
```

---

## Part 4 — CI/CD (GitHub Actions)

### 4.1 ci.yaml — triggers on every push and pull request

```yaml
name: CI

on:
  push:
    branches: ["*"]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt ruff pytest

      - name: Lint
        run: ruff check app/ tests/

      - name: Run tests
        run: pytest tests/ -v
        env:
          GEMINI_API_KEY: "test-key-not-real"  # tests mock the Gemini call

  build-and-push:
    needs: lint-and-test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
```

### 4.2 cd.yaml — documented but optional for local-only setup

Include this file with a comment block at the top explaining it targets a real
cluster (GKE, EKS, etc.) and that local deployment uses `KIND_CLUSTER.md` instead.
This shows you know what the full pipeline looks like without requiring live infra.

```yaml
# This workflow deploys to a real Kubernetes cluster.
# For local kind deployment, see KIND_CLUSTER.md.
# To enable: configure KUBE_CONFIG as a GitHub Actions secret.

name: CD

on:
  workflow_run:
    workflows: [CI]
    types: [completed]
    branches: [main]

jobs:
  deploy:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure kubectl
        uses: azure/k8s-set-context@v3
        with:
          kubeconfig: ${{ secrets.KUBE_CONFIG }}

      - name: Deploy
        run: |
          kubectl set image deployment/llm-gateway \
            llm-gateway=ghcr.io/${{ github.repository }}:${{ github.sha }} \
            -n llm-gateway
          kubectl rollout status deployment/llm-gateway -n llm-gateway
```

---

## Part 5 — Monitoring

### 5.1 Install kube-prometheus-stack via Helm

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values monitoring/prometheus-values.yaml
```

### 5.2 prometheus-values.yaml

```yaml
grafana:
  adminPassword: admin
  service:
    type: NodePort      # accessible on the kind cluster without ingress

prometheus:
  prometheusSpec:
    podMonitorSelectorNilUsesHelmValues: false
    serviceMonitorSelectorNilUsesHelmValues: false
```

### 5.3 Grafana Dashboard Panels

Build a dashboard with these panels and export the JSON to `monitoring/grafana-dashboard.json`:

| Panel | Type | Query |
|---|---|---|
| Requests per second | Time series | `rate(llm_requests_total[1m])` |
| Error rate | Stat | `rate(llm_requests_total{status_code=~"5.."}[5m])` |
| P50 / P95 / P99 latency | Time series | `histogram_quantile(0.95, rate(llm_request_duration_seconds_bucket[5m]))` |
| Total tokens used | Time series | `rate(llm_tokens_used_total[5m])` |
| Pod count | Stat | `kube_deployment_status_replicas{deployment="llm-gateway"}` |

### 5.4 Alerts

Add these to a `PrometheusRule` manifest in `k8s/`:

```yaml
groups:
  - name: llm-gateway
    rules:
      - alert: HighErrorRate
        expr: rate(llm_requests_total{status_code=~"5.."}[2m]) > 0.05
        for: 2m
        annotations:
          summary: "Error rate above 5% for 2 minutes"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(llm_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        annotations:
          summary: "P95 latency above 2 seconds"

      - alert: PodRestartLoop
        expr: rate(kube_pod_container_status_restarts_total{namespace="llm-gateway"}[10m]) > 0
        for: 10m
        annotations:
          summary: "Pod restarting repeatedly"
```

---

## Part 6 — Local Deployment Walkthrough (KIND_CLUSTER.md)

This is the file that lets anyone reproduce the full demo. Write it as a step-by-step guide.

### Prerequisites

```bash
# Install these tools
brew install kind kubectl helm k6   # macOS
# or use the official install docs for Linux/Windows
```

### Step 1 — Create the kind cluster

```bash
kind create cluster --name llm-gateway
kubectl cluster-info --context kind-llm-gateway
```

### Step 2 — Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/llm-inference-gateway
cd llm-inference-gateway
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

Get a free Gemini API key at: https://aistudio.google.com

### Step 3 — Build and load the image into kind

```bash
docker build -t llm-inference-gateway:local .
kind load docker-image llm-inference-gateway:local --name llm-gateway
```

### Step 4 — Deploy the app

```bash
kubectl apply -f k8s/namespace.yaml

# Create the secret with your real key
kubectl create secret generic llm-gateway-secrets \
  --from-literal=GEMINI_API_KEY=$(grep GEMINI_API_KEY .env | cut -d= -f2) \
  -n llm-gateway

kubectl apply -f k8s/
kubectl rollout status deployment/llm-gateway -n llm-gateway
```

### Step 5 — Test it

```bash
kubectl port-forward svc/llm-gateway 8080:80 -n llm-gateway

curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

### Step 6 — Install monitoring

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values monitoring/prometheus-values.yaml

# Access Grafana
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
# Open http://localhost:3000, login: admin / admin
# Import monitoring/grafana-dashboard.json
```

### Step 7 — Generate traffic for the demo screenshots

```bash
k6 run load-test/smoke.js
```

The `smoke.js` script should run 10 virtual users for 60 seconds hitting `POST /v1/chat`
with a simple prompt. This fills your Grafana charts with real-looking data for screenshots.

### Step 8 — Tear down

```bash
kind delete cluster --name llm-gateway
```

---

## Part 7 — Load Test Script (load-test/smoke.js)

```javascript
import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  vus: 10,
  duration: '60s',
};

export default function () {
  const payload = JSON.stringify({
    messages: [{ role: 'user', content: 'What is Kubernetes in one sentence?' }],
  });

  const params = { headers: { 'Content-Type': 'application/json' } };
  const res = http.post('http://localhost:8080/v1/chat', payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has choices': (r) => JSON.parse(r.body).choices !== undefined,
  });

  sleep(1);
}
```

---

## Part 8 — README Structure

Write the README in this order:

```
# LLM Inference Gateway

One-line description. One-line value prop.

## Architecture
[Mermaid diagram or Excalidraw screenshot]

## Features
- OpenAI-compatible REST API backed by Google Gemini 1.5 Flash
- Dockerized with multi-stage build and non-root user
- Kubernetes-ready with HPA, health probes, and resource limits
- CI via GitHub Actions: lint, test, build, push to GHCR
- Full observability: Prometheus metrics + Grafana dashboard
- Reproducible locally with kind in under 10 minutes

## Tech Stack
[Badges]

## Quickstart
[Link to KIND_CLUSTER.md]

## API Reference
[Endpoint table + example curl commands]

## Observability
[Screenshot of Grafana dashboard]

## CI/CD Pipeline
[Screenshot of GitHub Actions run]

## Running Tests
[pytest command]

## What I Would Add in Production
- Rate limiting per API key (e.g. with Redis + a FastAPI dependency)
- JWT or API key authentication middleware
- Request/response caching for repeated prompts
- Multi-provider fallback (Gemini -> OpenAI -> local model)
- Cost tracking per tenant
- Structured JSON logging with correlation IDs
- Helm chart for cleaner multi-environment deployment

## License
MIT
```

The "What I Would Add in Production" section is important. It shows seniority,
because you are not pretending this is production-ready, you are demonstrating
you know exactly what is missing and why.

---

## Part 9 — LinkedIn Post

**Hook (first two lines, visible before "see more"):**

> AI model deployment is the fastest-growing infrastructure problem right now.
> Here is how I built a production-style LLM inference gateway from scratch, fully on Kubernetes, with zero ongoing cost.

**Body:**

```
The project covers the full stack a team would actually need:

- FastAPI with an OpenAI-compatible /v1/chat endpoint backed by Google Gemini
- Multi-stage Dockerfile with a non-root user
- Kubernetes manifests with resource limits, health probes, and a Horizontal Pod Autoscaler
- GitHub Actions CI/CD: lint, test, build, push to GHCR on every merge
- Prometheus + Grafana for request rate, latency, and token usage

Everything runs locally on kind. Anyone can clone it, set a free Gemini API key,
and have the full stack running in under 10 minutes.

The repo includes a load test script to fill the Grafana dashboard with real traffic,
and a documented CD pipeline ready to point at GKE, EKS, or AKS.

Link in the comments.

#CloudEngineering #Kubernetes #DevOps #MLOps #LLM #SRE
```

**Visuals to attach:**
- Screenshot of the Grafana dashboard with live traffic
- Screenshot of the GitHub Actions CI pipeline (green)
- Architecture diagram

---

## Part 10 — Portfolio Section

**One paragraph + bullet stack + repo link:**

> Built a cloud-native LLM inference gateway to demonstrate production-style AI
> workload deployment. The service exposes an OpenAI-compatible REST API backed by
> Google Gemini 1.5 Flash, containerized with Docker, orchestrated on Kubernetes
> with autoscaling and full observability. CI via GitHub Actions builds and publishes
> the image to GHCR on every merge. The entire stack runs locally with kind and can
> be deployed to any CNCF-compliant cluster with no code changes.

**Stack line:**
`Python · FastAPI · Docker · Kubernetes · kind · GitHub Actions · GHCR · Prometheus · Grafana · Google Gemini`

**Links:** GitHub Repo ... Live Docs (Swagger UI via port-forward, screenshot)

---

## Estimated Build Time

| Phase | Estimated Time |
|---|---|
| FastAPI app + Gemini integration | 2-3h |
| Tests (with mocked Gemini calls) | 1h |
| Dockerfile + docker-compose | 1h |
| Kubernetes manifests | 2h |
| kind cluster setup + smoke test | 1h |
| GitHub Actions CI pipeline | 1-2h |
| Monitoring (Helm + dashboard) | 2h |
| Load test script + screenshots | 30min |
| README + KIND_CLUSTER.md | 1h |
| LinkedIn post + portfolio section | 30min |
| **Total** | **~12-13 hours** |

---

## Estimated Cost

| Resource | Cost |
|---|---|
| GKE / EKS / AKS | Not needed |
| Gemini API | Free (15 RPM, 1M tokens/day) |
| GitHub Actions | Free (public repo) |
| GHCR | Free (public repo) |
| Grafana Cloud | Not needed (runs in kind) |
| **Total** | **$0** |