# Log Anomaly Detection System

Microservice-based real-time log anomaly detection system using GRU AutoEncoder.

## Features

- **Multi-Domain Detection**: Supports HDFS, Hadoop, and OpenStack logs
- **Deep Learning Model**: GRU AutoEncoder with 93.41% accuracy
- **Real-time Processing**: Continuous log streaming and analysis
- **Pattern Explanation**: Automated anomaly explanation and recommendations
- **Kubernetes Deployment**: Scalable microservice architecture

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│              │    │              │    │              │    │              │
│ Log Collector│───▶│  Normalizer  │───▶│   Detector   │───▶│  Visualizer  │
│              │    │              │    │ (GRU Model)  │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                │
                                                ▼
                                        ┌──────────────┐
                                        │              │
                                        │ LLM Service  │
                                        │              │
                                        └──────────────┘
```

**Services:**
- **log-collector**: Reads log files and sends to normalizer
- **normalizer**: Converts logs to event sequences
- **detector**: GRU AutoEncoder model for anomaly detection
- **visualizer**: Stores results and provides REST API
- **llm-service**: Generates explanations for detected anomalies

## Quick Start

### Prerequisites

- Minikube
- Docker
- kubectl

### Installation

```bash
# Start Minikube
minikube start --memory=4096 --cpus=4

# Clone repository
git clone <repository-url>
cd AnomalyDetector

# Build images
make build

# Deploy to Kubernetes
make deploy
```

### Check Status

```bash
# View pod status
make status

# View logs
make logs-all
```

## Usage

### API Endpoints

**Visualizer (port 8502):**
```bash
# Get statistics
curl http://localhost:8502/statistics | python3 -m json.tool

# Get anomalies
curl "http://localhost:8502/anomalies?limit=5" | python3 -m json.tool
```

**LLM Service (port 8000):**
```bash
# Get anomaly explanation
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{
    "log": {
      "message": "ERROR: Connection timeout for block blk_12345",
      "loss": 0.002109,
      "threshold": 0.001000
    },
    "status": "anomaly"
  }' | python3 -m json.tool
```

### Port Forwarding

```bash
# Visualizer
kubectl port-forward svc/visualizer-service 8502:8502

# LLM Service
kubectl port-forward svc/llm-service 8000:8000
```

## Makefile Commands

```bash
make build        # Build all Docker images
make deploy       # Deploy to Kubernetes
make clean        # Delete all resources
make restart      # Restart all pods
make logs         # View detector logs
make logs-all     # View all service logs
make status       # Check system status
make test         # Run system test
```

## Model Details

- **Architecture**: Multi-domain GRU AutoEncoder
- **Vocabulary**: 767 events (HDFS, Hadoop, OpenStack)
- **Performance**:
  - Accuracy: 93.41%
  - Precision: 92.95%
  - Recall: 21.05%
- **Threshold**: 0.001000 (adjustable)

## Tech Stack

- **ML Framework**: PyTorch
- **Log Parsing**: Drain3
- **Backend**: Flask (Python 3.9)
- **Container**: Docker
- **Orchestration**: Kubernetes (Minikube)
- **Training**: Google Colab (T4 GPU)

## Project Structure

```
AnomalyDetector/
├── services/           # Microservices
│   ├── log-collector/
│   ├── normalizer/
│   ├── detector/
│   ├── visualizer/
│   └── llm-service/
├── k8s/               # Kubernetes configs
├── training/          # Model training notebooks
├── models/            # Trained models
├── data/              # Log data
└── Makefile           # Build automation
```

## Development

### Training New Model

1. Open `training/train_multi_domain_augmented.ipynb` in Google Colab
2. Upload training data
3. Run all cells
4. Download trained model files to `models/`

### Modifying Configuration

Edit `k8s/configmap.yaml`:
```yaml
data:
  LOG_FILE: "/data/HDFS_2k.log"
  BATCH_SIZE: "5"
  DELAY: "1.0"
  MAX_SEQUENCE_LENGTH: "50"
```

Apply changes:
```bash
kubectl apply -f k8s/configmap.yaml
kubectl rollout restart deployment/log-collector
```

## License

MIT
