# Reflection — Nguyễn Việt Trung (Analysis & Submission Owner)

## Đóng góp kỹ thuật

- **Viết báo cáo nhóm (`analysis/failure_analysis.md`):** Tổng hợp toàn bộ kết quả benchmark từ `reports/summary.json` và `reports/benchmark_results.json`; xây dựng bảng phân nhóm lỗi (Failure Clustering) và phân tích 5 Whys cho 3 case tệ nhất (`tc_0020`, `tc_0027`, `tc_rt_001`); đề xuất Action Plan cải tiến pipeline.
- **Chuẩn hóa hồ sơ nộp:** Đảm bảo đủ 4 thành phần theo submission checklist — source code, `reports/`, `analysis/failure_analysis.md`, và các file `analysis/reflections/reflection_*.md`; đối chiếu nội bộ với `GRADING_RUBRIC.md` để không bỏ sót tiêu chí.
- **Hiểu toàn bộ pipeline:** Agent V1/V2 → Retrieval metrics (Hit Rate/MRR) → RAGAS (Faithfulness/Relevancy) → Multi-Judge consensus → Regression Release Gate → báo cáo cost/token.

## Khái niệm đã vận dụng

- **MRR (Mean Reciprocal Rank):** Chỉ số phạt nặng khi tài liệu đúng không xuất hiện ở vị trí đầu danh sách. V2 cải thiện MRR từ 0.5556 lên 0.8571 (+0.3015), chứng tỏ rerank/boost có hiệu quả rõ rệt.
- **Cohen's Kappa:** Đo độ đồng thuận giữa hai Judge có tính đến yếu tố ngẫu nhiên. Kappa của V2 = 0.2331 (giảm so với V1 = 0.6982), cho thấy hai judge có xu hướng cho điểm khác nhau hơn khi chất lượng câu trả lời tăng — cần theo dõi và calibrate lại rubric.
- **Position Bias:** Rủi ro judge chấm điểm lệch theo vị trí trình bày câu trả lời. V2 giảm `position_bias_risk_rate` từ 0.6364 xuống 0.4727, tức là hệ thống ít bị ảnh hưởng hơn nhưng vẫn cần giám sát.
- **Trade-off chi phí / chất lượng:** V2 tốn 2.44e-05 USD/eval (tăng nhẹ so với V1 = 2.009e-05), nhưng đổi lại avg_score nhảy vọt từ 2.11 lên 4.41. Đây là trade-off chấp nhận được; báo cáo trong `summary.json` minh bạch hóa chi phí cho mỗi lần chạy eval.
- **Regression Release Gate:** Logic tự động so sánh delta giữa V1 và V2 theo các ngưỡng chất lượng và chi phí. Kết quả: `release_decision = RELEASE` — delta avg_score = +2.306, delta MRR = +0.3015, cost tăng không đáng kể.

## Vấn đề đã gặp và cách xử lý

- **Đọc hiểu kết quả từ nhiều nguồn khác nhau:** `summary.json` chứa cả regression metrics V1/V2 lẫn kết quả tổng hợp V2, dễ nhầm lẫn khi viết báo cáo. Cách xử lý: đọc kỹ schema JSON, phân biệt rõ `v1_metrics`, `v2_metrics`, và `delta` trước khi điền vào `failure_analysis.md`.
- **Phân nhóm lỗi thiếu nhất quán:** Ban đầu khó phân biệt lỗi thuộc về prompt generation hay retrieval. Cách xử lý: so sánh hit_rate/MRR với final_score từng case — khi retrieval tốt (hit=1) nhưng score thấp thì root cause nằm ở prompt/generation, không phải retrieval.
- **Judge disagreement rải rác, không cô lập được thành một nhóm rõ ràng:** Agreement rate V2 = 0.8873, tức vẫn có ~11% case hai judge bất đồng. Cách xử lý: ghi nhận trong failure analysis và đưa vào action plan yêu cầu calibrate lại rubric định kỳ, thay vì cố ép phân loại thành case lỗi cứng.

## Bài học

Vai trò tổng hợp báo cáo yêu cầu hiểu cả pipeline lẫn số liệu đầu ra — không thể viết được failure analysis chính xác nếu chỉ đọc kết quả mà không nắm ý nghĩa từng metric. Quan trọng hơn, khi cả hai chỉ số retrieval và generation cùng tốt nhưng vẫn có case fail, thì root cause thường nằm ở format/intent-matching ở tầng prompt — đây là điểm mà pipeline hiện tại còn thiếu kiểm soát.
