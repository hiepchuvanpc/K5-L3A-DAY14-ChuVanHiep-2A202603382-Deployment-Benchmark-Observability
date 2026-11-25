# Deployment Information

## Public URL
https://k5-day14-agent-pljl.onrender.com

## Platform
Render

## Test Commands

### Health Check
```bash
curl -i https://k5-day14-agent-pljl.onrender.com/health
# Expected: HTTP/1.1 200 OK
```

### Readiness Check
```bash
curl -i https://k5-day14-agent-pljl.onrender.com/ready
# Expected: HTTP/1.1 200 OK (hoặc 503 nếu không dùng Redis)
```

### Authentication Test (Unauthorized)
```bash
curl -i -X POST https://k5-day14-agent-pljl.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: HTTP/1.1 401 Unauthorized
```

### API Test (With Authentication)
```bash
curl -i -X POST https://k5-day14-agent-pljl.onrender.com/ask \
  -H "X-API-Key: day14-lab-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "Docker container là gì?"}'
# Expected: HTTP/1.1 200 OK
```

## Environment Variables Set

- `PORT`
- `ENVIRONMENT`
- `AGENT_API_KEY`
- `RATE_LIMIT_PER_MINUTE`
- `DAILY_BUDGET_USD`

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
