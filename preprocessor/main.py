from flask import Flask, request
from drain3 import TemplateMiner
import requests

app = Flask(__name__)
miner = TemplateMiner()

@app.route('/ingest', methods=['POST'])
def ingest():
    log = request.json["log"]
    result = miner.add_log_message(log)
    template = result["template_mined"]
    request.post("http://detector:6000/analyze", json={"template": template})
    return "ok"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)