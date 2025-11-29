# Log Anomaly Detection System

Microservice-based real-time log anomaly detection system using GRU AutoEncoder and LLM-assisted anomaly explanation.

## Features

- **Multi-Domain Detection** — Supports HDFS, Hadoop, and OpenStack logs
- **Deep Learning Model** — GRU AutoEncoder with 93.41% detection accuracy
- **Real-time Streaming Pipeline** — Collector → Normalizer → Detector → Visualizer
- **LLM-Assisted Diagnosis** — Severity, root cause & recommendations
- **Kubernetes Deployable** — Scalable microservice architecture
- **LLM Queue Offloading** — Prevents model latency from slowing the pipeline

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Log Collector│───▶│  Normalizer  │───▶│   Detector   │───▶│  Visualizer  │
└──────────────┘    └──────────────┘    │ (GRU Model)  │    └─────┬────────┘
                                         │               │          │
                                         ▼               │
                                  ┌──────────────┐       │
                                  │ LLM Queue    │◀──────┘
                                  │ (FastAPI)    │
                                  └─────┬────────┘
                                        │
                                        ▼
                                ┌──────────────┐
                                │ LLM Service  │
                                │ (Model API)  │
                                └──────────────┘
```

---

## Services

| Service       | Role                               | Framework | Port |
|--------------|-------------------------------------|-----------|------|
| log-collector | Log streaming to Normalizer        | Flask     | 5000 |
| normalizer    | Event normalization & mapping      | Flask     | 5001 |
| detector      | GRU AutoEncoder anomaly detection  | Flask     | 5002 |
| visualizer    | Dashboard + event storage API      | Flask     | 8502 |
| **llm-queue** | Async queue to offload LLM calls   | FastAPI   | 8200 |
| llm-service   | Model inference & explanation      | FastAPI   | 8000 |

---

## Quick Start

### Prerequisites
- Docker
- Minikube
- kubectl
- Make

### Installation

```bash
minikube start --memory=4096 --cpus=4
git clone <repository-url>
cd AnomalyDetector
make build
make deploy
```

### Status & Logs

```bash
make status
make logs-all
```

### Port Forwarding (Optional)

```bash
kubectl port-forward svc/visualizer-service 8502:8502
kubectl port-forward svc/llm-queue-service 8200:8200
kubectl port-forward svc/llm-service 8000:8000
```

---

## API Usage

### Visualizer (Events & Dashboard)

```bash
curl http://localhost:8502/statistics | python3 -m json.tool
curl http://localhost:8502/anomalies?limit=5 | python3 -m json.tool
```

### LLM Queue API

```bash
curl http://localhost:8200/queue
```

### LLM Service Debug

```bash
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{"log":{"message":"ERROR: timeout","loss":0.0021,"threshold":0.001},"status":"anomaly"}'
```

---

## Makefile Commands

```bash
make build          # Build Docker images
make deploy         # Deploy all services to K8s
make restart        # Restart pods
make clean          # Delete all resources
make logs-all       # View all service logs
make logs-detector  # View only detector logs
make status         # Check pods, services & configmaps
```

---

## Model Information

- **Model**: Multi-domain GRU AutoEncoder
- **Events Parsed**: 767
- **Accuracy**: 93.41%
- **Precision**: 92.95%
- **Recall**: 21.05%
- **Threshold**: 0.001
- **Max Sequence Length**: 50

---

## Project Structure

```
AnomalyDetector/
├── services/
│   ├── log-collector/
│   ├── normalizer/
│   ├── detector/
│   ├── visualizer/
│   ├── llm-queue/         # NEW — async queue for LLM
│   └── llm-service/       # FastAPI-based LLM inference
├── k8s/
├── models/
├── training/
├── data/
└── Makefile
```

---

## License

MIT