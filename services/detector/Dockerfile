FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    flask==3.0.0 \
    requests==2.31.0 \
    torch==2.0.1 \
    "numpy<2.0" \
    joblib==1.3.2 \
    drain3==0.9.11

# Model files will be copied by Makefile before build
COPY models/ /models/

COPY main.py .

EXPOSE 5002

CMD ["python", "-u", "main.py"]
