#!/bin/bash
set -e

DIR="/mnt/f/Vin AI/Lab 14/K5-L3A-DAY14-ChuVanHiep-2A202603382-Deployment-Benchmark-Observability/06-lab-complete/benchmark-observability/production"
cd "$DIR"
mkdir -p benchmark-results

echo "--- 1. Set scale 1 instance và reload Nginx ---"
docker compose -p k5-day14-observability up -d --scale agent=1
sleep 3
docker restart k5-day14-observability-nginx-1
sleep 3

echo "--- 2. Chạy Locust Benchmark Scale 1 Instance (100 users, 2 phút) ---"
docker compose -p k5-day14-observability run --rm locust \
  -f /mnt/locust/locustfile.py \
  --host http://nginx \
  --headless -u 100 -r 10 -t 2m \
  --csv /mnt/results/scale_1

echo "--- 3. Scale lên 3 Instances và reload Nginx ---"
docker compose -p k5-day14-observability up -d --scale agent=3
sleep 5
docker restart k5-day14-observability-nginx-1
sleep 5

echo "--- 4. Chạy Locust Benchmark Scale 3 Instances (100 users, 2 phút) ---"
docker compose -p k5-day14-observability run --rm locust \
  -f /mnt/locust/locustfile.py \
  --host http://nginx \
  --headless -u 100 -r 10 -t 2m \
  --csv /mnt/results/scale_3

echo "--- 5. Copy benchmark results ra root workspace ---"
mkdir -p "$DIR/../../../../benchmark-results"
cp -r benchmark-results/* "$DIR/../../../../benchmark-results/"

echo "Hoàn thành Locust Scaling Benchmark!"
