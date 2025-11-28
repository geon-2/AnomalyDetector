FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

# Data file will be copied by Makefile before build
COPY HDFS_2k.log /data/HDFS_2k.log

COPY main.py .

CMD ["python", "-u", "main.py"]
