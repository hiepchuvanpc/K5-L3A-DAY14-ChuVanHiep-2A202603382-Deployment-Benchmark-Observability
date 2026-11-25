# Deployment Information

## Public URL
https://k5-day14-agent-production.up.railway.app

## Platform
Railway / Render / Cloud Run

## Test Commands

Chạy với biến `BASE` trỏ tới URL public và `AGENT_API_KEY` đã đặt trên cloud:

```bash
BASE="https://k5-day14-agent-production.up.railway.app"
AGENT_API_KEY="your-secret-api-key"

# 1. Kiểm tra Liveness probe (Mong đợi HTTP 200)
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Kết quả: 200

# 2. Kiểm tra Readiness probe (Mong đợi HTTP 200 khi Redis kết nối tốt)
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Kết quả: 200

# 3. Kiểm tra bảo vệ Auth khi thiếu/sai Key (Mong đợi HTTP 401)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
# Kết quả: 401

# 4. Kiểm tra gọi Agent thành công khi có API Key đúng (Mong đợi HTTP 200)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
# Kết quả: 200
```

---

## Environment Variables Set

- `PORT`
- `ENVIRONMENT`
- `AGENT_API_KEY`
- `REDIS_URL`
- `RATE_LIMIT_PER_MINUTE`
- `DAILY_BUDGET_USD`

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
