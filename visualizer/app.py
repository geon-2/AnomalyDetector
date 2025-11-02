import streamlit as st
from flask import Flask, request
import threading

st.title("AIOps HDFS Anomaly Detector")
st.write("실시간 로그 이상탐지 결과")

if "logs" not in st.session_state:
    st.session_state["logs"] = []

flask_app = Flask(__name__)

@flask_app.route("/api/report", methods=["POST"])
def receive():
    data = request.json()
    st.session_state.logs.append(data)
    return "ok"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8501, debug=False)

threading.Thread(target=run_flask, daemon=True).start()

for log in st.session_state.logs[-20:]:
    color = "🚨" if log["anomaly"] else "✅"
    st.write(f"{color} {log['template']}  (error={log['error']:.6f})")