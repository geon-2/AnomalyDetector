"""
Visualizer Service (Backend API)
이상 탐지 결과 및 로그 저장/조회 API
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime
from pathlib import Path
from collections import deque

app = Flask(__name__)
CORS(app)

# 메모리 기반 데이터 저장 (실제 환경에서는 DB 사용)
events = deque(maxlen=10000)
statistics = {
    "total_logs": 0,
    "total_anomalies": 0,
    "total_normal": 0,
    "start_time": datetime.now().isoformat()
}


@app.route("/health", methods=["GET"])
def health():
    """헬스 체크"""
    return jsonify({"status": "healthy", "service": "visualizer"}), 200


@app.route("/event", methods=["POST"])
def receive_event():
    """이상 탐지 결과 수신"""
    data = request.json

    event = {
        "timestamp": datetime.now().isoformat(),
        "loss": data.get("loss", 0.0),
        "threshold": data.get("threshold", 0.0),
        "status": data.get("status", "unknown"),
        "log": data.get("log", {}),
        "llm_analysis": data.get("llm_analysis")
    }

    events.append(event)

    # 통계 업데이트
    statistics["total_logs"] += 1
    if event["status"] == "anomaly":
        statistics["total_anomalies"] += 1
    elif event["status"] == "normal":
        statistics["total_normal"] += 1

    # LLM 분석 결과 로깅
    if event.get("llm_analysis"):
        severity = event["llm_analysis"].get("severity", "N/A")
        pattern = event["llm_analysis"].get("pattern", "N/A")
        print(f"[visualizer] ✅ Event received: {event['status']} (loss={event['loss']:.6f}, severity={severity}, pattern={pattern})")
    else:
        print(f"[visualizer] ✅ Event received: {event['status']} (loss={event['loss']:.6f})")

    return jsonify({"status": "success"}), 200


@app.route("/events", methods=["GET"])
def get_events():
    """이벤트 목록 조회"""
    limit = request.args.get("limit", default=100, type=int)
    status_filter = request.args.get("status", default=None, type=str)

    filtered_events = list(events)

    if status_filter:
        filtered_events = [e for e in filtered_events if e["status"] == status_filter]

    # 최신 이벤트부터 반환
    filtered_events.reverse()

    return jsonify({
        "events": filtered_events[:limit],
        "total": len(filtered_events)
    }), 200


@app.route("/anomalies", methods=["GET"])
def get_anomalies():
    """이상 로그만 조회 (shortcut for /events?status=anomaly)"""
    limit = request.args.get("limit", default=100, type=int)

    anomalies = [e for e in events if e["status"] == "anomaly"]

    # 최신 이벤트부터 반환
    anomalies.reverse()

    return jsonify({
        "anomalies": anomalies[:limit],
        "total": len(anomalies)
    }), 200


@app.route("/statistics", methods=["GET"])
def get_statistics():
    """통계 정보 조회"""
    anomaly_rate = 0.0
    if statistics["total_logs"] > 0:
        anomaly_rate = statistics["total_anomalies"] / statistics["total_logs"] * 100

    return jsonify({
        **statistics,
        "anomaly_rate": round(anomaly_rate, 2),
        "current_time": datetime.now().isoformat()
    }), 200


@app.route("/clear", methods=["POST"])
def clear_data():
    """데이터 초기화"""
    events.clear()
    statistics["total_logs"] = 0
    statistics["total_anomalies"] = 0
    statistics["total_normal"] = 0
    statistics["start_time"] = datetime.now().isoformat()

    print("[visualizer] ✅ Data cleared")

    return jsonify({"status": "success"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8502)
