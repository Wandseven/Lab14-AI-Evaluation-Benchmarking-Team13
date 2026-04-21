# Reflection — Mẫu (đổi tên file thành `reflection_<HoTen>.md` khi nộp)

## Đóng góp kỹ thuật
- Tham gia thiết kế golden set (≥50 case) và `expected_retrieval_ids`.
- Hiểu pipeline: Agent V1/V2 → retrieval metrics (Hit/MRR) → hai judge consensus → regression gate.

## Khái niệm đã vận dụng
- **MRR:** phạt khi tài liệu đúng không ở đầu danh sách.
- **Agreement rate:** đo mức đồng thuận giữa hai judge; khi lệch >1 điểm dùng luật hòa giải bảo thủ.
- **Trade-off chi phí / chất lượng:** theo dõi `cost_per_eval_usd` và token trong `summary.json`.

## Vấn đề đã gặp và cách xử lý
- **Encoding console Windows:** tránh in emoji/Unicode không hỗ trợ; ưu tiên log ASCII hoặc ghi file UTF-8.
- **Retrieval nhiễu V1:** so sánh V1 vs V2 để chứng minh cải thiện MRR sau khi rerank/boost.

## Bài học
Đo được retrieval trước khi chấm generation giúp phân tích gốc lỗi (chunking vs retrieval vs prompt).
