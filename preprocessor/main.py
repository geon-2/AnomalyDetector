from flask import Flask, request
import requests as rq
import joblib
from drain3 import TemplateMiner

app = Flask(__name__)

templates = joblib.load("/models/templates.pkl")
template_to_idx = {t: i for i, t in enumerate(templates)}
max_len = joblib.load("/models/model_meta.pkl")["max_len"]

miner = TemplateMiner()

@app.route("/ingest", methods=["POST"])
def ingest():
    log_line = request.json.get("log", "")
    result = miner.add_log_message(log_line)
    template = result["template_mined"]

    # Unknown template 방지
    if template not in template_to_idx:
        print(f"[WARN] Unknown template: {template}")
        return "skip", 200

    # 최근 max_len 시퀀스 생성 (간단하게 단일 템플릿 전달 가능)
    rq.post("http://detector:6000/analyze", json={"template_seq": [template]})
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)