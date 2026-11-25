import time
import httpx
import random

QUESTIONS = [
    "Docker container là gì?",
    "Readiness probe khác gì liveness probe?",
    "Vì sao nên dùng p95 thay vì latency trung bình?",
    "Prometheus thu thập metric như thế nào?",
    "Graceful shutdown hoạt động ra sao khi nhận SIGTERM?",
    "Tính chi phí token của LLM như thế nào?",
]

headers = {"X-API-Key": "day14-lab-key"}

print("Bắt đầu sinh traffic nền cho Grafana và Jaeger (chạy trong 120s)...")
start_time = time.time()
while time.time() - start_time < 120:
    q = random.choice(QUESTIONS)
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post("http://localhost:8080/ask", json={"question": q}, headers=headers)
            client.get("http://localhost:8080/health")
    except Exception:
        pass
    time.sleep(0.3)
print("Hoàn thành đợt sinh traffic!")
