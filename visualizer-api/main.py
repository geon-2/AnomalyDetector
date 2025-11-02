from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

LOG_PATH = "/data/events.jsonl"
os.makedirs("/data", exist_ok=True)

@app.route("/event", methods=["POST"])
def receive_event():
    data = request.get_json(force=True)
    if data:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(data) + "\n")
        print(f"[API] Event logged: {data}")
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "invalid data"}), 400

if __name__ == "__main__":
    print("[INFO] Visualizer API running on port 8502")
    app.run(host="0.0.0.0", port=8502)