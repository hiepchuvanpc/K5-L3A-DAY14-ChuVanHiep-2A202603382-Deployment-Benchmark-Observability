#!/bin/bash
set -e

REPO_DIR="/mnt/f/Vin AI/Lab 14/K5-L3A-DAY14-ChuVanHiep-2A202603382-Deployment-Benchmark-Observability/06-lab-complete/benchmark-observability/develop"
cd "$REPO_DIR"
mkdir -p reports

echo "Dọn dẹp tiến trình app.py cũ..."
pkill -f 'app.py' || true
sleep 1

echo "Khởi động Agent v2 (đã cập nhật Knowledge Base) trên port 8002..."
PORT=8002 AGENT_VERSION=v2 /root/lab_venv/bin/python app.py > /tmp/agent_v2.log 2>&1 &

echo "Đang đợi service v2 sẵn sàng..."
for i in {1..30}; do
  if curl -s http://localhost:8002/metrics > /dev/null; then
    echo "Agent v2 đã sẵn sàng!"
    break
  fi
  sleep 0.5
done

echo "=== 1. Đánh giá chất lượng v2 sau khi sửa KB (eval v2 fixed) ==="
/root/lab_venv/bin/python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json || true

echo "=== 2. Chạy Load Test v2 với concurrency 100 ==="
/root/lab_venv/bin/python load_test.py --url http://localhost:8002 --requests 300 --concurrency 100 --out reports/load_v2_c100.json || true

echo "=== 3. Chạy Tail Latency Test ==="
echo "Đo MOCK_SLOW_RATE=0.03..."
/root/lab_venv/bin/python load_test.py --url http://localhost:8002 --requests 300 --concurrency 10 --out reports/load_v2_slow_0.03.json || true

echo "Đo MOCK_SLOW_RATE=0..."
PORT=8003 AGENT_VERSION=v2 MOCK_SLOW_RATE=0 /root/lab_venv/bin/python app.py > /tmp/agent_v2_slow0.log 2>&1 &
sleep 2
/root/lab_venv/bin/python load_test.py --url http://localhost:8003 --requests 300 --concurrency 10 --out reports/load_v2_slow_0.json || true
pkill -f 'PORT=8003' || true

echo "Đo MOCK_SLOW_RATE=0.1..."
PORT=8004 AGENT_VERSION=v2 MOCK_SLOW_RATE=0.1 /root/lab_venv/bin/python app.py > /tmp/agent_v2_slow01.log 2>&1 &
sleep 2
/root/lab_venv/bin/python load_test.py --url http://localhost:8004 --requests 300 --concurrency 10 --out reports/load_v2_slow_0.1.json || true
pkill -f 'PORT=8004' || true

# Copy toàn bộ reports ra root workspace
echo "Đồng bộ thư mục reports ra thư mục gốc repo..."
mkdir -p "$REPO_DIR/../../../../reports"
cp -r "$REPO_DIR/reports/"* "$REPO_DIR/../../../../reports/"

echo "Hoàn thành toàn bộ Benchmark Part 7.1!"
