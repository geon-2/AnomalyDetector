FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

# Copy only necessary data file (not the whole data folder)
COPY data/HDFS_2k.log /data/HDFS_2k.log

COPY main.py .

CMD ["python", "-u", "main.py"]
