FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir flask==3.0.0

COPY main.py .

EXPOSE 8000

CMD ["python", "-u", "main.py"]
