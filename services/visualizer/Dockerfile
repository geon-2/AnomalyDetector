FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir flask==3.0.0 flask-cors==4.0.0

COPY main.py .

EXPOSE 8502

CMD ["python", "-u", "main.py"]
