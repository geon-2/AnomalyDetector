FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install flask drain3 requests
CMD ["python", "main.py"]