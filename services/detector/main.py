"""
Anomaly Detector Service
통합 LSTM/GRU AutoEncoder 모델을 사용한 이상 탐지
"""
import os
from flask import Flask, request, jsonify
import torch
import torch.nn as nn
import joblib
import numpy as np
import requests
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from collections import deque

app = Flask(__name__)

# 환경 변수
VISUALIZER_URL = os.getenv("VISUALIZER_URL", "http://visualizer-service:8502/event")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm-service:8000/explain")
MODEL_DIR = os.getenv("MODEL_DIR", "/models")
MAX_SEQUENCE_LENGTH = int(os.getenv("MAX_SEQUENCE_LENGTH", "20"))

# 모델 타입 (lstm 또는 gru)
MODEL_TYPE = os.getenv("MODEL_TYPE", "lstm")


class UnifiedLSTMAutoEncoder(nn.Module):
    """통합 LSTM 기반 시계열 AutoEncoder"""

    def __init__(self, input_dim, hidden_dim=256, num_layers=2, dropout=0.1, use_gru=False):
        super(UnifiedLSTMAutoEncoder, self).__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.use_gru = use_gru

        if use_gru:
            self.encoder = nn.GRU(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0,
                batch_first=True
            )
            self.decoder = nn.GRU(
                input_size=hidden_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0,
                batch_first=True
            )
        else:
            self.encoder = nn.LSTM(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0,
                batch_first=True
            )
            self.decoder = nn.LSTM(
                input_size=hidden_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0,
                batch_first=True
            )

        self.output_layer = nn.Sequential(
            nn.Linear(hidden_dim, input_dim),
            nn.Sigmoid()
        )

    def forward(self, x):
        if self.use_gru:
            encoded, h_n = self.encoder(x)
            last_hidden = h_n[-1].unsqueeze(1).repeat(1, x.size(1), 1)
            decoded, _ = self.decoder(last_hidden)
        else:
            encoded, (h_n, c_n) = self.encoder(x)
            last_hidden = h_n[-1].unsqueeze(1).repeat(1, x.size(1), 1)
            decoded, _ = self.decoder(last_hidden)

        output = self.output_layer(decoded)
        return output


# GRU AutoEncoder 정의 (HDFS_v1용)
class GRUAutoEncoder(nn.Module):
    """GRU 기반 시퀀스 AutoEncoder (HDFS_v1)"""
    def __init__(self, input_dim, hidden_dim=128, num_layers=2, dropout=0.1):
        super(GRUAutoEncoder, self).__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.encoder = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )

        self.decoder = nn.GRU(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )

        self.output_layer = nn.Sequential(
            nn.Linear(hidden_dim, input_dim),
            nn.Sigmoid()
        )

    def forward(self, x):
        # Encode
        encoded, h_n = self.encoder(x)

        # Decode
        last_hidden = h_n[-1].unsqueeze(1).repeat(1, x.size(1), 1)
        decoded, _ = self.decoder(last_hidden)

        # Output
        output = self.output_layer(decoded)
        return output


# 모델 로딩
def load_model():
    """Multi-Domain / HDFS_v1 GRU AutoEncoder 모델 로딩"""
    print(f"[detector] Loading model from {MODEL_DIR}")

    # Multi-Domain 모델 파일 확인 (우선순위 1)
    multi_domain_meta_path = os.path.join(MODEL_DIR, "multi_domain_model_meta.pkl")

    if os.path.exists(multi_domain_meta_path):
        # Multi-Domain 모델 로드
        print(f"[detector] Loading Multi-Domain GRU AutoEncoder")

        # 메타데이터 로딩
        meta = joblib.load(multi_domain_meta_path)

        # Event vocabulary 로딩
        vocab_path = os.path.join(MODEL_DIR, "multi_domain_event_vocab.pkl")
        event_to_idx = joblib.load(vocab_path)

        # Threshold 로딩
        threshold_path = os.path.join(MODEL_DIR, "multi_domain_threshold.pkl")
        threshold = joblib.load(threshold_path)

        # 모델 파라미터
        max_len = meta.get("max_seq_len", 50)
        num_events = meta.get("num_events")
        hidden_dim = meta.get("hidden_dim", 128)
        num_layers = meta.get("num_layers", 2)
        domains = meta.get("domains", ["hdfs", "hadoop", "openstack"])

        # 모델 로딩
        model_path = os.path.join(MODEL_DIR, "multi_domain_gru_autoencoder.pth")
        model = GRUAutoEncoder(
            input_dim=num_events,
            hidden_dim=hidden_dim,
            num_layers=num_layers
        )
        model.load_state_dict(torch.load(model_path, map_location="cpu"))
        model.eval()

        print(f"[detector] ✅ Multi-Domain Model loaded")
        print(f"[detector] Domains: {', '.join(domains)}")
        print(f"[detector] Events: {num_events}, Max len: {max_len}")
        print(f"[detector] Hidden dim: {hidden_dim}, Layers: {num_layers}")
        print(f"[detector] Threshold: {threshold:.6f}")
        print(f"[detector] Test Accuracy: {meta.get('test_accuracy', 0)*100:.2f}%")
        print(f"[detector] Test Precision: {meta.get('test_precision', 0)*100:.2f}%")
        print(f"[detector] Test Recall: {meta.get('test_recall', 0)*100:.2f}%")

        # Drain3 miner 새로 생성
        config = TemplateMinerConfig()
        config.profiling_enabled = False
        miner = TemplateMiner(config=config)

        return model, event_to_idx, threshold, max_len, num_events, num_events, True, miner

    # HDFS_v1 모델 파일 확인 (우선순위 2)
    hdfs_v1_meta_path = os.path.join(MODEL_DIR, "hdfs_v1_model_meta.pkl")

    if os.path.exists(hdfs_v1_meta_path):
        # HDFS_v1 모델 로드
        print(f"[detector] Loading HDFS_v1 GRU AutoEncoder")

        # 메타데이터 로딩
        meta = joblib.load(hdfs_v1_meta_path)

        # Event vocabulary 로딩
        vocab_path = os.path.join(MODEL_DIR, "hdfs_v1_event_vocab.pkl")
        event_to_idx = joblib.load(vocab_path)

        # Threshold 로딩
        threshold_path = os.path.join(MODEL_DIR, "hdfs_v1_threshold.pkl")
        threshold = joblib.load(threshold_path)

        # 모델 파라미터
        max_len = meta.get("max_seq_len", 50)
        num_events = meta.get("num_events")
        hidden_dim = meta.get("hidden_dim", 128)
        num_layers = meta.get("num_layers", 2)

        # 모델 로딩
        model_path = os.path.join(MODEL_DIR, "hdfs_v1_gru_autoencoder.pth")
        model = GRUAutoEncoder(
            input_dim=num_events,
            hidden_dim=hidden_dim,
            num_layers=num_layers
        )
        model.load_state_dict(torch.load(model_path, map_location="cpu"))
        model.eval()

        print(f"[detector] ✅ HDFS_v1 Model loaded")
        print(f"[detector] Events: {num_events}, Max len: {max_len}")
        print(f"[detector] Hidden dim: {hidden_dim}, Layers: {num_layers}")
        print(f"[detector] Threshold: {threshold:.6f}")

        # Drain3 miner 새로 생성 (HDFS 로그용)
        config = TemplateMinerConfig()
        config.profiling_enabled = False
        miner = TemplateMiner(config=config)

        return model, event_to_idx, threshold, max_len, num_events, num_events, True, miner

    else:
        # 기존 모델 로드 (Legacy)
        print(f"[detector] Loading legacy model")

        # 메타데이터 로딩
        meta_path = os.path.join(MODEL_DIR, "model_meta.pkl")
        meta = joblib.load(meta_path)

        # 템플릿 로딩
        templates_path = os.path.join(MODEL_DIR, "templates.pkl")
        unique_templates = joblib.load(templates_path)
        template_to_idx = {t: i for i, t in enumerate(unique_templates)}

        # Threshold 로딩
        threshold_path = os.path.join(MODEL_DIR, "threshold.pkl")
        threshold = joblib.load(threshold_path)

        # Drain3 miner 상태 로딩
        drain3_state_path = os.path.join(MODEL_DIR, "drain3_state.pkl")
        if os.path.exists(drain3_state_path):
            miner = joblib.load(drain3_state_path)
            print(f"[detector] ✅ Drain3 상태 로딩 완료: {len(miner.drain.clusters)} clusters")
        else:
            config = TemplateMinerConfig()
            config.profiling_enabled = False
            miner = TemplateMiner(config=config)

        # 모델 파라미터
        max_len = meta.get("max_len", MAX_SEQUENCE_LENGTH)
        num_templates = meta.get("num_templates", len(unique_templates))
        input_dim = meta.get("input_dim", num_templates)
        hidden_dim = meta.get("hidden_dim", 256)
        num_layers = meta.get("num_layers", 2)
        model_type = meta.get("model_type", MODEL_TYPE)
        use_gru = "gru" in model_type.lower()

        # 모델 로딩
        legacy_model_path = os.path.join(MODEL_DIR, "hdfs_autoencoder.pth")
        new_model_path = os.path.join(MODEL_DIR, f"unified_{model_type}.pth")

        if os.path.exists(new_model_path):
            model_path = new_model_path
        elif os.path.exists(legacy_model_path):
            model_path = legacy_model_path
        else:
            model_path = new_model_path

        state = torch.load(model_path, map_location="cpu")

        if "encoder.0.weight" in state:
            # Linear AutoEncoder
            encoder_weight_shape = state['encoder.0.weight'].shape
            actual_hidden_dim = encoder_weight_shape[0]
            actual_input_dim = encoder_weight_shape[1]

            model = nn.Sequential(
                nn.Linear(actual_input_dim, actual_hidden_dim),
                nn.ReLU(),
                nn.Linear(actual_hidden_dim, actual_input_dim),
                nn.Sigmoid()
            )
            combined_state = {
                '0.weight': state['encoder.0.weight'],
                '0.bias': state['encoder.0.bias'],
                '2.weight': state['decoder.0.weight'],
                '2.bias': state['decoder.0.bias']
            }
            model.load_state_dict(combined_state)

            input_dim = actual_input_dim
            hidden_dim = actual_hidden_dim
            num_templates = actual_input_dim
        else:
            # LSTM/GRU AutoEncoder
            model = UnifiedLSTMAutoEncoder(
                input_dim=input_dim,
                hidden_dim=hidden_dim,
                num_layers=num_layers,
                use_gru=use_gru
            )
            model.load_state_dict(state)

        model.eval()

        print(f"[detector] Model loaded: {model_type}")
        print(f"[detector] Input dim: {input_dim}, Templates: {num_templates}")
        print(f"[detector] Threshold: {threshold:.6f}")

        is_sequence_model = "encoder.weight_ih_l0" in state or "encoder.0.weight" not in state

        return model, template_to_idx, threshold, max_len, num_templates, input_dim, is_sequence_model, miner


# 전역 변수
model, template_to_idx, threshold, max_len, num_templates, input_dim, is_sequence_model, miner = load_model()

# 시퀀스 버퍼 (슬라이딩 윈도우)
sequence_buffer = deque(maxlen=max_len)


@app.route("/health", methods=["GET"])
def health():
    """헬스 체크"""
    return jsonify({"status": "healthy", "service": "detector"}), 200


@app.route("/analyze", methods=["POST"])
def analyze():
    """로그 이상 탐지"""
    data = request.json
    messages = data.get("messages", [])
    ecs_logs = data.get("ecs_logs", [])

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    results = []

    for i, message in enumerate(messages):
        # 템플릿/이벤트 추출
        result = miner.add_log_message(message)
        template = result["template_mined"]
        cluster_id = result.get("cluster_id")

        # Multi-domain 모델인 경우 이벤트 ID 생성
        if cluster_id is not None and os.path.exists(os.path.join(MODEL_DIR, "multi_domain_model_meta.pkl")):
            # 도메인 감지 (간단한 휴리스틱)
            domain = detect_domain(message)
            event_id = f"{domain}_E{cluster_id}"
        else:
            event_id = template

        # 시퀀스 버퍼에 추가
        sequence_buffer.append(event_id)

        # 시퀀스가 충분히 모였을 때 분석
        if len(sequence_buffer) >= max_len:
            anomaly_result = detect_anomaly(list(sequence_buffer))
            results.append(anomaly_result)

            # Visualizer로 전송
            if i < len(ecs_logs):
                send_to_visualizer(anomaly_result, ecs_logs[i])

    print(f"[detector] ✅ Analyzed {len(messages)} messages")

    return jsonify({
        "status": "success",
        "analyzed": len(messages),
        "results": results
    }), 200


def detect_domain(log_message):
    """로그 메시지에서 도메인 감지 (휴리스틱)"""
    msg_lower = log_message.lower()

    # HDFS 패턴
    if any(keyword in msg_lower for keyword in ['hdfs', 'datanode', 'namenode', 'blockreport', 'dfs.', 'blk_']):
        return "HDFS"

    # Hadoop 패턴
    if any(keyword in msg_lower for keyword in ['mapreduce', 'application_', 'yarn', 'job_', 'task_']):
        return "Hadoop"

    # OpenStack 패턴
    if any(keyword in msg_lower for keyword in ['nova', 'neutron', 'keystone', 'instance', 'compute']):
        return "OpenStack"

    # 기본값: HDFS
    return "HDFS"


def detect_anomaly(template_sequence):
    """템플릿 시퀀스로 이상 탐지"""
    # 템플릿 벡터화
    matched_templates = 0
    if is_sequence_model:
        # 시퀀스 모델: (batch_size, seq_len, num_templates)
        # input_dim은 항상 num_templates와 동일 (시간 특성 제거됨)
        vec = np.zeros((max_len, num_templates), dtype=np.float32)
        for i, template in enumerate(template_sequence[:max_len]):
            if template in template_to_idx:
                idx = template_to_idx[template]
                vec[i][idx] = 1.0
                matched_templates += 1
        x = torch.tensor(vec.reshape(1, max_len, num_templates), dtype=torch.float32)
    else:
        # 단순 AutoEncoder: 마지막 템플릿만 사용 (batch_size, input_dim)
        vec = np.zeros(num_templates, dtype=np.float32)
        if template_sequence and template_sequence[-1] in template_to_idx:
            idx = template_to_idx[template_sequence[-1]]
            vec[idx] = 1.0
            matched_templates = 1
        x = torch.tensor(vec.reshape(1, num_templates), dtype=torch.float32)

    # 예측
    with torch.no_grad():
        reconstructed = model(x)
        loss = ((x - reconstructed) ** 2).mean().item()

    is_anomaly = loss > threshold
    status = "anomaly" if is_anomaly else "normal"

    # 디버깅 로그 (샘플링: 10개 중 1개만 출력)
    import random
    if random.random() < 0.1:
        print(f"[detector] 🔍 Loss: {loss:.6f} | Threshold: {threshold:.6f} | Status: {status} | Matched: {matched_templates}/{len(template_sequence)}")

    return {
        "loss": float(loss),
        "threshold": float(threshold),
        "status": status,
        "sequence_length": len(template_sequence)
    }


def send_to_visualizer(anomaly_result, ecs_log):
    """이상 탐지 결과를 큐에 넣고 우선 visualizer로 전송"""
    try:
        # 항상 visualizer에는 즉시 전달
        payload = {
            "loss": anomaly_result["loss"],
            "status": anomaly_result["status"],
            "threshold": anomaly_result["threshold"],
            "log": ecs_log,
            "llm_analysis": None  # 초기에는 LLM 결과 없음
        }

        requests.post(VISUALIZER_URL, json=payload, timeout=4)

        # ⬇️ anomaly면 LLM 분석을 위한 큐에 push
        if anomaly_result["status"] == "anomaly":
            try:
                queue_payload = {
                    "loss": anomaly_result["loss"],
                    "status": anomaly_result["status"],
                    "threshold": anomaly_result["threshold"],
                    "log": ecs_log,
                }
                requests.post("http://llm-queue-service:9001/push", json=queue_payload, timeout=1)
                print("[detector] 📌 LLM task queued")
            except Exception as e:
                print(f"[detector] ⚠️ LLM queue push failed: {e}")

        print(f"[detector] 🚀 anomaly sent to visualizer (LLM later)")
    except Exception as e:
        print(f"[detector] ⚠️ Failed to send event: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
