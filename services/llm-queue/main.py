from fastapi import FastAPI, Request
import requests
from queue import Queue
import threading
import time

app = FastAPI()
task_queue = Queue()

LLM_SERVICE_URL = "http://llm-service:8000/explain"
VISUALIZER_URL = "http://visualizer-service:8502/event"

@app.post("/push")
async def push_task(request: Request):
    payload = await request.json()
    task_queue.put(payload)
    return {"status": "queued", "queue_size": task_queue.qsize()}

def worker():
    while True:
        task = task_queue.get()
        try:
            llm_result = requests.post(LLM_SERVICE_URL, json={
                "log": task["log"],
                "status": task["status"]
            }, timeout=30).json()

            update_payload = {
                "loss": task["loss"],
                "threshold": task["threshold"],
                "status": task["status"],
                "log": task["log"],
                "llm_analysis": llm_result
            }
            requests.post(VISUALIZER_URL, json=update_payload, timeout=4)
            print("[llm-worker] ✔ updated visualizer with LLM result")
        except Exception as e:
            print(f"[llm-worker] ⚠ Failed LLM job: {e}")
        finally:
            task_queue.task_done()
            time.sleep(0.3)

threading.Thread(target=worker, daemon=True).start()