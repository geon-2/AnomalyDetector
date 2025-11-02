import requests, time

LOG_FILE = "/data/HDFS_2k.log"
PREPROCESSOR_URL = "http://preprocessor:5001/ingest"

def wait_for_preprocessor(max_retries=20, delay=3):
    for i in range(max_retries):
        try:
            r = requests.post(PREPROCESSOR_URL, json={"log": "health_check"})
            if r.status_code == 200:
                print(f"[log-source] ✅ Preprocessor ready (attempt {i+1})")
                return True
        except requests.exceptions.RequestException:
            print(f"[log-source] Waiting for preprocessor... ({i+1}/{max_retries})")
            time.sleep(delay)
    print("[log-source] ❌ Preprocessor not responding, exiting.")
    return False


def stream_logs():
    with open(LOG_FILE) as f:
        for line in f:
            log = line.strip()
            if not log:
                continue
            try:
                r = requests.post(PREPROCESSOR_URL, json={"log": log})
                if r.status_code != 200:
                    print(f"[log-source] ⚠️ Failed ({r.status_code}): {log[:80]}")
            except requests.exceptions.RequestException as e:
                print(f"[log-source] ❌ Connection error: {e}")
            time.sleep(0.2)


if __name__ == "__main__":
    if wait_for_preprocessor():
        stream_logs()
    else:
        exit(1)