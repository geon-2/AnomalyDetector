"""
Log Normalizer Service
ECS 9.2.0 기반 로그 정규화 서비스 + LLM 자동 스키마 생성
"""
import os
import sys
import requests
import yaml
import re
from flask import Flask, request, jsonify
from pathlib import Path
from collections import defaultdict

# normalizer 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent))
from normalizer.normalizer import ECSNormalizer

app = Flask(__name__)

# 환경 변수
DETECTOR_URL = os.getenv("DETECTOR_URL", "http://detector-service:5002/analyze")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm-service:8000/generate_schema")
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
AUTO_SCHEMA_GENERATION = os.getenv("AUTO_SCHEMA_GENERATION", "false").lower() == "true"

# Normalizer 초기화
NORMALIZER_DIR = Path(__file__).parent / "normalizer"
normalizer = ECSNormalizer(
    schemas_dir=str(NORMALIZER_DIR / "schemas"),
    mappings_dir=str(NORMALIZER_DIR / "mappings")
)

# 미지의 로그 타입 수집 (자동 스키마 생성용)
unknown_log_samples = defaultdict(list)

print(f"[normalizer] Initialized with schemas and mappings")
print(f"[normalizer] LLM integration: {USE_LLM}")
print(f"[normalizer] Auto schema generation: {AUTO_SCHEMA_GENERATION}")


@app.route("/health", methods=["GET"])
def health():
    """헬스 체크"""
    return jsonify({"status": "healthy", "service": "normalizer"}), 200


@app.route("/normalize", methods=["POST"])
def normalize():
    """로그 정규화"""
    data = request.json
    logs = data.get("logs", [])
    source = data.get("source", None)  # source가 없으면 자동 감지

    if not logs:
        return jsonify({"error": "No logs provided"}), 400

    normalized_logs = []
    failed_count = 0
    auto_detected = False

    # source가 지정되지 않았으면 첫 로그로 감지
    if not source:
        source = detect_log_type(logs[0])
        auto_detected = True
        print(f"[normalizer] 🔍 Auto-detected log type: {source}")

    # 정규화 수행
    for raw_log in logs:
        try:
            # 로그 파싱
            parsed_log = parse_log(raw_log, source)

            # ECS 정규화 시도
            try:
                ecs_log = normalizer.normalize(parsed_log, source=source)
                normalized_logs.append(ecs_log)
            except Exception as norm_error:
                # 정규화 실패 시 - 미지의 로그 타입일 가능성
                if source == "unknown" or "mapping not found" in str(norm_error).lower():
                    # 샘플 수집
                    if AUTO_SCHEMA_GENERATION and len(unknown_log_samples[source]) < 10:
                        unknown_log_samples[source].append(raw_log)
                        print(f"[normalizer] 📝 Collecting sample for '{source}' ({len(unknown_log_samples[source])}/10)")

                        # 충분한 샘플이 모였으면 스키마 생성
                        if len(unknown_log_samples[source]) == 10:
                            schema = generate_schema_with_llm(source, unknown_log_samples[source])
                            if schema:
                                # 재시도
                                ecs_log = normalizer.normalize(parsed_log, source=source)
                                normalized_logs.append(ecs_log)
                                continue

                raise norm_error

        except Exception as e:
            failed_count += 1
            if failed_count <= 3:
                print(f"[normalizer] ⚠️ Normalization failed: {e}")

    print(f"[normalizer] ✅ Normalized {len(normalized_logs)}/{len(logs)} logs")

    # Detector로 전송
    if normalized_logs:
        send_to_detector(normalized_logs)

    return jsonify({
        "status": "success",
        "normalized": len(normalized_logs),
        "failed": failed_count,
        "source": source,
        "auto_detected": auto_detected
    }), 200


def parse_log(raw_log, source):
    """간단한 로그 파싱"""
    # HDFS 로그 형식: Date Time Pid Level Component: Content
    parts = raw_log.split(None, 5)
    if len(parts) < 6:
        return {"Content": raw_log}

    return {
        "Date": parts[0],
        "Time": parts[1],
        "Pid": parts[2],
        "Level": parts[3],
        "Component": parts[4].rstrip(":"),
        "Content": parts[5] if len(parts) > 5 else ""
    }


def detect_log_type(raw_log):
    """로그 타입 자동 감지"""
    # 간단한 패턴 매칭으로 로그 타입 감지
    patterns = {
        "hdfs": r"blk_|DataNode|NameNode|HDFS",
        "hadoop": r"org\.apache\.hadoop|mapreduce",
        "spark": r"org\.apache\.spark|SparkContext",
        "apache": r"\[.*?\]\s+\"(GET|POST|PUT|DELETE)",
        "linux": r"kernel:|systemd:|sshd:",
        "openssh": r"sshd\[|Accepted password|Failed password",
        "openstack": r"nova|neutron|keystone|glance",
    }

    for log_type, pattern in patterns.items():
        if re.search(pattern, raw_log, re.IGNORECASE):
            return log_type

    return "unknown"


def generate_schema_with_llm(log_type, log_samples):
    """LLM을 사용하여 새로운 로그 타입의 스키마 생성 (vLLM OpenAI API)"""
    if not USE_LLM or not AUTO_SCHEMA_GENERATION:
        return None

    try:
        print(f"[normalizer] 🤖 Generating schema for '{log_type}' using vLLM...")

        # 로그 샘플 포맷팅
        log_samples_text = "\n".join(f"- {log}" for log in log_samples[:5])

        # OpenAI 호환 API 요청
        messages = [
            {
                "role": "system",
                "content": "You are an expert in ECS (Elastic Common Schema) 9.2.0 log analysis and schema generation. Generate accurate, well-structured YAML schemas for log normalization."
            },
            {
                "role": "user",
                "content": f"""다음 {log_type} 로그 샘플을 분석하여 ECS 9.2.0 YAML 매핑 스키마를 생성하세요.

로그 샘플:
{log_samples_text}

플랫폼: {log_type}"""
            }
        ]

        payload = {
            "model": "meta-llama/Meta-Llama-3-8B-Instruct",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 512
        }

        response = requests.post(
            f"{LLM_SERVICE_URL}/v1/chat/completions",
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            generated_text = result["choices"][0]["message"]["content"]

            print(f"[normalizer] ✅ LLM response received for '{log_type}'")

            # YAML 블록 추출
            try:
                if "```yaml" in generated_text:
                    yaml_start = generated_text.find("```yaml") + 7
                    yaml_end = generated_text.find("```", yaml_start)
                    yaml_content = generated_text[yaml_start:yaml_end].strip()
                elif "```" in generated_text:
                    yaml_start = generated_text.find("```") + 3
                    yaml_end = generated_text.find("```", yaml_start)
                    yaml_content = generated_text[yaml_start:yaml_end].strip()
                else:
                    yaml_content = generated_text

                # YAML 파싱
                schema = yaml.safe_load(yaml_content)

                print(f"[normalizer] ✅ Schema parsed for '{log_type}'")

                # 스키마 저장
                save_schema(log_type, schema)

                return schema

            except Exception as parse_error:
                print(f"[normalizer] ⚠️ YAML parsing failed: {parse_error}")
                return None
        else:
            print(f"[normalizer] ⚠️ vLLM service error: {response.status_code}")
            return None

    except Exception as e:
        print(f"[normalizer] ⚠️ Failed to generate schema with vLLM: {e}")
        return None


def save_schema(log_type, schema):
    """생성된 스키마를 파일로 저장"""
    try:
        # mappings 디렉토리에 저장
        mapping_file = NORMALIZER_DIR / "mappings" / f"{log_type}.yaml"

        with open(mapping_file, 'w', encoding='utf-8') as f:
            yaml.dump(schema, f, default_flow_style=False, allow_unicode=True)

        print(f"[normalizer] 💾 Schema saved: {mapping_file}")

        # Normalizer 재초기화 (새 스키마 로드)
        global normalizer
        normalizer = ECSNormalizer(
            schemas_dir=str(NORMALIZER_DIR / "schemas"),
            mappings_dir=str(NORMALIZER_DIR / "mappings")
        )

    except Exception as e:
        print(f"[normalizer] ⚠️ Failed to save schema: {e}")


def send_to_detector(normalized_logs):
    """정규화된 로그를 Detector로 전송"""
    try:
        # message 필드만 추출
        messages = [log.get("message", "") for log in normalized_logs]

        payload = {
            "messages": messages,
            "ecs_logs": normalized_logs
        }

        response = requests.post(DETECTOR_URL, json=payload, timeout=10)

        if response.status_code == 200:
            print(f"[normalizer] ✅ Sent {len(normalized_logs)} logs to detector")
        else:
            print(f"[normalizer] ⚠️ Detector response: {response.status_code}")

    except Exception as e:
        print(f"[normalizer] ⚠️ Failed to send to detector: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
