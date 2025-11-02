import requests, time

LOG_FILE = "/data/HDFS_2k.log"

with open(LOG_FILE) as f:
    for line in f:
        log = line.strip()
        if log:
            requests.post("http://preprocessor:5000/ingest", json={"log": log})
            time.sleep(0.2)