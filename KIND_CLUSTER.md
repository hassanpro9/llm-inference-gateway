# Local Kubernetes Deployment with kind

Run the full LLM Inference Gateway stack locally — API, Prometheus, and Grafana — using `kind` (Kubernetes in Docker). No cloud account needed.

**Estimated time: ~10 minutes**

---

## Prerequisites

```bash
# macOS (Homebrew)
brew install kind kubectl helm k6

# Verify
kind version
kubectl version --client
helm version
k6 version
```

You also need **Docker Desktop** running.

Get a free Gemini API key (no credit card) at: https://aistudio.google.com

---

## Step 1 — Create the kind cluster

```bash
kind create cluster --name llm-gateway
kubectl cluster-info --context kind-llm-gateway
```

---

## Step 2 — Clone and configure

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/llm-inference-gateway
cd llm-inference-gateway

cp .env.example .env
# Open .env and set your GEMINI_API_KEY
```

---

## Step 3 — Build and load the image

```bash
docker build -t llm-inference-gateway:local .
kind load docker-image llm-inference-gateway:local --name llm-gateway
```

This loads the image directly into the kind cluster so Kubernetes can pull it without a registry.

---

## Step 4 — Deploy the application

```bash
# Create the namespace and config
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml

# Create the secret from your .env file (never commit the real secret.yaml)
kubectl create secret generic llm-gateway-secrets \
  --from-literal=GEMINI_API_KEY=$(grep GEMINI_API_KEY .env | cut -d= -f2) \
  -n llm-gateway

# Update the image name to the locally loaded image
# (Edit k8s/deployment.yaml: change the image to llm-inference-gateway:local)
# Then apply the rest of the manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Wait for pods to be ready
kubectl rollout status deployment/llm-gateway -n llm-gateway
```

Check pod status:

```bash
kubectl get pods -n llm-gateway
kubectl logs -l app=llm-gateway -n llm-gateway
```

---

## Step 5 — Test the API

In a separate terminal, start the port-forward:

```bash
kubectl port-forward svc/llm-gateway 8080:80 -n llm-gateway
```

Then send a request:

```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is Kubernetes in one sentence?"}]}'
```

Check the health endpoints:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/metrics
```

Swagger UI is available at: http://localhost:8080/docs

---

## Step 6 — Install monitoring (Prometheus + Grafana)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values monitoring/prometheus-values.yaml

# Wait for the stack to be ready (~2 minutes)
kubectl rollout status deployment/monitoring-grafana -n monitoring
```

Access Grafana:

```bash
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
```

Open http://localhost:3000 — login: `admin` / `admin`

**Import the dashboard:**
1. Click the **+** icon → **Import**
2. Upload `monitoring/grafana-dashboard.json`
3. Select your Prometheus datasource
4. Click **Import**

---

## Step 7 — Generate traffic for demo screenshots

Make sure the port-forward from Step 5 is still running, then:

```bash
k6 run load-test/smoke.js
```

This runs 10 virtual users for 60 seconds. After ~30 seconds you'll see live data in the Grafana charts.

To target a different URL:

```bash
BASE_URL=http://localhost:8080 k6 run load-test/smoke.js
```

---

## Step 8 — Tear down

```bash
kind delete cluster --name llm-gateway
```

This removes everything — the cluster, all pods, and the loaded images.

---

## Troubleshooting

**Pods stuck in `Pending`**

```bash
kubectl describe pod -l app=llm-gateway -n llm-gateway
```

Usually means the image wasn't loaded into kind. Re-run Step 3.

**`/ready` returns 503**

The `GEMINI_API_KEY` secret isn't set. Re-run the `kubectl create secret` command in Step 4.

**Gemini returns 429 (rate limit)**

The free tier allows 15 requests per minute. The load test includes `sleep(1)` to stay under this limit. If you still hit it, reduce the k6 `vus` to 5.

**Port already in use**

Change the local port in the port-forward command:
```bash
kubectl port-forward svc/llm-gateway 8081:80 -n llm-gateway
```
