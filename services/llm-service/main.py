"""
Anomaly Explanation Service
이상 로그에 대한 설명과 대응 방안을 생성하는 서비스
"""
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# 로그 패턴별 설명 템플릿
EXPLANATIONS = {
    # HDFS 패턴
    'block': {
        'keywords': ['blk_', 'block', 'datanode', 'namenode'],
        'normal': 'HDFS 블록 처리가 정상적으로 진행되고 있습니다.',
        'anomaly': 'HDFS 블록 전송 또는 복제 과정에서 이상이 감지되었습니다. 네트워크 연결 상태와 DataNode 상태를 확인해야 합니다.'
    },
    'connection': {
        'keywords': ['connection', 'timeout', 'failed', 'error'],
        'normal': '네트워크 연결이 정상적으로 유지되고 있습니다.',
        'anomaly': '네트워크 연결 문제가 발생했습니다. 방화벽 설정, 네트워크 대역폭, 서버 응답 시간을 점검하세요.'
    },
    'disk': {
        'keywords': ['disk', 'storage', 'space', 'io'],
        'normal': '디스크 I/O가 정상 범위 내에서 동작 중입니다.',
        'anomaly': '디스크 I/O 병목 또는 저장 공간 부족이 의심됩니다. 디스크 사용량과 I/O 성능을 모니터링하세요.'
    },
    # Hadoop 패턴
    'mapreduce': {
        'keywords': ['mapreduce', 'map', 'reduce', 'task', 'job'],
        'normal': 'MapReduce 작업이 정상적으로 실행되고 있습니다.',
        'anomaly': 'MapReduce 작업 실행 중 오류가 발생했습니다. Task 실패 로그와 리소스 할당 상태를 확인하세요.'
    },
    # OpenStack 패턴
    'instance': {
        'keywords': ['instance', 'vm', 'compute', 'nova'],
        'normal': 'VM 인스턴스가 정상적으로 동작 중입니다.',
        'anomaly': 'VM 인스턴스 생성 또는 관리 중 문제가 발생했습니다. 하이퍼바이저 상태와 리소스 할당을 점검하세요.'
    },
    # 일반 패턴
    'memory': {
        'keywords': ['memory', 'heap', 'oom', 'outofmemory'],
        'normal': '메모리 사용량이 정상 범위 내에 있습니다.',
        'anomaly': '메모리 부족 또는 메모리 누수가 의심됩니다. 힙 덤프를 분석하고 메모리 설정을 조정하세요.'
    },
    'default': {
        'keywords': [],
        'normal': '시스템이 정상적으로 동작하고 있습니다.',
        'anomaly': '비정상적인 패턴이 감지되었습니다. 상세 로그를 확인하고 시스템 상태를 점검하세요.'
    }
}

def detect_pattern(message):
    """로그 메시지에서 패턴 감지"""
    message_lower = message.lower()

    for pattern_name, pattern_info in EXPLANATIONS.items():
        if pattern_name == 'default':
            continue
        keywords = pattern_info['keywords']
        if any(keyword in message_lower for keyword in keywords):
            return pattern_name

    return 'default'

def generate_explanation(log_data, status):
    """이상 로그에 대한 설명 생성"""
    message = log_data.get('message', '')
    loss = log_data.get('loss', 0.0)
    threshold = log_data.get('threshold', 0.0)

    # 패턴 감지
    pattern = detect_pattern(message)
    pattern_info = EXPLANATIONS[pattern]

    # 기본 설명
    if status == 'anomaly':
        base_explanation = pattern_info['anomaly']
        severity = 'HIGH' if loss > threshold * 2 else 'MEDIUM'
    else:
        base_explanation = pattern_info['normal']
        severity = 'LOW'

    # 상세 설명 생성
    explanation = {
        'summary': base_explanation,
        'severity': severity,
        'pattern': pattern,
        'details': {
            'loss_score': f"{loss:.6f}",
            'threshold': f"{threshold:.6f}",
            'deviation': f"{((loss / threshold - 1) * 100):.1f}%" if threshold > 0 else "N/A"
        },
        'recommendations': get_recommendations(pattern, status, loss, threshold),
        'timestamp': datetime.now().isoformat()
    }

    return explanation

def get_recommendations(pattern, status, loss, threshold):
    """대응 방안 제안"""
    if status == 'normal':
        return ["시스템이 정상적으로 동작 중입니다.", "지속적인 모니터링을 권장합니다."]

    recommendations = []

    # 패턴별 권장사항
    pattern_recommendations = {
        'block': [
            "DataNode의 상태를 확인하세요 (hdfs dfsadmin -report)",
            "네트워크 연결 상태를 점검하세요",
            "블록 복제 설정(dfs.replication)을 확인하세요"
        ],
        'connection': [
            "네트워크 지연 시간을 측정하세요 (ping, traceroute)",
            "방화벽 규칙을 확인하세요",
            "서버 로드를 확인하고 필요시 스케일 아웃하세요"
        ],
        'disk': [
            "디스크 사용량을 확인하세요 (df -h)",
            "I/O 대기 시간을 확인하세요 (iostat)",
            "오래된 로그 파일을 정리하세요"
        ],
        'mapreduce': [
            "Failed task 로그를 확인하세요",
            "메모리 할당 설정을 확인하세요 (mapreduce.map.memory.mb)",
            "YARN 리소스 매니저 상태를 확인하세요"
        ],
        'instance': [
            "하이퍼바이저 로그를 확인하세요",
            "Compute 노드의 리소스 상태를 확인하세요",
            "VM 이미지와 플레이버 설정을 검증하세요"
        ],
        'memory': [
            "힙 덤프를 생성하고 분석하세요",
            "JVM 메모리 설정을 조정하세요 (-Xmx, -Xms)",
            "메모리 누수가 의심되면 프로파일링 도구를 사용하세요"
        ],
        'default': [
            "상세 로그를 확인하세요",
            "시스템 리소스 사용률을 모니터링하세요",
            "최근 변경사항을 검토하세요"
        ]
    }

    recommendations.extend(pattern_recommendations.get(pattern, pattern_recommendations['default']))

    # 심각도에 따른 추가 권장사항
    if loss > threshold * 3:
        recommendations.insert(0, "⚠️ 긴급: 즉시 조치가 필요합니다!")
    elif loss > threshold * 2:
        recommendations.insert(0, "⚡ 주의: 빠른 대응이 권장됩니다.")

    return recommendations[:5]  # 최대 5개

@app.route("/health", methods=["GET"])
def health():
    """헬스 체크"""
    return jsonify({
        "status": "healthy",
        "service": "llm-service"
    }), 200

@app.route("/explain", methods=["POST"])
def explain():
    """이상 로그 설명 생성"""
    data = request.json
    log_data = data.get("log", {})
    status = data.get("status", "normal")

    if not log_data:
        return jsonify({"error": "No log data provided"}), 400

    # 설명 생성
    explanation = generate_explanation(log_data, status)

    return jsonify(explanation), 200

@app.route("/batch_explain", methods=["POST"])
def batch_explain():
    """여러 이상 로그에 대한 설명 일괄 생성"""
    data = request.json
    logs = data.get("logs", [])

    if not logs:
        return jsonify({"error": "No logs provided"}), 400

    explanations = []
    for log_entry in logs:
        log_data = log_entry.get("log", {})
        status = log_entry.get("status", "normal")
        explanation = generate_explanation(log_data, status)
        explanations.append(explanation)

    return jsonify({
        "explanations": explanations,
        "count": len(explanations)
    }), 200

if __name__ == "__main__":
    print("[llm-service] Starting Anomaly Explanation Service")
    print("[llm-service] Mode: Rule-based pattern matching")
    app.run(host="0.0.0.0", port=8000)
