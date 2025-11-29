"""
Anomaly Explanation Service
LLM-based analysis using Transformers (Llama-3.2-3B)
"""
from numpy import dtype
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer
from datetime import datetime
import torch
import json
import re
import os

app = FastAPI()

MODEL_DIR = os.getenv("MODEL_DIR", "/models/llm")
MODEL_NAME = 'TinyLlama/TinyLlama-1.1B-Chat-v1.0'

print(f"[llm-service] Loading model from local path: {MODEL_DIR}")

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    dtype=torch.float16,
    device_map="cpu",
    low_cpu_mem_usage=True
)
print(f"[llm-service] Model loaded successfully")

# Pattern-based explanation templates (fallback)
EXPLANATIONS = {
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
    'mapreduce': {
        'keywords': ['mapreduce', 'map', 'reduce', 'task', 'job'],
        'normal': 'MapReduce jobs are executing normally.',
        'anomaly': 'Error occurred during MapReduce job execution. Check failed task logs and resource allocation.'
    },
    'instance': {
        'keywords': ['instance', 'vm', 'compute', 'nova'],
        'normal': 'VM instances are operating normally.',
        'anomaly': 'Issue detected in VM instance creation or management. Check hypervisor status and resource allocation.'
    },
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


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.3


class ExplainRequest(BaseModel):
    log: dict
    status: str = "normal"


class BatchExplainRequest(BaseModel):
    logs: list


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


def generate_with_llm(prompt: str, max_tokens: int = 256, temperature: float = 0.3):
    """Generate text using Llama-3.2"""
    try:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id
            )
        response_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response_text
    except Exception as e:
        print(f"[llm-service] ⚠️ Generation failed: {e}")
        raise


def generate_explanation_with_llm(log_data, status):
    """Generate explanation using LLM"""
    message = log_data.get('message', '')
    loss = log_data.get('loss', 0.0)
    threshold = log_data.get('threshold', 0.0)
    deviation = ((loss / threshold - 1) * 100) if threshold > 0 else 0

    prompt = f"""You are a distributed system log analyst. Analyze the following anomaly detection result and provide a detailed explanation.

**Anomaly Detection Result:**
- Status: {status}
- Loss Score: {loss:.6f}
- Threshold: {threshold:.6f}
- Deviation: {deviation:.1f}%
- Log Message: {message}

**Task:**
1. Identify the root cause of this anomaly
2. Assess the severity level (LOW/MEDIUM/HIGH/CRITICAL)
3. Provide 3-5 specific actionable recommendations to address this issue

**Response Format (JSON):**
{{
  "summary": "Brief explanation of the anomaly",
  "root_cause": "Identified root cause",
  "severity": "SEVERITY_LEVEL",
  "impact": "Potential impact on the system",
  "recommendations": ["recommendation 1", "recommendation 2", ...]
}}

Respond only with the JSON object, no additional text."""

    try:
        llm_response = generate_with_llm(prompt, max_tokens=512, temperature=0.3)
        json_match = re.search(r'\{[\s\S]*\}', llm_response)
        if json_match:
            analysis = json.loads(json_match.group())
            explanation = {
                'summary': analysis.get('summary', 'Anomaly detected'),
                'root_cause': analysis.get('root_cause', 'Unknown'),
                'severity': analysis.get('severity', 'MEDIUM'),
                'impact': analysis.get('impact', 'System may be affected'),
                'pattern': detect_pattern(message),
                'details': {
                    'loss_score': f"{loss:.6f}",
                    'threshold': f"{threshold:.6f}",
                    'deviation': f"{deviation:.1f}%"
                },
                'recommendations': analysis.get('recommendations', []),
                'timestamp': datetime.now().isoformat(),
                'llm_analyzed': True
            }
            print(f"[llm-service] ✅ LLM analysis completed: {explanation['severity']}")
            return explanation
        else:
            raise ValueError("No JSON found in LLM response")
    except Exception as e:
        print(f"[llm-service] ⚠️ LLM analysis failed: {e}, falling back to rule-based")
        return generate_explanation_fallback(log_data, status)


def generate_explanation_fallback(log_data, status):
    """Fallback: Generate explanation using rule-based system"""
    message = log_data.get('message', '')
    loss = log_data.get('loss', 0.0)
    threshold = log_data.get('threshold', 0.0)
    pattern = detect_pattern(message)
    pattern_info = EXPLANATIONS[pattern]

    if status == 'anomaly':
        base_explanation = pattern_info['anomaly']
        severity = 'HIGH' if loss > threshold * 2 else 'MEDIUM'
    else:
        base_explanation = pattern_info['normal']
        severity = 'LOW'

    explanation = {
        'summary': base_explanation,
        'root_cause': 'Pattern-based detection: ' + pattern,
        'severity': severity,
        'impact': 'Requires investigation',
        'pattern': pattern,
        'details': {
            'loss_score': f"{loss:.6f}",
            'threshold': f"{threshold:.6f}",
            'deviation': f"{((loss / threshold - 1) * 100):.1f}%" if threshold > 0 else "N/A"
        },
        'recommendations': get_recommendations(pattern, status, loss, threshold),
        'timestamp': datetime.now().isoformat(),
        'llm_analyzed': False
    }
    return explanation


def get_recommendations(pattern, status, loss, threshold):
    """Get recommended actions"""
    if status == 'normal':
        return ["System is operating normally.", "Continue monitoring recommended."]

    pattern_recommendations = {
        'block': [
            "Check DataNode status (hdfs dfsadmin -report)",
            "Verify network connectivity",
            "Check block replication settings"
        ],
        'connection': [
            "Measure network latency",
            "Check firewall rules",
            "Verify server load and scale out if needed"
        ],
        'disk': [
            "Check disk usage (df -h)",
            "Monitor I/O wait time",
            "Clean up old log files"
        ],
        'mapreduce': [
            "Check failed task logs",
            "Verify memory allocation settings",
            "Check YARN resource manager status"
        ],
        'instance': [
            "Check hypervisor logs",
            "Verify compute node resource status",
            "Validate VM image and flavor settings"
        ],
        'memory': [
            "Generate and analyze heap dump",
            "Adjust JVM memory settings",
            "Use profiling tools if memory leak suspected"
        ],
        'default': [
            "Check detailed logs",
            "Monitor system resource usage",
            "Review recent changes"
        ]
    }

    recommendations = list(pattern_recommendations.get(pattern, pattern_recommendations['default']))
    if loss > threshold * 3:
        recommendations.insert(0, "⚠️ URGENT: Immediate action required!")
    elif loss > threshold * 2:
        recommendations.insert(0, "⚡ WARNING: Quick response recommended.")

    return recommendations[:5]


@app.get("/health")
def health():
    """Health check"""
    return {"status": "ok", "service": "llm-service"}


@app.post("/generate")
def generate(request: GenerateRequest):
    """Generate text using Llama-3.2"""
    try:
        response_text = generate_with_llm(
            request.prompt,
            request.max_tokens,
            request.temperature
        )
        return {
            "prompt": request.prompt,
            "response": response_text,
            "model": MODEL_NAME
        }
    except Exception as e:
        return {"error": str(e)}, 500


@app.post("/explain")
def explain(request: ExplainRequest):
    """Generate explanation for anomaly log using LLM"""
    log_data = request.log
    status = request.status

    if not log_data:
        return {"error": "No log data provided"}, 400

    if status == 'anomaly':
        explanation = generate_explanation_with_llm(log_data, status)
    else:
        explanation = generate_explanation_fallback(log_data, status)

    return explanation


@app.post("/batch_explain")
def batch_explain(request: BatchExplainRequest):
    """Generate explanations for multiple anomaly logs using LLM"""
    logs = request.logs

    if not logs:
        return {"error": "No logs provided"}, 400

    explanations = []
    for log_entry in logs:
        log_data = log_entry.get("log", {})
        status = log_entry.get("status", "normal")

        if status == 'anomaly':
            explanation = generate_explanation_with_llm(log_data, status)
        else:
            explanation = generate_explanation_fallback(log_data, status)

        explanations.append(explanation)

    return {"explanations": explanations, "count": len(explanations)}


if __name__ == "__main__":
    import uvicorn
    print("[llm-service] Starting Anomaly Explanation Service")
    print(f"[llm-service] Model: {MODEL_NAME}")
    print("[llm-service] Fallback: Rule-based pattern matching")
    uvicorn.run(app, host="0.0.0.0", port=8000)
