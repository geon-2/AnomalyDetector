FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG HF_TOKEN
ENV HF_TOKEN=${HF_TOKEN}

# 모델 저장 경로 준비
RUN mkdir -p /models/llm

# 모델 다운로드 후 로컬 디렉토리에 저장
RUN python3 - <<EOF
from transformers import AutoModelForCausalLM, AutoTokenizer
import os, shutil
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
save_dir = "/models/llm"
token = os.getenv("HF_TOKEN")

print("📥 Downloading model to cache...")
tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
model = AutoModelForCausalLM.from_pretrained(model_id, token=token)

print("💾 Saving model to", save_dir)
tokenizer.save_pretrained(save_dir)
model.save_pretrained(save_dir)

print("✅ Model saved successfully")
EOF

COPY main.py .

EXPOSE 8000
CMD ["python", "-u", "main.py"]