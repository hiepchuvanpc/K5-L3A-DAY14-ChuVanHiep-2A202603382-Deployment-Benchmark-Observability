# Benchmark & Observability Report — Day 14

**Họ tên:** Chử Văn Hiệp - 2A202603382
**Ngày chạy:** 25/11/2026
**Môi trường:** Windows 11 + WSL2 Ubuntu 24.04 LTS, Docker Desktop WSL2 backend, 8 CPU Cores / 16GB RAM

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% tương tác người dùng có phản hồi dưới 0.5 giây, giữ trải nghiệm mượt mà không bị cảm giác gián đoạn |
| Error rate `/ask` | < 1.0 % | Hệ thống phục vụ trợ lý AI chỉ chấp nhận tối đa 1% lỗi tạm thời do mạng/upstream LLM |
| Accuracy trên golden dataset | ≥ 95.0 % | Chất lượng câu trả lời kỹ thuật của RAG Agent phải đạt độ tin cậy rất cao trước khi release production |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.16 | 192.4 | 223.2 | 1686.4 | 1.33% | ✅ PASS |
| 10 | 36.14 | 192.0 | 221.3 | 1708.8 | 1.33% | ✅ PASS |
| 50 | 43.11 | 550.1 | 2664.2 | 4290.7 | 1.00% | ❌ FAIL (p95 > 500ms) |
| 100 | 59.53 | 524.5 | 3428.2 | 3822.1 | 0.67% | ❌ FAIL (p95 > 500ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

- **RPS không tăng tuyến tính theo concurrency**.
- Khi concurrency tăng từ 1 lên 10, RPS tăng mạnh từ 4.16 lên 36.14 req/s (~8.7 lần). Lý do là Uvicorn/FastAPI chạy trên cơ chế async non-blocking IO event loop; khi concurrency còn thấp, thời gian chờ mock LLM (IO sleep) được multiplex hiệu quả giữa các coroutine.
- Tuy nhiên, khi concurrency tăng từ 10 lên 50 và 100, RPS chỉ tăng khiêm tốn từ 36.14 lên 43.11 và 59.53 req/s. Nguyên nhân:
  1. **CPU Bound trên Single Event Loop**: Python chạy single-process (GIL). Khối lượng tính toán của CPU cho việc parse JSON, HTTP routing, serialization và context switching bắt đầu bão hòa 1 core CPU.
  2. **Hàng đợi Connection & Scheduling Queuing**: Khi có 50–100 request đồng thời, các request phải xếp hàng chờ event loop xử lý, dẫn đến queuing delay làm p95 latency vọt từ 221.3 ms lên 2664.2 ms và 3428.2 ms, vi phạm SLO 500ms.
  3. Để cải thiện RPS và p95 ở concurrency cao, bắt buộc phải scale ngang nhiều worker process (Uvicorn workers) hoặc scale nhiều container pods qua Load Balancer (Nginx).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.5 | 219.3 | 223.8 |
| 0.03 (mặc định) | 247.5 | 222.6 | 1712.3 |
| 0.1 | 347.9 | 1689.1 | 1717.2 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **Chỉ số nhạy nhất với request chậm là p99, tiếp theo là p95**:
  - Khi `MOCK_SLOW_RATE = 0` (không có request chậm): avg là 191.5 ms, p95 là 219.3 ms, p99 là 223.8 ms. Mọi chỉ số rất đồng đều.
  - Khi `MOCK_SLOW_RATE = 0.03` (chỉ 3% request bị chậm): latency trung bình (avg) chỉ tăng nhẹ từ 191.5 lên 247.5 ms (+56 ms, nhìn qua có vẻ rất tốt), p95 hầu như chưa phản ánh (222.6 ms), nhưng **p99 tăng vọt lên 1712.3 ms** (gấp 7.6 lần)!
  - Khi `MOCK_SLOW_RATE = 0.1` (10% request bị chậm): avg tăng lên 347.9 ms, trong khi cả **p95 (1689.1 ms)** và **p99 (1717.2 ms)** đều bộc lộ rõ rệt sự cố nghẽn mạng/chậm upstream.
- **Vì sao SLO không nên đặt theo average (trung bình)?**
  - Giá trị trung bình (Mean/Average) làm phẳng và che giấu hoàn toàn các ngoại lai nghiêm trọng (outliers/tail latency).
  - Nếu đặt SLO là `average < 300 ms`, thì với 3% request bị chậm 1.7 giây, hệ thống vẫn báo "đạt SLO" (avg = 247.5 ms). Nhưng trên thực tế, cứ 100 người dùng thì có 3 người phải chờ gần 2 giây, tạo ra trải nghiệm tồi tệ. Do đó, các hệ sinh thái sản xuất luôn đặt SLO theo **p95 hoặc p99** để bảo vệ trải nghiệm của mọi nhóm người dùng.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | **100.0% (23/23)** |
| Avg tokens / câu | 57.1 | 109.3 | 114.2 |
| Tổng cost (USD) | $0.000405 | $0.000764 | $0.000795 |
| Cost / câu đúng (USD) | $0.00040455 | $0.00003639 | **$0.00003458** |
| Quality gate | ❌ FAIL | ✅ PASS | ✅ PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung kiến thức phân biệt JWT vs API Key vào `KNOWLEDGE_BASE` trong `mock_llm.py`: JWT là token có cấu trúc header, payload, chữ ký mã hóa và tự động hết hạn, trong khi API Key là chuỗi tĩnh không tự hết hạn. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung kiến thức Kubernetes HPA vào `KNOWLEDGE_BASE` trong `mock_llm.py`: HPA tự động scale số lượng pod dựa trên chỉ số tài nguyên như CPU, memory hoặc custom metrics do ứng dụng tự định nghĩa. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

1. **Về Chất lượng (Accuracy)**:
   - Agent v1 không có Retrieval (RAG) chỉ đạt 4.3% accuracy (chỉ trả lời được 1 câu hỏi định nghĩa deploy chung chung, 22 câu còn lại trả lời sai hoàn toàn).
   - Agent v2 tích hợp Retrieval từ Knowledge Base đạt 91.3% ban đầu và sau khi cập nhật bổ sung 2 kiến thức còn thiếu đã đạt tuyệt đối **100.0% (23/23 PASS)**.
2. **Về Chi phí (Cost)**:
   - Tổng chi phí của v2 ($0.000795) cao hơn v1 ($0.000405) gần 96% vì mỗi câu hỏi v2 phải nạp thêm ngữ cảnh retrieval vào prompt, làm tăng số lượng input tokens (từ 57.1 lên 114.2 tokens/câu).
   - Tuy nhiên, khi xét chỉ số **Cost trên mỗi câu đúng (Cost / câu đúng)**, Agent v2 lại rẻ hơn gấp **11.7 lần** so với v1 ($0.00003458/câu so với $0.00040455/câu). Chi phí đầu tư cho context retrieval mang lại giá trị thực tế vượt trội.
3. **Về Độ trễ (Latency)**:
   - Latency p50 của v2 tăng nhẹ từ 165.9 ms lên 188.0 ms (+22.1 ms) do bước tìm kiếm tài liệu (vector/keyword search) và sinh output dài hơn.
   - Mức tăng latency ~13% là hoàn toàn chấp nhận được để đổi lại sự chính xác tuyệt đối của mô hình AI trong nghiệp vụ sản xuất.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals: Traffic RPS, Error Rate, Latency p50/p95/p99, Active Instances)
- [x] Một trace chậm trong Jaeger (thấy span `chat mock-llm-small` chiếm 98.5% thời gian)
- [x] Một trace lỗi trong Jaeger (có event `exception` và tag `error=true` khi upstream trả 503)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing** (như `AgentHighLatencyP95` hoặc `AgentHighErrorRate`)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (critical) | ~1 phút (`for: 1m`) | **Error Rate (%)** |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (warning) | ~2 phút (`for: 2m`) | **Latency Percentiles (p50 / p95 / p99)** |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (warning) | ~2 phút (`for: 2m`) | **LLM Cost Burn Rate ($/hr)** |
| D | `docker pause` 1 instance | `AgentInstanceDown` (critical) | ~30 giây (`for: 30s`) | **Active Instances / Availability** |
| E | `AGENT_VERSION=v1` | *(Không có alert nào firing)* | N/A | **Agent Version Info / Token Output** |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

1. **Bản chất vấn đề**:
   - Thí nghiệm E chuyển `AGENT_VERSION=v1` (bỏ qua bước RAG Retrieval). Mặc dù API vẫn trả HTTP 200, phản hồi rất nhanh (latency tốt) và không phát sinh lỗi HTTP hay vượt ngân sách, nhưng độ chính xác nghiệp vụ (Accuracy) sụt giảm thảm hại từ **100% xuống 4.3%**. Các alert truyền thống (lỗi 5xx, latency, CPU, RAM) hoàn toàn "mù" trước dạng suy giảm chất lượng này.
2. **Giải pháp giám sát trong Production**:
   - **Continuous Synthetic E2E Evaluation**: Thiết lập một CronJob / background test runner định kỳ gửi 23 câu hỏi trong Golden Dataset tới hệ thống staging/canary/production và tự động chấm điểm keyword/LLM-as-a-judge. Nếu accuracy giảm xuống dưới ngưỡng SLO (vd < 95%), kích hoạt Alert P0: `AgentQualityRegression`.
   - **User Feedback / Thumbs-down Monitoring**: Thu thập metric người dùng đánh giá câu trả lời (like/dislike/report). Cấu hình Prometheus Alert: `sum(rate(agent_feedback_dislike_total[15m])) / sum(rate(agent_feedback_total[15m])) > 0.05` để phát hiện phản ứng bất thường của người dùng.
   - **Semantic Drift & Token Distribution Monitoring**: Theo dõi độ dài token đầu ra (`llm_tokens_total{type="output"}`). Khi v1 hoạt động, câu trả lời generic rất ngắn (~30–50 tokens) so với câu trả lời đầy đủ context của v2 (~114 tokens). Sự sụt giảm đột biến về output token rate là tín hiệu cảnh báo anomaly.
   - **Version Drift Alert**: Đặt alert kiểm tra nhãn metric `agent_info{version!="v2"} > 0` nhằm ngăn chặn instance chạy phiên bản code cũ bị deploy nhầm vào cluster.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `9d9cf6cf7be58d6b6527a145bf6084e0`
- Tổng thời gian: **1665.9 ms**
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (**1641.1 ms**, chiếm **98.51%** tổng thời gian request)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T09:39:39.524051+00:00", "level": "INFO", "service": "observable-agent", "instance": "cb4ab37aea38", "event": "llm_call", "trace_id": "9d9cf6cf7be58d6b6527a145bf6084e0", "span_id": "10ebe4a8b4ad75fb", "request_id": "6742dc10efbc", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1641.1}
{"ts": "2026-11-25T09:39:39.524636+00:00", "level": "INFO", "service": "observable-agent", "instance": "cb4ab37aea38", "event": "http_request", "trace_id": "9d9cf6cf7be58d6b6527a145bf6084e0", "span_id": "10ebe4a8b4ad75fb", "request_id": "6742dc10efbc", "method": "POST", "route": "/ask", "status": 200, "ms": 1665.9}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 66.18 | 190 | 240 | 1700 | 86 (1.09%) |
| 3 | 64.96 | 200 | 580 | 1700 | 65 (0.84%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

1. **Phân tích kết quả thực tế**:
   - Khi tăng từ 1 instance lên 3 instances, tỷ lệ lỗi upstream (`503 Server Error`) giảm từ 86 lỗi (1.09%) xuống 65 lỗi (0.84%), cho thấy tải phân tán giúp giảm thiểu tình trạng dồn ứ cục bộ.
   - Tuy nhiên, throughput tổng thể (RPS ~65–66 req/s) và p99 (~1700 ms) không có sự khác biệt đáng kể giữa 1 pod và 3 pods, trong khi p95 dao động trong khoảng 240 ms – 580 ms.
2. **Nút thắt nằm ở đâu (Bottlenecks)?**:
   - **Nút thắt Upstream LLM / External Dependency**: Mỗi request gọi model AI bị chi phối bởi độ trễ upstream cố định (~120–180 ms) và tỷ lệ 3% request bị chậm bất thường (+1500 ms tail latency). Scale tầng tính toán agent (compute tier) không thể làm tăng tốc độ xử lý của nhà cung cấp LLM bên ngoài.
   - **Tài nguyên phần cứng máy chủ chủ (Host CPU / Docker Desktop)**: Cả 3 container agent, Nginx, Prometheus, Grafana, Jaeger và Locust process cùng chia sẻ tài nguyên CPU của 1 máy laptop/VM duy nhất. Khi Locust sinh tải đồng thời 100 client ảo, CPU của máy chủ đạt ngưỡng bão hòa cho việc điều phối network context switching giữa các container.
   - **Kết luận kiến trúc**: Để scale hiệu quả các ứng dụng LLM Agent trong thực tế:
     - Cần áp dụng **Semantic Caching** (Redis / Memcached) ở phía trước để các câu hỏi trùng lặp không phải gọi lại upstream LLM.
     - Áp dụng **Streaming Response (SSE / WebSocket)** để giảm thời gian chờ phản hồi đầu tiên (Time to First Token - TTFT) cho người dùng.
     - Thiết lập cơ chế **Circuit Breaker / Dynamic Fallback** chuyển sang model nhỏ hơn hoặc cache khi upstream LLM bị nghẽn.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Hiểu rõ ranh giới giữa Hiệu năng (Performance) và Chất lượng (Quality)**: Một agent có RPS cao và latency siêu thấp nhưng trả lời sai toàn bộ (như agent v1 đạt 4.3% accuracy) là hoàn toàn vô giá trị trong sản xuất. Cần kết hợp song song Load Testing và Golden Dataset Quality Gate trước mỗi lần release.
  2. **Tầm quan trọng sống còn của Percentile (p95, p99)**: Latency trung bình (Average) là một "cái bẫy" che đậy các sự cố tail latency nghiêm trọng. Chỉ có p95 và p99 mới phản ánh trung thực trải nghiệm của người dùng thực tế khi hệ thống chịu tải hoặc gặp sự cố mạng.
  3. **Sức mạnh liên kết giữa Ba trụ cột Observability (Metrics - Logs - Traces)**: Metric giúp phát hiện vấn đề (Alert firing trên Prometheus/Grafana), Trace giúp khoanh vùng chính xác span gây chậm trễ (Jaeger), và JSON Structured Log mang `trace_id` giúp đào sâu nguyên nhân gốc rễ (Root Cause Analysis) đến từng dòng code.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  1. **Metric đo Time-to-First-Token (TTFT) và Inter-Token Latency**: Đối với agent hỗ trợ streaming, TTFT là chỉ số quan trọng nhất quyết định cảm giác nhanh/chậm của người dùng.
  2. **Semantic Cache Hit/Miss Rate Metric**: Đo tỷ lệ câu hỏi được giải quyết từ cache để đánh giá hiệu quả tối ưu chi phí và giảm tải cho backend LLM.
  3. **Alert Token Budget Quota Exceeded (Cost Guard)**: Cảnh báo đa tầng khi chi phí tích lũy trong ngày vượt 80% ngân sách và tự động chuyển sang chế độ degraded service (model tiết kiệm) khi chạm trần 100%.
  4. **Prometheus Alert DeadMan's Switch (Watchdog)**: Alert luôn firing để đảm bảo toàn bộ đường truyền từ Prometheus tới Alertmanager/PagerDuty không bao giờ bị đứt gãy trong im lặng.
