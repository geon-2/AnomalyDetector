FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install flask torch joblib numpy requests
CMD ["python", "main.py"]