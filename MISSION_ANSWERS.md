# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Phát hiện Anti-patterns trong `develop/app.py`

Khi phân tích mã nguồn `01-localhost-vs-production/develop/app.py`, phát hiện 7 vấn đề vi phạm nguyên tắc thiết kế ứng dụng production (12-Factor App):

1. **Hardcoded Secrets (Dòng 17–18):**
   * Code: `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
   * Vấn đề: Khóa API và tài khoản cơ sở dữ liệu bị nhúng trực tiếp trong code. Nếu commit lên Git/GitHub, thông tin nhạy cảm sẽ bị lộ ra ngoài ngay lập tức.
2. **Thiếu Configuration Management (Dòng 21–22):**
   * Code: `DEBUG = True` và `MAX_TOKENS = 500`.
   * Vấn đề: Các tham số cấu hình không đọc từ biến môi trường (`.env` / Environment Variables). Không thể thay đổi hành vi ứng dụng giữa các môi trường (dev, staging, production) mà không phải sửa code.
3. **In log thô và làm rò rỉ Secret qua stdout (Dòng 33–34):**
   * Code: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.
   * Vấn đề: Dùng hàm `print()` không có timestamp, log level và in thẳng API key ra log stream, gây vi phạm nghiêm trọng tiêu chuẩn bảo mật và không thể phân tích tự động bằng Log Aggregators (Datadog, Loki, CloudWatch).
4. **Thiếu Health Check & Readiness Endpoints:**
   * Vấn đề: Không có endpoint `/health` (Liveness probe) và `/ready` (Readiness probe). Nền tảng điều phối (Kubernetes, Docker Swarm, Railway, Render) không thể biết container còn hoạt động tốt hay đã bị treo (deadlock) để tự động khởi động lại.
5. **Hardcoded Host và Port cố định (Dòng 49–53):**
   * Code: `host="localhost"`, `port=8000`.
   * Vấn đề: Bind vào `localhost` khiến container bị cô lập hoàn toàn, không thể tiếp nhận kết nối mạng từ bên ngoài container. Cổng `8000` cố định khiến app không thể chạy trên các PaaS cloud (nơi cổng được cấp phát động qua biến môi trường `$PORT`).
6. **Bật debug reload trong Production (Dòng 53):**
   * Code: `reload=True`.
   * Vấn đề: Tính năng tự động reload mã nguồn tiêu tốn nhiều tài nguyên CPU/RAM và tạo lỗ hổng bảo mật nếu deploy trên production.
7. **Không xử lý Graceful Shutdown:**
   * Vấn đề: Ứng dụng không lắng nghe tín hiệu `SIGTERM` từ hệ thống. Khi container dừng lại, các request đang trong quá trình xử lý (in-flight requests) sẽ bị ngắt đột ngột, dẫn đến mất dữ liệu hoặc trả về lỗi 502/504 cho người dùng.

---

### Exercise 1.2: Chạy Basic Version

Khởi động ứng dụng `01-localhost-vs-production/develop/app.py`:
```bash
python app.py
```

Thực hiện gọi API kiểm tra:
```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```

**Kết quả nhận được (HTTP 200 OK):**
```json
{"answer": "Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```
*Nhận xét:* Ứng dụng chạy được trên máy cục bộ nhưng chứa nhiều rủi ro bảo mật, không sẵn sàng để đưa lên môi trường Cloud.

---

### Exercise 1.3: So sánh Develop vs Production

| Tiêu chí | Bản Develop (`develop/app.py`) | Bản Production (`production/app.py`) | Tại sao quan trọng trong Production? |
|---|---|---|---|
| **Cấu hình (Config)** | Hardcode giá trị cố định trực tiếp trong file mã nguồn. | Đọc tập trung qua `config.settings` kế thừa từ `pydantic-settings` / biến môi trường. | Tuân thủ 12-Factor App (Config in environment). Cho phép thay đổi cấu hình linh hoạt giữa các môi trường dev, staging, prod mà không cần build lại code; bảo vệ an toàn các thông tin nhạy cảm. |
| **Health Check** | Không có endpoint kiểm tra sức khỏe. | Có `/health` (Liveness) và `/ready` (Readiness). | Orchestrator (K8s, Docker, Cloud Load Balancer) định kỳ thăm dò tình trạng container. Khi app bị treo, orchestrator tự động restart; khi app chưa tải xong tài nguyên, traffic sẽ không bị route vào. |
| **Ghi Log (Logging)** | Dùng hàm `print()` text thô, in cả secret `OPENAI_API_KEY`. | Structured JSON logging (`logger.info(...)`), ghi rõ timestamp, level, context và tuyệt đối không log secret. | Log dạng JSON tiêu chuẩn giúp các hệ thống Log Aggregator (Elasticsearch, Loki, Datadog) dễ dàng parse, filter, index và cảnh báo lỗi trong thời gian thực. |
| **Host / Port Binding** | `localhost:8000`, `reload=True`. | `0.0.0.0` với dynamic `settings.port`, tắt reload khi ở production. | `0.0.0.0` cho phép đón nhận traffic từ bên ngoài mạng container. Dynamic port giúp tương thích với cơ chế cấp phát cổng của Railway/Render/GCP. |
| **Tắt ứng dụng (Shutdown)** | Tắt đột ngột khi container bị kill. | Bắt tín hiệu `SIGTERM`, dùng FastAPI `lifespan` context manager để graceful shutdown. | Đảm bảo các request đang dở dang (in-flight requests) được phục vụ trọn vẹn trước khi process dừng hẳn; giải phóng kết nối database, redis sạch sẽ. |
| **Bảo mật & CORS** | Không có middleware kiểm soát nguồn gọi. | Tích hợp `CORSMiddleware` với danh sách whitelist domain (`allowed_origins`). | Ngăn chặn các truy vấn giả mạo từ website độc hại (Cross-Origin Request Forgery), đảm bảo chỉ client được cấp phép mới gọi được API. |

---

## Part 2: Docker Containerization

### Exercise 2.1: Phân tích Dockerfile cơ bản (`02-docker/develop/Dockerfile`)

1. **Base image là gì?**
   * Base image được sử dụng là `python:3.11`. Đây là full distribution image của Python dựa trên nền Debian, bao gồm đầy đủ Python runtime, pip, các gói build tools, compiler (gcc, make) và thư viện hệ thống tiêu chuẩn.
2. **Working directory là gì?**
   * Working directory được khai báo qua lệnh `WORKDIR /app`. Đây là thư mục làm việc mặc định bên trong container. Tất cả các lệnh tiếp theo (`COPY`, `RUN`, `CMD`) đều được thực thi tại đường dẫn `/app`.
3. **Tại sao `COPY requirements.txt` trước?**
   * Việc này nhằm tối ưu hóa **Docker Layer Caching**. Docker lưu cache kết quả từng lệnh (layer) theo thứ tự từ trên xuống dưới. Mã nguồn thường xuyên được cập nhật, trong khi danh sách thư viện (`requirements.txt`) ít khi thay đổi. Bằng cách copy `requirements.txt` và chạy `RUN pip install` trước, Docker sẽ tái sử dụng lại layer cài đặt thư viện ở những lần build tiếp theo, giúp giảm thời gian build từ vài phút xuống chỉ vài giây.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?**
   * `ENTRYPOINT`: Xác định tiến trình cố định chạy khi container khởi động (đóng vai trò như executable chính, rất khó bị ghi đè ngẫu nhiên khi chạy lệnh `docker run`).
   * `CMD`: Cung cấp danh sách đối số mặc định cho `ENTRYPOINT`, hoặc đóng vai trò là lệnh mặc định nếu không khai báo `ENTRYPOINT`. `CMD` có thể dễ dàng bị ghi đè bằng cách truyền đối số phía sau `docker run <image> <command>`.

---

### Exercise 2.2: Build và Chạy Container Develop

Lệnh build từ thư mục gốc:
```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
```

Khởi động container ở chế độ nền:
```bash
docker run -d --name test-agent-dev -p 8000:8000 my-agent:develop
```

Gọi kiểm tra API:
```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```
**Kết quả trả về:**
```json
{"answer": "Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Dọn dẹp container:
```bash
docker stop test-agent-dev && docker rm test-agent-dev
```

---

### Exercise 2.3: So sánh Kích Thước Multi-stage Build

Build image production sử dụng kỹ thuật Multi-stage:
```bash
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
```

Kiểm tra kích thước image thực tế đo được từ lệnh `docker images`:
```text
REPOSITORY            TAG       IMAGE ID       SIZE (Virtual)   DISK USAGE
my-agent:develop      latest    2054f28da6ff   1.67 GB          426 MB
my-agent:advanced     latest    621ab9c441e6   240 MB           57.4 MB
```

* **Dung lượng develop:** `1.67 GB`
* **Dung lượng production:** `240 MB`
* **Mức độ giảm dung lượng:**
  $$\frac{1670 - 240}{1670} \times 100\% \approx \mathbf{85.6\%}$$

**Tại sao Multi-stage build giảm được dung lượng lớn như vậy?**
* **Stage 1 (Builder):** Sử dụng `python:3.11-slim`, cài đặt thêm `gcc`, `libpq-dev` và các build tools để compile các thư viện C/Python. Thư viện được cài vào thư mục `/root/.local`. Stage này chứa rất nhiều rác build và package compiler tạm thời.
* **Stage 2 (Runtime):** Khởi tạo từ một base image `python:3.11-slim` hoàn toàn mới và sạch (~150 MB). Chỉ copy thư mục dependencies đã build (`/root/.local`) từ Stage 1 sang `/home/appuser/.local`, không mang theo `gcc`, compiler hay cache của apt.
* **Bảo mật tăng cường:** Tạo và chuyển quyền sang user không đặc quyền (`USER appuser`), không chạy với quyền `root`.

---

### Exercise 2.4: Sơ đồ kiến trúc Docker Compose Stack

File `02-docker/production/docker-compose.yml` điều phối cụm microservices:

```
                  ┌──────────────────────────────┐
                  │        Client / Web          │
                  └──────────────┬───────────────┘
                                 │
                         HTTP Request (Port 80)
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │            Nginx             │
                  │   (Reverse Proxy / Ingress)  │
                  └──────────────┬───────────────┘
                                 │
                       Proxy Pass (Port 8000)
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │       FastAPI Agent          │
                  │      (2 Replicas / App)      │
                  └──────┬────────────────┬──────┘
                         │                │
            Cache & Rate Limit     Vector Similarity
             (Port 6379/TCP)        (Port 6333/TCP)
                         │                │
                         ▼                ▼
                  ┌──────────────┐ ┌──────────────┐
                  │    Redis     │ │    Qdrant    │
                  │ (In-memory)  │ │ (Vector DB)  │
                  └──────────────┘ └──────────────┘
```

**Cách các service tương tác:**
1. **Nginx:** Đóng vai trò là cửa ngõ tiếp nhận duy nhất từ bên ngoài qua cổng 80/443. Nginx điều hướng các yêu cầu `/` và `/health` vào service `agent` qua mạng nội bộ Docker (`internal`).
2. **Agent:** Ứng dụng AI Agent FastAPI lắng nghe trên cổng 8000 trong mạng nội bộ, chỉ expose qua Nginx nhằm che giấu hạ tầng backend.
3. **Redis:** Lưu trữ phiên làm việc (Session) và đếm lượt gọi phục vụ Rate Limiting.
4. **Qdrant:** Cơ sở dữ liệu Vector phục vụ truy xuất thông tin tăng cường (RAG).
5. **Cơ chế Healthcheck & Depends_on:** Service `agent` phụ thuộc vào `redis` và `qdrant` với điều kiện `condition: service_healthy`, đảm bảo agent chỉ nhận request khi các kho dữ liệu phụ trợ đã sẵn sàng.

---

## Part 3: Cloud Deployment

### Exercise 3.1 & 3.2: Triển Khai Cloud & So Sánh `railway.toml` vs `render.yaml`

#### 1. Thông tin triển khai Agent Part 6:
* Theo quy định dành riêng cho lớp K5 (mục *Lưu ý khi làm bài* số 8 trong `README.md`), sinh viên triển khai trực tiếp mã nguồn production hoàn chỉnh từ thư mục `06-lab-complete/` lên Cloud (kèm dịch vụ Redis Cloud) thay vì deploy ứng dụng mẫu.
* Chi tiết Public URL, các biến môi trường và kết quả 4 lệnh kiểm thử HTTP (200, 200, 401, 200) được ghi nhận đầy đủ tại [DEPLOYMENT.md](DEPLOYMENT.md).

#### 2. So sánh cấu hình giữa `railway.toml` và `render.yaml`:

| Tiêu chí | Railway (`railway.toml`) | Render Blueprint (`render.yaml`) | Phân tích lý do kỹ thuật |
|---|---|---|---|
| **Định dạng & Tiêu chuẩn** | Cấu hình dạng **TOML** ngắn gọn, tập trung chủ yếu vào runtime và builder. | Cấu hình dạng **YAML** theo mô hình Infrastructure-as-Code (IaC) toàn diện (Blueprint). | `railway.toml` hướng tới tính tiện dụng, nhanh gọn cho service đơn lẻ. `render.yaml` chuẩn hóa toàn bộ hạ tầng (web app, database, worker) thành mã nguồn (IaC) có thể tái sử dụng và kiểm soát phiên bản qua Git. |
| **Builder & Image** | Khai báo `[build] builder = "DOCKERFILE"`. | Khai báo `type: web`, `runtime: docker`. | Cả hai đều hỗ trợ build từ Dockerfile đa tầng (multi-stage), đảm bảo container chạy giống hệt máy local. |
| **Health Check Path** | `[deploy] healthcheckPath = "/health"`. | `healthCheckPath: /health`. | Định nghĩa endpoint liveness probe để nền tảng tự động kiểm tra tình trạng sống của container và tự động chuyển hướng traffic khi dịch vụ khởi động hoàn tất. |
| **Quản lý Secrets & Biến môi trường** | Thiết lập trực tiếp trên web dashboard hoặc qua Railway CLI (`railway variables set AGENT_API_KEY=...`). | Khai báo rõ ràng trong YAML: hỗ trợ thuộc tính `generateValue: true` (tự sinh secret ngẫu nhiên) hoặc `sync: false` (yêu cầu người dùng điền trên dashboard). | Cách tiếp cận của Render Blueprint giúp ngăn chặn triệt để việc vô tình ghi đè hoặc lộ secret plaintext vào file cấu hình được commit lên GitHub. |
| **Điều phối đa dịch vụ (Multi-service)** | Quản lý Redis thông qua tính năng plugin/template trên UI của Railway project. | Hỗ trợ khai báo đồng thời cả service web (`type: web`) và Redis instance (`type: redis`) trong cùng một file `render.yaml`. | Render cho phép quản trị toàn bộ cụm microservice phụ thuộc trong cùng một tệp blueprint duy nhất. |

---

### Exercise 3.3: Phân Tích Pipeline CI/CD Google Cloud Run (`cloudbuild.yaml` + `service.yaml`)

Đọc và phân tích kiến trúc CI/CD trong `03-cloud-deployment/production-cloud-run/`:
1. **Trigger tự động:** Pipeline được cấu hình tự động kích hoạt mỗi khi có commit mới được push lên nhánh chính (`main`).
2. **Luồng thực thi tuần tự 4 bước (`cloudbuild.yaml`):**
   * **Bước 1 (Test):** Sử dụng container `python:3.11-slim`, cài đặt dependencies và chạy toàn bộ unit tests qua `pytest tests/ -v`. Chỉ khi toàn bộ test PASS thì pipeline mới cho phép chuyển sang bước sau.
   * **Bước 2 (Build):** Dùng Docker builder (`gcr.io/cloud-builders/docker`) để đóng gói mã nguồn thành Docker image, gán 2 tag là `$COMMIT_SHA` (định danh phiên bản duy nhất để rollback) và `latest`, kết hợp `--cache-from` để tối ưu layer caching.
   * **Bước 3 (Push):** Đẩy đồng thời các image tags lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
   * **Bước 4 (Deploy):** Dùng công cụ `gcloud` deploy image vừa build lên **Cloud Run** tại khu vực `asia-southeast1` ở chế độ managed, public unauthenticated endpoint.
3. **Cấu hình Hạ tầng & Độ tin cậy (`service.yaml`):**
   * **Serverless Autoscaling:** Cấu hình `minScale: 1` (giữ ít nhất 1 container luôn chạy để loại bỏ hiện tượng *Cold Start* cho người dùng) và `maxScale: 10` để kiểm soát trần chi phí.
   * **Bảo mật Secret:** Khóa API (`OPENAI_API_KEY`, `AGENT_API_KEY`) không truyền qua biến thông thường mà được trích xuất an toàn từ **Google Secret Manager** (`valueFrom.secretKeyRef`).
   * **Health Monitoring:** Thiết lập `livenessProbe` gọi `/health` định kỳ 30 giây và `startupProbe` gọi `/ready` mỗi 3 giây để đảm bảo container sẵn sàng phục vụ trước khi nhận traffic.

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (Develop)

Phân tích cơ chế kiểm thực trong `04-api-gateway/develop/app.py`:
1. **API Key được kiểm tra ở đâu?**
   * Được kiểm tra thông qua FastAPI dependency `verify_api_key(api_key: str = Security(api_key_header))` (dòng 39–55), được inject trực tiếp vào endpoint `POST /ask` qua cú pháp `_key: str = Depends(verify_api_key)`.
2. **Điều gì xảy ra nếu sai key hoặc thiếu key?**
   * **Thiếu key:** Header `X-API-Key` không được gửi $\rightarrow$ Trả về mã lỗi **`HTTP 401 Unauthorized`** kèm thông báo `"Missing API key. Include header: X-API-Key: <your-key>"`.
   * **Sai key:** Key gửi lên không khớp với giá trị cấu hình `AGENT_API_KEY` $\rightarrow$ Trả về mã lỗi **`HTTP 403 Forbidden`** kèm thông báo `"Invalid API key."`.
3. **Làm sao rotate (đổi) key?**
   * Key được đọc động từ biến môi trường `AGENT_API_KEY` (`API_KEY = os.getenv("AGENT_API_KEY", ...)`).
   * Để xoay vòng key, chỉ cần cập nhật giá trị biến môi trường `AGENT_API_KEY` mới trong tệp cấu hình/dashboard PaaS và khởi động lại container/service mà không cần chỉnh sửa hay build lại mã nguồn. Trong production, có thể hỗ trợ danh sách nhiều key hợp lệ (key cũ và key mới) trong một khoảng thời gian ân hạn (grace period) trước khi thu hồi hoàn toàn key cũ.

---

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting Test Results

Kiểm thử thực tế trên phiên bản `04-api-gateway/production/app.py` với tài khoản `student` / `demo123` (hạn mức 10 requests/phút):

#### 1. Gọi khi không có Token (HTTP 401 Unauthorized):
```http
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 08:01:34 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 76
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Not authenticated"}
```

#### 2. Lấy JWT Token qua `POST /auth/token`:
```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'
```
*Token nhận được (đã che để bảo mật):*
```text
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdHVkZW50Iiwicm9sZSI6InVzZXIiLCJleHAiOjE3OTU1OTczNTR9...
```

#### 3. Gọi hợp lệ có Token (HTTP 200 OK):
```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:01:34 GMT
server: uvicorn
content-length: 196
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{
  "question": "what is docker?",
  "answer": "Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!",
  "usage": {
    "requests_remaining": 9,
    "budget_remaining_usd": 0.000019
  }
}
```

#### 4. Gọi liên tiếp kiểm tra Rate Limiting (15 requests liên tiếp):
```text
Request  1: HTTP 200
Request  2: HTTP 200
Request  3: HTTP 200
Request  4: HTTP 200
Request  5: HTTP 200
Request  6: HTTP 200
Request  7: HTTP 200
Request  8: HTTP 200
Request  9: HTTP 200
Request 10: HTTP 429
Request 11: HTTP 429
Request 12: HTTP 429
Request 13: HTTP 429
Request 14: HTTP 429
Request 15: HTTP 429
```

#### 5. Chi tiết Response khi vượt ngưỡng Rate Limit (HTTP 429 Too Many Requests):
```http
HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 08:01:36 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795593756
retry-after: 59
content-length: 98
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{
  "detail": {
    "error": "Rate limit exceeded",
    "limit": 10,
    "window_seconds": 60,
    "retry_after_seconds": 59
  }
}
```

**Phân tích thuật toán Rate Limiting (`rate_limiter.py`):**
* **Thuật toán sử dụng:** **Sliding Window Counter** (sử dụng cấu trúc `collections.deque` lưu timestamps của các request).
* **Cơ chế hoạt động:** Khi một request đến, thuật toán dọn dẹp các timestamp cũ ngoài khung thời gian trượt 60 giây (`now - window_seconds`). Nếu số lượng phần tử còn lại trong window vượt quá `max_requests`, hệ thống tính toán thời gian `retry_after_seconds` từ timestamp cũ nhất và trả về mã lỗi 429 kèm header `Retry-After`.
* **Hạn mức:** 10 requests/phút đối với người dùng thông thường (`student`), và 100 requests/phút đối với quản trị viên (`teacher`/`admin`).
* **Bypass limit cho admin:** Hệ thống kiểm tra trường `role` trong payload của JWT Token (`user["role"] == "admin"`). Nếu là admin, request sẽ được điều hướng qua instance `rate_limiter_admin` với quota cao gấp 10 lần hoặc có thể bypass hoàn toàn kiểm tra rate limit.

---

### Exercise 4.4: Thiết Kế và Cài Đặt Cost Guard

#### 1. Tại sao cần cả Rate Limiting và Cost Guard?
* **Rate Limiting bảo vệ Tốc độ (Velocity Protection):** Ngăn chặn tấn công flood/DDoS, spam requests liên tục làm nghẽn đường truyền và quá tải tài nguyên máy chủ (CPU, RAM, Event Loop) trong thời gian ngắn (tính theo giây/phút).
* **Cost Guard bảo vệ Ngân sách (Financial Protection):** Một client có thể gọi rất chậm (1 request/phút — hoàn toàn vượt qua Rate Limit), nhưng mỗi request gửi một prompt khổng lồ kèm context dài (ví dụ: 100,000 tokens). Điều này làm cạn kiệt ngân sách API OpenAI/Anthropic hàng nghìn USD. Cost Guard đo lường lượng token tiêu thụ tích lũy (theo ngày/tháng) và chặn truy cập bằng mã **`HTTP 402 Payment Required`** khi vượt quá ngân sách định mức.

#### 2. Kiến trúc Cost Guard với Redis:
Để hoạt động chính xác trong môi trường phân tán (nhiều instance agent), Cost Guard cần lưu trạng thái tích lũy vào Redis:
* **Key thiết kế:** `budget:{user_id}:{YYYY-MM}` (theo dõi theo tháng) hoặc `budget:{user_id}:{YYYY-MM-DD}` (theo dõi theo ngày).
* **Luồng xử lý:**
  1. **Pre-check:** Trước khi forward request sang LLM, kiểm tra giá trị hiện tại `r.get(key)`. Nếu `current_cost >= monthly_budget`, từ chối ngay với `HTTP 402 Payment Required`.
  2. **Call LLM:** Gọi LLM và tính toán số token thực tế (`prompt_tokens`, `completion_tokens`).
  3. **Post-record:** Tính chi phí phát sinh:
     $$\text{Cost} = \frac{\text{Input Tokens}}{1000} \times P_{\text{input}} + \frac{\text{Output Tokens}}{1000} \times P_{\text{output}}$$
     Gọi `r.incrbyfloat(key, cost)` và gán TTL 32 ngày (`r.expire(key, 32 * 86400)`) để tự động giải phóng bộ nhớ.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Liveness Probe (`/health`) vs Readiness Probe (`/ready`)

Phân tích sự khác biệt cốt lõi giữa hai loại health checks trong hạ tầng production:

| Đặc tính | Liveness Probe (`GET /health`) | Readiness Probe (`GET /ready`) |
|---|---|---|
| **Câu hỏi cần trả lời** | "Tiến trình (process) của ứng dụng có còn sống không?" | "Ứng dụng đã sẵn sàng tiếp nhận traffic của người dùng chưa?" |
| **Mục đích kiểm tra** | Phát hiện deadlocks, memory leaks, crash ngầm hoặc infinite loop khiến tiến trình bị treo. | Kiểm tra các phụ thuộc hạ tầng (Database, Redis đã kết nối chưa? Model AI/weights đã nạp xong vào RAM chưa?). |
| **Hành động của Orchestrator** | Nếu trả về lỗi (non-200) $\rightarrow$ Orchestrator (K8s, Docker) sẽ **kill container và khởi động lại container mới** (Restart). | Nếu trả về lỗi (`503 Service Unavailable`) $\rightarrow$ Load balancer **tạm ngắt route traffic** tới container đó mà **không restart**, chờ đến khi sẵn sàng. |
| **Trạng thái khi Redis sập** | Vẫn phải trả về **`200 OK`** (vì process web server uvicorn vẫn đang sống, không nên restart liên tục gây crash loop). | Phải trả về **`503 Service Unavailable`** (vì thiếu Redis thì agent không thể đọc/ghi session hay kiểm tra rate limit). |

---

### Exercise 5.2: Cơ Chế Graceful Shutdown

Kiến trúc xử lý tắt an toàn (Graceful Shutdown) trong `05-scaling-reliability/develop/app.py`:
1. **Lắng nghe tín hiệu `SIGTERM`:** Khi platform/orchestrator muốn dừng container (để cập nhật phiên bản hoặc scale down), nó gửi tín hiệu `SIGTERM` (signal 15) trước khi dùng `SIGKILL` (signal 9).
2. **Ngừng nhận request mới:** Ngay khi nhận `SIGTERM`, server chuyển cờ `_is_ready = False`. Khi đó endpoint `/ready` lập tức trả về `503`, báo cho Load Balancer ngắt route các kết nối mới vào instance này.
3. **Phục vụ trọn vẹn request đang dở dang (In-flight requests):**
   * Middleware `track_requests` duy trì biến đếm `_in_flight_requests`.
   * Khi shutdown, hàm lifespan context manager chờ `_in_flight_requests == 0` (với timeout an toàn tối đa 30s).
   * Các request người dùng đang gửi (ví dụ: đang đợi LLM sinh câu trả lời mất 2–3 giây) vẫn được phục vụ hoàn chỉnh và trả về `200 OK`.
4. **Giải phóng tài nguyên:** Đóng các kết nối Redis/DB pool rồi tiến trình mới chính thức dừng với exit code `0`.

---

### Exercise 5.3: Stateless Design vs Stateful Design

* **Vấn đề của Stateful (Lưu Session trong RAM):**
  * Khi mở rộng hệ thống lên nhiều instance ($N > 1$) phía sau Nginx/Load Balancer, thuật toán Round-Robin sẽ phân phối các lượt request liên tiếp của cùng một người dùng tới các container ngẫu nhiên khác nhau.
  * Nếu lưu lịch sử chat trong RAM cục bộ (`dict` hoặc `list` trong memory), khi request 1 rơi vào Instance 1 (lưu session), request 2 rơi vào Instance 2 (không tìm thấy session) $\rightarrow$ Ngữ cảnh bị mất, Agent trả lời ngô nghê hoặc crash.
* **Giải pháp Stateless với Redis:**
  * Toàn bộ trạng thái phiên làm việc (Chat History, Token Budget, Rate Limit Window) được lưu trữ tập trung tại **Redis**.
  * Các container Agent trở thành hoàn toàn "không trạng thái" (stateless). Bất kỳ instance nào nhận được request cũng chỉ cần dùng `session_id` để lấy toàn bộ lịch sử từ Redis, xử lý xong lại ghi ngược vào Redis.
  * Cho phép hệ thống scale ngang tùy ý (3, 10, hay 100 instances) và thực hiện **Zero-downtime Rolling Deploy** (tắt từng container cũ, bật container mới mà người dùng không hề bị mất phiên).

---

### Exercise 5.4 & 5.5: Kết Quả Kiểm Thử Thực Tế Khi Scale 3 Instance Agent

Khởi động cụm 3 Agent Instances + Redis + Nginx Load Balancer:
```bash
docker compose -f 05-scaling-reliability/production/docker-compose.yml -p k5-day14-scaling up -d --build --scale agent=3
```

Thực thi kịch bản kiểm thử gửi 5 câu hỏi liên tiếp trong cùng 1 session qua Nginx (Port 8080):
```bash
python test_stateless.py
```

**Output đo lường thực tế:**
```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 2a416624-0c8c-4211-9bc8-142ebc24242e

Request 1: [instance-24119e]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-ba35a6]
  Q: Why do we need containers?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 3: [instance-2218ef]
  Q: What is Kubernetes?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 4: [instance-24119e]
  Q: How does load balancing work?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

Request 5: [instance-ba35a6]
  Q: What is Redis used for?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-2218ef', 'instance-24119e', 'instance-ba35a6'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
  [user]: What is Kubernetes?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: How does load balancing work?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...
  [user]: What is Redis used for?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...

✅ Session history preserved across all instances via Redis!
```

**Nhận xét kết quả:**
* 5 request liên tiếp trong cùng session `2a416624-0c8c-4211-9bc8-142ebc24242e` được Nginx điều phối luân phiên qua cả 3 instance khác nhau (`instance-2218ef`, `instance-24119e`, `instance-ba35a6`).
* Toàn bộ 10 tin nhắn hội thoại (5 câu hỏi của user và 5 câu trả lời của assistant) đều được lưu trữ toàn vẹn và đọc ra chính xác từ Redis.
* Chứng minh kiến trúc Stateless + Redis Cache hoạt động hoàn hảo khi scale ngang.

Dọn dẹp cụm containers:
```bash
docker compose -f 05-scaling-reliability/production/docker-compose.yml -p k5-day14-scaling down
```

---

## Part 6: Final Project Deliverable

### Kết Quả Chạy `check_production_ready.py` (Chế độ đầy đủ, Docker)

Toàn bộ 12 tiêu chí đánh giá Production Readiness đều đạt tối đa (**`PASS 12/12`**, **43/43 checks passed**):

```text
================================================================
  Production Readiness Check — Day 14 Lab
================================================================

✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Dockerfile tồn tại
     ✅ requirements.txt tồn tại
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn (slim / alpine / distroless) — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 25s
     ✅ Docker: image < 500 MB — 238 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
     ✅ docker-compose.yml tồn tại
     ✅ Có service agent (build từ Dockerfile) + redis — services: agent, redis — đọc bằng docker compose config
     ✅ Service agent kết nối redis (REDIS_URL + depends_on)

✅ 3. .dockerignore
     ✅ .dockerignore tồn tại và có nội dung
     ✅ .dockerignore loại trừ .env (secrets)
     ✅ .dockerignore loại trừ __pycache__, venv

✅ 4. Health check endpoint (GET /health)
     ✅ Code có route /health
     ✅ Khi chạy: GET /health → 200 — uvicorn --workers 2

✅ 5. Readiness endpoint (GET /ready)
     ✅ Code có route /ready
     ✅ Khi chạy: GET /ready → 200
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
     ✅ Code đọc header X-API-Key
     ✅ Khi chạy: thiếu / sai API key → 401
     ✅ Khi chạy: API key đúng → 200

✅ 7. Rate limiting
     ✅ Code trả HTTP 429 khi vượt giới hạn
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Code trả HTTP 402 khi hết budget
     ✅ Khi chạy: hết budget → 402 — 402 ở request thứ 1

✅ 9. Config từ environment variables
     ✅ app/config.py đọc biến môi trường
     ✅ .env.example liệt kê đủ biến cấu hình
     ✅ .env nằm trong .gitignore
     ✅ Không hard-code secret trong code
     ✅ Khi chạy: agent dùng AGENT_API_KEY và RATE_LIMIT_PER_MINUTE từ env

✅ 10. Structured logging
     ✅ Code ghi log dạng JSON
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 7 dòng JSON

✅ 11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ✅ Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — exit code 0
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 0.7s

✅ 12. Public URL ready (Railway / Render config)
     ✅ Có railway.toml hoặc render.yaml (không chỉ toàn comment)
     ✅ railway.toml: builder + healthcheckPath = "/health"
     ✅ render.yaml: web service + healthCheckPath /health
     ✅ render.yaml: secret không ghi thẳng giá trị (generateValue / sync: false)
     ✅ App lắng nghe theo biến PORT do platform cấp

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

## AI Log
*(Ghi nhận quá trình tương tác, kiểm thử và rà soát lỗi)*
* **Mục đích sử dụng:** Phân tích mã nguồn anti-patterns, thiết lập môi trường WSL2, đối soát lệnh build Docker multi-stage, đo đạc kích thước thực tế, kiểm thử luồng bảo mật API Gateway (Part 4), kiểm thử kiến trúc Stateless Agent mở rộng 3 instances với Redis và Nginx (Part 5), hoàn thiện toàn bộ mã nguồn production agent trong `06-lab-complete/` (Part 6) đạt chuẩn 12-factor production readiness (`PASS 12/12`), và phân tích hạ tầng Cloud Deployment (Part 3: so sánh Railway vs Render, phân tích pipeline Cloud Run CI/CD).
* **Kiểm tra độc lập:** Tự chạy các container, gửi curl requests đo lường thực tế kết quả 401, 200, 429, chạy `test_stateless.py` xác minh 3 instances phục vụ chung 1 session, đối chiếu kích thước image qua `docker images`, phân tích cú pháp `cloudbuild.yaml` và `service.yaml`, và thực thi kiểm thử tự động toàn diện qua `check_production_ready.py` (chế độ đầy đủ kèm Docker) đạt chứng nhận `PASS 12/12`.
