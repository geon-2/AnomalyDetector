from flask import Flask, request, jsonify
import torch, torch.nn as nn, joblib, numpy as np, requests

app = Flask(__name__)

class AE(nn.Module):
    def __init__(self, input_dim, hidden_dim=128):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.ReLU())
        self.dec = nn.Sequential(nn.Linear(hidden_dim, input_dim), nn.Sigmoid())
    def forward(self, x): return self.dec(self.enc(x))

template_to_idx = joblib.load('/models/templates.pkl')
threshold = joblib.load('/models/threshold.pkl')
num_templates = len(template_to_idx)
input_dim = num_templates
model = AE(input_dim)
model.load_state_dict(torch.load('/models/hdfs_autoencoder.pth', map_location=torch.device('cpu')))
model.eval()

@app.route('/analyze', methods=['POST'])
def analyze():
    template = request.json['template']
    vec = np.zeros((1, num_templates))
    if template in template_to_idx:
        vec[0][template_to_idx[template]] = 1
    x = torch.tensor(vec, dtype=torch.float32)
    with torch.no_grad():
        recon = model(x)
        loss = ((x - recon)**2).mean().item()
    anomaly = loss > threshold
    requests.post("http://visualizer:8501/api/report", json={"template": template, "error": loss, "anomaly": anomaly})
    return jsonify({"template": template, "anomaly": anomaly, "error": loss})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000)