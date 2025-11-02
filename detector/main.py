from flask import Flask, request, jsonify
import torch
import torch.nn as nn
import joblib
import numpy as np
import requests

VISUALIZER_URL = "http://visualizer-api:8502/event"

class AE(nn.Module):
    def __init__(self, input_dim, hidden_dim=128):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU()
        )
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, input_dim),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


template_to_idx = joblib.load("/models/templates.pkl")
meta = joblib.load("/models/model_meta.pkl")
threshold = joblib.load("/models/threshold.pkl")

max_len = meta["max_len"]
num_templates = meta["num_templates"]
input_dim = max_len * num_templates

print(f"[INFO] Loaded model meta: input_dim={input_dim}, max_len={max_len}, num_templates={num_templates}")

model = AE(input_dim=input_dim)
state = torch.load("/models/hdfs_autoencoder.pth", map_location="cpu")
model.load_state_dict(state)
model.eval()

app = Flask(__name__)

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    template_seq = data.get("template_seq", [])
    if not isinstance(template_seq, list) or len(template_seq) == 0:
        return jsonify({"error": "Invalid template sequence"}), 400

    vec = np.zeros((max_len, num_templates), dtype=np.float32)
    for i, t in enumerate(template_seq[:max_len]):
        if t in template_to_idx:
            idx = template_to_idx[t]
            vec[i][idx] = 1.0

    x = torch.tensor(vec.reshape(1, -1), dtype=torch.float32)
    with torch.no_grad():
        recon = model(x)
        loss = ((x - recon) ** 2).mean().item()

    status = "anomaly" if loss > threshold else "normal"
    print(f"[DETECT] loss={loss:.6f} | threshold={threshold:.6f} | {status}")

    payload = {"loss": loss, "status": status, "template_seq": template_seq}
    try:
        resp = requests.post(VISUALIZER_URL, json=payload, timeout=2)
        if resp.status_code == 200:
            print(f"[FORWARD] Sent to visualizer: {status}")
        else:
            print(f"[FORWARD] Visualizer response: {resp.status_code}")
    except Exception as e:
        print(f"[WARN] Visualizer not reachable: {e}")

    return jsonify({"loss": loss, "status": status})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000)