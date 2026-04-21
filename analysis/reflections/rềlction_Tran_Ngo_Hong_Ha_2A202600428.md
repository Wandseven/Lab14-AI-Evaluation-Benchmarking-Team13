# Reflection Cá Nhân — Judge / Consensus

---

# Đóng góp kỹ thuật
- Thiết kế và triển khai hệ thống Multi-Judge Evaluation sử dụng hai mô hình LLM độc lập nhằm tăng độ tin cậy của kết quả đánh giá.
- Xây dựng module `engine/llm_judge.py` để thực hiện:
  + Gọi song song 2 mô hình LLM (GPT + Gemini)
  + Thu thập kết quả đánh giá độc lập
  + Tính toán độ lệch điểm
- Triển khai cơ chế Conflict Resolution:
  + Khi chênh lệch điểm giữa hai judge vượt ngưỡng (> 1.0), kích hoạt bước adjudication
  + Thực hiện đánh giá lại bằng model chính để đưa ra kết quả consensus
- Xây dựng module `engine/consensus.py` để:
  + Tính toán điểm trung bình có trọng số
  + Xử lý fallback khi một model lỗi hoặc timeout
  + Đảm bảo hệ thống không crash khi API thất bại
- Triển khai module `engine/rater_metrics.py` để theo dõi:
  + Agreement Rate giữa các judge
  + Cohen’s Kappa
  + Position Bias
- Áp dụng xử lý async parallel execution bằng `asyncio.gather()` nhằm:
  + Giảm latency hệ thống
  + Tối ưu hiệu suất multi-judge
- Thiết kế cơ chế fallback:
  + Khi một model lỗi → dùng model còn lại
  + Khi cả hai model lỗi → trả về giá trị mặc định an toàn

**Evidence (Git commits):**
- 04f99f43a1de99624b124ecb4efa5e7b403289b1

---

# Khái niệm đã vận dụng

### 1. Multi-Judge System

Hệ thống sử dụng hai mô hình độc lập để giảm bias và tăng độ tin cậy:
- Judge A: GPT model
- Judge B: Gemini model
Sau đó hệ thống tính:
- Agreement rate
- Score gap
- Final consensus score

---

### 2. Cohen’s Kappa
Cohen’s Kappa được sử dụng để đo mức độ đồng thuận giữa hai judge:
- Kappa = 1 -> đồng thuận hoàn toàn
- Kappa = 0 -> đồng thuận ngẫu nhiên
- Kappa < 0 -> bất đồng lớn
Việc theo dõi Cohen’s Kappa giúp đánh giá độ tin cậy của hệ thống multi-judge.

---

### 3. MRR (Mean Reciprocal Rank)
MRR được sử dụng để đánh giá chất lượng ranking của hệ thống retrieval:
- MRR cao -> kết quả retrieval tốt
- MRR thấp -> cần cải thiện retrieval pipeline
MRR hỗ trợ phân tích hiệu quả khi hệ thống đánh giá nhiều candidate responses.

---

### 5. Trade-off Chi phí vs Chất lượng

Hệ thống sử dụng:

| Model | Vai trò | Chi phí | Chất lượng |
|-------|---------|---------|------------|
| GPT-4o | Judge chính | Cao | Cao |
| Gemini Flash | Judge phụ | Thấp | Trung bình |

Trade-off:

- Multi-judge tăng chi phí
- Nhưng tăng reliability và giảm bias
- Sử dụng adjudication chỉ khi cần để tối ưu chi phí

---

# Problem Solving (10 điểm)

### 1. Vấn đề: API latency khi gọi multi-model

Giải pháp:

- Sử dụng `asyncio.gather()`
- Gọi song song hai model
- Giảm latency tổng thể

---

### 2. Vấn đề: API failure / timeout

Giải pháp:

- Thiết kế fallback logic
- Khi 1 judge lỗi thì dùng judge còn lại
- Khi cả 2 lỗi thì trả về default score

---

### 3. Vấn đề: Score conflict giữa các model

Giải pháp:

- Thiết kế adjudication step
- Gọi model chính để resolve conflict
- Tính final consensus score

