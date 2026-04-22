# Reflection — Nguyễn Việt Trung (Analysis & Submission Owner)

## 1. Engineering Contribution

**Vai trò chính:** Viết báo cáo nhóm, tổng hợp kết quả benchmark cuối, chuẩn hóa toàn bộ hồ sơ nộp bài.

**Đóng góp cụ thể:**

- **`analysis/failure_analysis.md`:** Đọc trực tiếp từ `reports/summary.json` và `reports/benchmark_results.json` để trích xuất số liệu thực (55 cases, pass/fail 51/4, avg_score V2 = 4.4121, MRR V2 = 0.8571, agreement_rate = 0.8873, release_decision = RELEASE). Xây dựng bảng Failure Clustering, phân tích 5 Whys cho 3 case tệ nhất và đề xuất Action Plan cụ thể.
- **Chuẩn hóa hồ sơ nộp:** Đối chiếu từng mục trong `GRADING_RUBRIC.md` với các file thực tế trong repo để đảm bảo submission checklist đầy đủ — source code, `reports/summary.json`, `reports/benchmark_results.json`, `analysis/failure_analysis.md`, `analysis/reflections/reflection_*.md`.
- **Nắm toàn bộ luồng pipeline:** Agent V1 → Agent V2 → Retrieval Eval (Hit Rate / MRR) → RAGAS (Faithfulness / Relevancy) → Multi-Judge Consensus → Regression Release Gate → Cost/Token Report. Sự hiểu biết này là điều kiện cần để viết failure analysis chính xác, không nhầm tầng lỗi.

**Chứng minh qua Git commits:** Các commit liên quan trực tiếp tới `analysis/failure_analysis.md`, `analysis/reflections/`, và README bao gồm commit `762e037` (feat: add group and individual report)

---

## 2. Technical Depth

**MRR (Mean Reciprocal Rank):**
MRR đo chất lượng retrieval bằng cách tính nghịch đảo thứ hạng của tài liệu đúng đầu tiên, rồi lấy trung bình trên toàn bộ query. Nếu tài liệu đúng đứng ở rank 1 thì đóng góp 1.0; rank 2 đóng góp 0.5; rank 3 đóng góp 0.33 — tức là phạt nặng khi retrieval trả về đúng nhưng không ưu tiên. Trong benchmark này, V1 có MRR = 0.5556 (tài liệu đúng thường không ở đầu), V2 cải thiện lên 0.8571 (+0.3015) nhờ rerank/boost, cho thấy retrieval stage đã đặt đúng tài liệu lên vị trí ưu tiên hơn.

**Cohen's Kappa:**
Cohen's Kappa đo mức đồng thuận giữa hai judge sau khi đã loại trừ xác suất đồng ý ngẫu nhiên, công thức: κ = (P_o − P_e) / (1 − P_e). Khác với agreement rate đơn thuần chỉ đếm tỷ lệ khớp, Kappa cho biết mức độ tin cậy thực sự của hệ thống đánh giá. V1 có Kappa = 0.6982 (đồng thuận tốt), nhưng V2 giảm xuống 0.2331 — hai judge bất đồng nhiều hơn khi câu trả lời chất lượng cao hơn, vì rubric chưa được calibrate cho dải điểm 4–5.

**Position Bias:**
Position Bias là hiện tượng judge cho điểm cao hơn chỉ vì câu trả lời đứng ở một vị trí nhất định trong prompt, chứ không phải vì nội dung tốt hơn. Hệ thống đo bằng `position_bias_risk_rate` (tỷ lệ case có delta điểm đáng kể khi đổi thứ tự trình bày). V2 giảm từ 0.6364 xuống 0.4727 — cải thiện rõ, nhưng gần một nửa số case vẫn có nguy cơ bị ảnh hưởng, cần tiếp tục theo dõi.

**Trade-off Chi phí / Chất lượng:**
V2 tốn 2.44e-05 USD/eval so với V1 = 2.009e-05 USD/eval, tăng ~21%. Tuy nhiên avg_score nhảy từ 2.11 lên 4.41 (+109%), MRR tăng +0.3015, Faithfulness tăng từ 0.8131 lên 0.9147, Relevancy tăng từ 0.4461 lên 0.9428. Đây là trade-off hoàn toàn chấp nhận được — chi phí tăng rất nhỏ, chất lượng tăng gần gấp đôi. Release Gate tự động kết luận `RELEASE` dựa trên ngưỡng này.

---

## 3. Problem Solving

**Vấn đề 1 — Nhầm tầng lỗi khi phân tích failure:**
Ban đầu có xu hướng quy tất cả các case fail về lỗi retrieval vì đây là tầng dễ đo nhất. Cách giải quyết: đối chiếu trực tiếp hit_rate và MRR từng case với final_score — khi hit_rate = 1.0 và MRR cao nhưng score vẫn thấp, thì retrieval không phải root cause. Ba case fail (`tc_0020`, `tc_0027`, `tc_rt_001`) đều thuộc nhóm này: retrieval tốt, lỗi nằm ở prompt generation (thiếu intent-based response mode) và safety policy (refusal template chưa đủ cứng).

**Vấn đề 2 — Đọc hiểu schema `summary.json` phức tạp:**
File `summary.json` lồng nhiều lớp — `metadata`, `v1_metrics`, `v2_metrics`, `delta`, `release_decision` — dễ nhầm khi trích số liệu. Cách giải quyết: đọc toàn bộ schema trước, lập danh sách các trường cần dùng cho báo cáo, sau đó trích xuất tuần tự thay vì đọc lướt.

**Vấn đề 3 — Judge disagreement không cô lập thành nhóm lỗi cứng:**
Agreement rate V2 = 0.8873, tức ~11% case hai judge bất đồng nhưng rải rác ở nhiều loại câu hỏi khác nhau, không tập trung thành cluster rõ ràng. Cách giải quyết: không ép phân loại thành một nhóm fail riêng biệt, thay vào đó ghi nhận như một vấn đề hệ thống cần calibrate định kỳ và đưa vào Action Plan — "Theo dõi định kỳ agreement/kappa để calibrate lại rubric giữa 2 model judge."
