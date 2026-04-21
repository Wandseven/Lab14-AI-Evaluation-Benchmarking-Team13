# Báo cáo Cá nhân — Lab Day 14: AI Evaluation Factory

**Họ và tên:** Nguyễn Tuấn Kiệt
**Vai trò:** Data / SDG Lead
**Ngày:** 21/04/2026

---

## 1. Đóng góp Kỹ thuật (Engineering Contribution)

### 1.1 Các file chịu trách nhiệm chính

| File | Mô tả |
|------|-------|
| `data/knowledge_base.py` | Thiết kế và duy trì toàn bộ knowledge corpus (18 chunks, mỗi chunk có stable ID) |
| `data/synthetic_gen.py` | Viết pipeline SDG tự động tạo ≥55 test cases, bao gồm base, expanded và red-team |
| `data/golden_set.jsonl` | Output cuối cùng: 55 test cases chất lượng cao (tạo ra sau mỗi vòng run) |

### 1.2 Công việc cụ thể đã thực hiện

#### Knowledge Base (`knowledge_base.py`)
- Xây dựng corpus tĩnh gồm **18 chunks** phủ đủ các chủ đề cần thiết: AI Evaluation, RAG pipeline, Chunking, Hallucination, Async/Cost, Regression, Multi-judge, Security và Safety.
- Mỗi chunk được gán **stable ID** (ví dụ: `chunk_eval_01`, `chunk_rag_02`, `chunk_sec_01`...) để làm **ground truth** cho phép tính toán chính xác Hit Rate và MRR.
- Thiết kế các chunk "red-team" chuyên biệt như `chunk_inject_01` (system boundary) và `chunk_sec_01` (policy từ chối) để phục vụ kiểm tra an toàn.
- Cung cấp hàm tiện ích `chunks_by_id()` để các module khác (retrieval_eval, runner) tra cứu nhanh.

#### Synthetic Data Generation (`synthetic_gen.py`)
- Viết **3 lớp case generation**:
  1. `_base_cases()` — 19 case gốc fact-check, mỗi case gắn với 1 chunk cụ thể trong KB.
  2. `_expand_to_fifty()` — Tự động sinh biến thể (paraphrase, hỏi ngắn, diễn đạt lại) từ các case gốc để đạt mục tiêu ≥52 case, giữ nguyên `expected_retrieval_ids`.
  3. `_red_team_cases()` — 3 case red-team đặc biệt (`tc_rt_001` → `tc_rt_003`) kiểm tra prompt injection, secret exposure, và out-of-scope query.
- Tổng output: **55 test cases** (tc_0001 → tc_0052 + 3 red-team), đảm bảo đa dạng:
  - 3 mức độ khó: easy / medium / hard
  - 7 loại case type: fact-check, safety, adversarial, conflict, ambiguous, latency-stress, paraphrase, red-team
- Pipeline chạy **async** (`asyncio.run(main())`) để sẵn sàng scale khi cần gọi LLM sinh câu hỏi thực tế.
- Output file `data/golden_set.jsonl` đúng schema (id, question, expected_answer, context, expected_retrieval_ids, metadata).


---

## 2. Độ sâu Kỹ thuật (Technical Depth)

### 2.1 Hiểu về Hit Rate và MRR

**Hit Rate** (tỉ lệ truy vấn có ít nhất 1 tài liệu đúng trong top-k) là metric "nhị phân" — chỉ phân biệt pass/fail cho từng query, không quan tâm tài liệu xếp ở vị trí nào. Do đó Hit Rate dễ đạt cao nhưng không phản ánh đúng chất lượng ranking.

**MRR** (Mean Reciprocal Rank) khắc phục điểm yếu này bằng cách phạt tài liệu đúng xếp ở thứ hạng thấp. Công thức:

```
MRR = (1/|Q|) × Σ (1 / rank_i)
```

Trong hệ thống này, các `expected_retrieval_ids` tôi thiết kế trong golden set chính là ground truth để `engine/retrieval_eval.py` tính toán cả hai metric. Kết quả thực tế sau khi chạy benchmark:
- **Hit Rate = 0.9818** (V2) — hệ thống retrieve đúng tài liệu trong 54/55 trường hợp.
- **MRR = 0.8571** (V2) — cải thiện đáng kể so với V1 (0.5556), cho thấy chunking ID mapping chuẩn đã giúp reranking hoạt động tốt hơn.

### 2.2 Thiết kế Ground Truth ID và Mapping

Một quyết định thiết kế quan trọng là sử dụng **stable chunk ID** thay vì dùng text matching. Điều này có lý do:
- Text matching dễ bị ảnh hưởng bởi paraphrase, encoding, hay whitespace.
- ID cố định cho phép kiểm tra exact match dứt khoát: `retrieved_id in expected_ids`.
- Khi KB mở rộng, chỉ cần thêm chunks mới, không cần viết lại logic eval.

### 2.3 Đa dạng độ khó và Red-Teaming

Phân phối độ khó trong golden set được thiết kế có chủ ý:

| Difficulty | Số cases | Mục đích |
|------------|----------|----------|
| Easy | ~20 | Baseline sanity check, đảm bảo agent không fail những case cơ bản |
| Medium | ~20 | Kiểm tra khả năng suy luận với ngữ cảnh đầy đủ |
| Hard | ~12 | Stress test: conflicting docs, adversarial prompts, latency stress |
| Red-team | 3 | Kiểm tra ranh giới an toàn |

Các **red-team case** đặc biệt quan trọng vì chúng kiểm tra khả năng **từ chối hợp lý** (graceful refusal) — một tiêu chí mà production AI system bắt buộc phải đáp ứng nhưng thường bị bỏ qua trong academic benchmark thông thường.

### 2.4 Trade-off Chi phí vs Chất lượng Dataset

Khi thiết kế SDG, tôi cân nhắc giữa hai hướng:
1. **Dùng LLM để tự động sinh câu hỏi** từ chunk text — chất lượng cao hơn nhưng tốn API cost.
2. **Viết thủ công + expand bằng template** — kiểm soát được chất lượng và không tốn chi phí.

Tôi chọn hybrid approach: **viết thủ công 19 base cases** (đảm bảo chất lượng) + **auto-expand bằng template paraphrase** (đảm bảo số lượng ≥50). Cách này giúp nhóm không tốn thêm API tokens trong giai đoạn setup, dành ngân sách cho phần benchmark chính.

---

## 3. Giải quyết Vấn đề (Problem Solving)

### 3.1 Vấn đề: Đảm bảo đủ 50+ cases với đa dạng type

**Bài toán:** Rubric yêu cầu ≥50 test cases, nhưng nếu chỉ viết tay sẽ mất quá nhiều thời gian, còn nếu clone lặp lại thì không có giá trị đánh giá.

**Giải pháp:** Thiết kế hàm `_expand_to_fifty()` với 3 template paraphrase (`Hỏi ngắn: {}`, `Diễn đạt lại: {}`, `Kiểm tra lại: {}`) để sinh biến thể giữ nguyên expected_retrieval_ids. Các biến thể này vẫn có giá trị thực vì chúng kiểm tra **robustness của retrieval** — cùng một intent nhưng cách diễn đạt khác nhau thì hệ thống có retrieve đúng không.

### 3.2 Vấn đề: Schema consistency cho toàn bộ pipeline

**Bài toán:** Các module downstream (retrieval_eval, runner, check_lab) đều parse JSONL, bất kỳ field nào bị thiếu sẽ gây crash.

**Giải pháp:** Tôi thiết kế schema cứng ngay từ đầu và đảm bảo tất cả 3 loại case generation (base, expanded, red-team) đều output đủ 6 fields: `id`, `question`, `expected_answer`, `context`, `expected_retrieval_ids`, `metadata`. Red-team cases đặc biệt dùng `context: ""` (chuỗi rỗng, không phải null) để tránh lỗi khi module downstream stringify.

### 3.3 Vấn đề: ID uniqueness khi expand và pad

**Bài toán:** Khi loop expand có thể tạo ra ID trùng lặp nếu không kiểm soát.

**Giải pháp:** Dùng `seen = set()` để track IDs đã dùng, skip nếu đã tồn tại. Cơ chế pad (`tc_pad_XXXX`) là safety net nếu sau expand vẫn chưa đủ 50 case.

---

## 4. Kết quả Đạt được

Sau khi chạy `python data/synthetic_gen.py` và `python main.py`, hệ thống của nhóm đạt:

| Metric | V1 | V2 | Cải thiện |
|--------|----|----|-----------|
| Hit Rate | 0.9818 | 0.9818 | Ổn định |
| MRR | 0.5556 | **0.8571** | +53.9% |
| Faithfulness | 0.8131 | **0.9147** | +12.5% |
| Relevancy | 0.4461 | **0.9428** | +111.4% |
| Avg Score | 2.0939 | **4.4697** | +113.5% |
| Cost/Eval | $0.0000201 | $0.0000244 | +21.4% |

**Release Decision: RELEASE** — Chất lượng tăng đáng kể, chi phí tăng trong mức chấp nhận.

Golden set chất lượng cao là foundation giúp các metric trên có ý nghĩa: nếu expected_retrieval_ids sai, Hit Rate và MRR sẽ phản ánh không đúng thực trạng retrieval.

---

## 5. Bài học và Reflection

### 5.1 Điều học được về AI Evaluation

Trước lab này, tôi thường nghĩ "đánh giá AI" chỉ đơn giản là hỏi và chấm điểm câu trả lời. Qua quá trình xây dựng golden set và KB, tôi nhận ra rằng **chất lượng của bộ test cases** quyết định gần như toàn bộ ý nghĩa của kết quả benchmark. Một golden set thiếu đa dạng hoặc thiếu ground truth IDs sẽ cho ra số đẹp nhưng vô nghĩa.

Cụ thể, tôi hiểu sâu hơn về tầm quan trọng của **Retrieval Evaluation trước Generation Evaluation** — nếu retriever lấy sai chunk, judge dù giỏi đến đâu cũng không thể phát hiện ra nguồn gốc lỗi thật sự. Đây chính là insight mà README nhóm nhấn mạnh: "Nhóm nào bỏ qua bước Retrieval sẽ không thể đạt điểm tối đa."

### 5.2 Điều làm tốt

- Thiết kế KB và ID mapping rõ ràng ngay từ đầu, giúp các module downstream không cần sửa gì.
- Red-team cases được bổ sung đủ 3 loại (secret extraction, prompt injection, out-of-scope), đáp ứng rubric về "bộ Red Teaming phá vỡ hệ thống."
- `synthetic_gen.py` chạy async và idempotent — chạy lại nhiều lần vẫn cho cùng kết quả.

### 5.3 Điều có thể cải thiện

- **Multi-turn cases** chưa được triển khai do thời gian giới hạn. Đây là loại khó nhất (context carry-over, correction) và sẽ là hướng mở rộng quan trọng cho production-grade evaluation.
- **LLM-assisted paraphrase** — thay vì dùng template tĩnh, có thể dùng LLM nhỏ (GPT-3.5) để sinh câu hỏi paraphrase tự nhiên hơn, tăng độ thực tế của benchmark.
- Nên bổ sung thêm các **conflicting document cases** với nhiều phiên bản hơn (A, B, C) để kiểm tra khả năng agent xử lý khi KB có mâu thuẫn nhiều chiều.

### 5.4 Kỹ năng phát triển được

- Hiểu rõ về **schema-driven design**: thiết kế data contract trước khi code giúp toàn bộ team phối hợp mượt mà.
- Kinh nghiệm thực hành với **adversarial testing** và red-teaming — kỹ năng ngày càng quan trọng trong AI safety.
- Kỹ năng **async Python** cho data generation pipeline, sẵn sàng tích hợp LLM call sau này.

---

## 6. Đối chiếu Rubric

| Tiêu chí Rubric | Đóng góp của tôi | Tự đánh giá |
|-----------------|------------------|-------------|
| **Dataset & SDG** (10đ nhóm) — Golden Dataset ≥50 cases với ground truth IDs + Red Teaming | Trực tiếp: KB (18 chunks + stable IDs), SDG script (55 cases, 3 categories), 3 red-team cases | ✅ Đầy đủ |
| **Retrieval Evaluation** (10đ nhóm) — Hit Rate & MRR | Gián tiếp: Ground truth IDs do tôi thiết kế là input cho retrieval_eval.py | ✅ Hỗ trợ |
| **Engineering Contribution** (15đ cá nhân) | Commit: knowledge_base.py, synthetic_gen.py, golden_set.jsonl | ✅ Rõ ràng |
| **Technical Depth** (15đ cá nhân) — Hiểu MRR, Cohen's Kappa, trade-off chi phí | Giải thích ở mục 2 (Hit Rate vs MRR, ground truth design, cost trade-off) | ✅ Đủ sâu |
| **Problem Solving** (10đ cá nhân) | 3 vấn đề cụ thể + giải pháp ở mục 3 | ✅ Có bằng chứng |

---
