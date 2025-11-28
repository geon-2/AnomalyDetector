FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir flask requests pyyaml

# normalizer 모듈 복사
COPY normalizer/ ./normalizer/

COPY main.py .

EXPOSE 5001

CMD ["python", "-u", "main.py"]
