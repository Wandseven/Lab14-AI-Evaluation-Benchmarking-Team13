# Reflection Cá Nhân - Vai trò Runner/Regression/Release Gate Engineer

## 1) Phạm vi công việc đã đảm nhận
Trong bài lab này, tôi đảm nhận vai trò **Người 4 - Runner/Regression/Release Gate Engineer** với các nhiệm vụ chính:
- Xây dựng async runner để chạy benchmark theo lô, theo dõi độ trễ và kết quả từng case.
- Hoàn thiện pipeline benchmark cho 2 phiên bản Agent (V1 và V2) và tổng hợp kết quả.
- Triển khai regression testing (V1 vs V2) và release gate tự động dựa trên ngưỡng chất lượng/chi phí.
- Chuẩn hóa định dạng output cho `reports/summary.json`, `reports/benchmark_results.json` và script `check_lab.py`.

## 2) Đóng góp kỹ thuật cụ thể (theo module)
### a) `engine/runner.py`
- Tổ chức luồng chạy song song bằng `asyncio.gather` theo batch.
- Thu thập kết quả theo từng test case: latency, tokens, cost, retrieval metrics, judge score, trạng thái pass/fail.
- Bổ sung xử lý trường hợp lỗi API để hạn chế vỡ toàn pipeline benchmark.

### b) `main.py`
- Chạy benchmark cho cả **Agent_V1_Base** và **Agent_V2_Optimized** trên cùng golden set.
- Tổng hợp các metrics quan trọng: avg_score, hit_rate, mrr, faithfulness, relevancy, agreement_rate, token/cost/latency.
- Thêm nhóm metrics reliability: Cohen's Kappa, position bias risk rate, position bias mean delta.
- Tính delta regression và ghi vào `metadata.regression`.
- Triển khai release decision (`RELEASE`/`ROLLBACK`/`HOLD`) dựa trên ngưỡng để quyết định có triển khai bản mới hay không.

### c) `check_lab.py`
- Đảm bảo script kiểm tra có thể chạy ổn định trên Windows console.
- Kiểm tra đủ file, đủ field bắt buộc trong report (metrics + metadata + retrieval + multi-judge + version).

## 3) Kết quả đạt được
- Pipeline chạy được theo đúng flow:
  1. `python data/synthetic_gen.py`
  2. `python main.py`
  3. `python check_lab.py`
- Tạo đầy đủ 2 file report bắt buộc:
  - `reports/summary.json`
  - `reports/benchmark_results.json`
- Regression mode hiển thị rõ V1, V2, delta và release gate.
- Kiểm tra cuối bằng `check_lab.py` đạt trạng thái sẵn sàng để chấm điểm.

## 4) Độ sâu kỹ thuật (Technical Depth)
- **MRR (Mean Reciprocal Rank):** hiểu và áp dụng để đánh giá chất lượng xếp hạng retrieval, không chỉ kiểm tra có tìm thấy tài liệu đúng.
- **Cohen's Kappa:** dùng để đo mức độ đồng thuận giữa 2 rater rời rạc (judge model A/B), bổ sung cho agreement rate.
- **Position Bias:** theo dõi rủi ro thiên vị thứ tự trình bày thông qua heuristic đo overlap theo hoán vị.
- **Trade-off chất lượng vs chi phí:** theo dõi cost/tokens/latency song song với avg_score, từ đó ra quyết định gate hợp lý.

## 5) Vấn đề gặp phải và cách xử lý
- Gặp lỗi API bên ngoài (timeout, 429, 503, model unsupported, parameter mismatch) làm benchmark bị gián đoạn.
- Cách xử lý:
  - Thêm fallback để không vỡ toàn bộ luồng chạy.
  - Bổ sung timeout/retry và giảm batch size để hạn chế request burst.
  - Điều chỉnh tham số gọi model (ví dụ `max_completion_tokens` cho model mới).
  - Chuẩn hóa logging cảnh báo để debug nhanh nguyên nhân lỗi.

## 6) Bài học kinh nghiệm
- Trong hệ thống eval thực tế, **đo lường retrieval và judge reliability** quan trọng không kém chất lượng generation.
- Regression gate cần thiết để tránh đưa bản mới chất lượng thấp lên production.
- Kiến trúc robust (fallback + retry + async control) giúp pipeline ổn định hơn khi phụ thuộc API bên thứ 3.

## 7) Định hướng cải tiến tiếp theo
- Bổ sung calibration set riêng cho judge A/B trước khi benchmark full.
- Cải thiện release gate theo ngưỡng động (adaptive thresholds) theo từng nhóm testcase.
- Tối ưu tiếp chi phí eval bằng cache kết quả judge cho các lần chạy lặp.
