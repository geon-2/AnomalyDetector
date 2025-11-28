"""
Anomaly Explanation Service
Rule-based pattern matching for log anomaly explanation
"""
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Pattern-based explanation templates
EXPLANATIONS = {
    # HDFS patterns
    'block': {
        'keywords': ['blk_', 'block', 'datanode', 'namenode'],
        'normal': 'HDFS block processing is operating normally.',
        'anomaly': 'Anomaly detected in HDFS block transfer or replication. Check network connectivity and DataNode status.'
    },
    'connection': {
        'keywords': ['connection', 'timeout', 'failed', 'error'],
        'normal': 'Network connections are stable.',
        'anomaly': 'Network connection issues detected. Check firewall settings, bandwidth, and server response times.'
    },
    'disk': {
        'keywords': ['disk', 'storage', 'space', 'io'],
        'normal': 'Disk I/O is operating within normal range.',
        'anomaly': 'Disk I/O bottleneck or low storage space suspected. Monitor disk usage and I/O performance.'
    },
    # Hadoop patterns
    'mapreduce': {
        'keywords': ['mapreduce', 'map', 'reduce', 'task', 'job'],
        'normal': 'MapReduce jobs are executing normally.',
        'anomaly': 'Error occurred during MapReduce job execution. Check failed task logs and resource allocation.'
    },
    # OpenStack patterns
    'instance': {
        'keywords': ['instance', 'vm', 'compute', 'nova'],
        'normal': 'VM instances are operating normally.',
        'anomaly': 'Issue detected in VM instance creation or management. Check hypervisor status and resource allocation.'
    },
    # General patterns
    'memory': {
        'keywords': ['memory', 'heap', 'oom', 'outofmemory'],
        'normal': 'Memory usage is within normal range.',
        'anomaly': 'Memory shortage or leak suspected. Analyze heap dumps and adjust memory settings.'
    },
    'default': {
        'keywords': [],
        'normal': 'System is operating normally.',
        'anomaly': 'Abnormal pattern detected. Check detailed logs and system status.'
    }
}

def detect_pattern(message):
    """Detect pattern from log message"""
    message_lower = message.lower()

    for pattern_name, pattern_info in EXPLANATIONS.items():
        if pattern_name == 'default':
            continue
        keywords = pattern_info['keywords']
        if any(keyword in message_lower for keyword in keywords):
            return pattern_name

    return 'default'

def generate_explanation(log_data, status):
    """Generate explanation for anomaly log"""
    message = log_data.get('message', '')
    loss = log_data.get('loss', 0.0)
    threshold = log_data.get('threshold', 0.0)

    # Detect pattern
    pattern = detect_pattern(message)
    pattern_info = EXPLANATIONS[pattern]

    # Base explanation
    if status == 'anomaly':
        base_explanation = pattern_info['anomaly']
        severity = 'HIGH' if loss > threshold * 2 else 'MEDIUM'
    else:
        base_explanation = pattern_info['normal']
        severity = 'LOW'

    # Generate detailed explanation
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
    """Get recommended actions"""
    if status == 'normal':
        return ["System is operating normally.", "Continue monitoring recommended."]

    recommendations = []

    # Pattern-specific recommendations
    pattern_recommendations = {
        'block': [
            "Check DataNode status (hdfs dfsadmin -report)",
            "Verify network connectivity",
            "Check block replication settings (dfs.replication)"
        ],
        'connection': [
            "Measure network latency (ping, traceroute)",
            "Check firewall rules",
            "Verify server load and scale out if needed"
        ],
        'disk': [
            "Check disk usage (df -h)",
            "Monitor I/O wait time (iostat)",
            "Clean up old log files"
        ],
        'mapreduce': [
            "Check failed task logs",
            "Verify memory allocation settings (mapreduce.map.memory.mb)",
            "Check YARN resource manager status"
        ],
        'instance': [
            "Check hypervisor logs",
            "Verify compute node resource status",
            "Validate VM image and flavor settings"
        ],
        'memory': [
            "Generate and analyze heap dump",
            "Adjust JVM memory settings (-Xmx, -Xms)",
            "Use profiling tools if memory leak suspected"
        ],
        'default': [
            "Check detailed logs",
            "Monitor system resource usage",
            "Review recent changes"
        ]
    }

    recommendations.extend(pattern_recommendations.get(pattern, pattern_recommendations['default']))

    # Add severity-based recommendations
    if loss > threshold * 3:
        recommendations.insert(0, "⚠️ URGENT: Immediate action required!")
    elif loss > threshold * 2:
        recommendations.insert(0, "⚡ WARNING: Quick response recommended.")

    return recommendations[:5]  # Max 5 recommendations

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": "llm-service"
    }), 200

@app.route("/explain", methods=["POST"])
def explain():
    """Generate explanation for anomaly log"""
    data = request.json
    log_data = data.get("log", {})
    status = data.get("status", "normal")

    if not log_data:
        return jsonify({"error": "No log data provided"}), 400

    # Generate explanation
    explanation = generate_explanation(log_data, status)

    return jsonify(explanation), 200

@app.route("/batch_explain", methods=["POST"])
def batch_explain():
    """Generate explanations for multiple anomaly logs"""
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
