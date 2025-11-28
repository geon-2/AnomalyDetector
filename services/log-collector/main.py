"""
Log Collector Service
로그 파일을 읽어 Normalizer 서비스로 전송
"""
import os
import time
import requests
from pathlib import Path

LOG_FILE = os.getenv("LOG_FILE", "/data/HDFS_2k.log")
NORMALIZER_URL = os.getenv("NORMALIZER_URL", "http://normalizer-service:5001/normalize")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
DELAY = float(os.getenv("DELAY", "0.5"))


def wait_for_service(url, max_retries=30, delay=3):
    """서비스가 준비될 때까지 대기"""
    health_url = url.rsplit('/', 1)[0] + "/health"
    for i in range(max_retries):
        try:
            r = requests.get(health_url, timeout=2)
            if r.status_code == 200:
                print(f"[log-collector] ✅ Service ready (attempt {i+1})")
                return True
        except requests.exceptions.RequestException:
            print(f"[log-collector] Waiting for service... ({i+1}/{max_retries})")
            time.sleep(delay)
    print("[log-collector] ❌ Service not responding, exiting.")
    return False


def stream_logs():
    """로그 파일을 읽어 전송"""
    print(f"[log-collector] Starting log streaming from {LOG_FILE}")

    if not Path(LOG_FILE).exists():
        print(f"[log-collector] ❌ Log file not found: {LOG_FILE}")
        return

    with open(LOG_FILE, 'r') as f:
        batch = []
        line_count = 0

        for line in f:
            log = line.strip()
            if not log:
                continue

            batch.append(log)
            line_count += 1

            if len(batch) >= BATCH_SIZE:
                send_batch(batch)
                batch = []
                time.sleep(DELAY)

        # Send remaining logs
        if batch:
            send_batch(batch)

        print(f"[log-collector] ✅ Finished streaming {line_count} logs")


def send_batch(batch):
    """로그 배치를 Normalizer로 전송"""
    try:
        payload = {"logs": batch, "source": "hdfs"}
        r = requests.post(NORMALIZER_URL, json=payload, timeout=10)

        if r.status_code == 200:
            print(f"[log-collector] ✅ Sent {len(batch)} logs")
        else:
            print(f"[log-collector] ⚠️ Failed ({r.status_code}): {r.text[:100]}")
    except requests.exceptions.RequestException as e:
        print(f"[log-collector] ❌ Connection error: {e}")


if __name__ == "__main__":
    if wait_for_service(NORMALIZER_URL):
        stream_logs()
    else:
        exit(1)
