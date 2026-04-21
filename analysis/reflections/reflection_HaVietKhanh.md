# Báo cáo Cá nhân: KhanhHaV

## 👤 2. Điểm Cá nhân (Tối đa 40 điểm)

| Hạng mục | Tiêu chí | Điểm tự đánh giá |
| :--- | :--- | :---: |
| **Engineering Contribution** | - Đóng góp cụ thể vào các module phức tạp (Async, Multi-Judge, Metrics).<br>- Chứng minh qua Git commits và giải trình kỹ thuật. | 15/15 |
| **Technical Depth** | - Giải thích được các khái niệm: MRR, Cohen's Kappa, Position Bias.<br>- Hiểu về trade-off giữa Chi phí và Chất lượng. | 15/15 |
| **Problem Solving** | - Cách giải quyết các vấn đề phát sinh trong quá trình code hệ thống phức tạp. | 10/10 |

---

### Chi tiết đánh giá:

#### 1. Engineering Contribution (15/15)
- **Đóng góp cụ thể**: Xây dựng module **Metrics Engine** thông qua class `ExpertEvaluator` với cơ chế tính toán bất đồng bộ (**Async**). Module này cho phép tự động tính toán các chỉ số quan trọng để đánh giá độ chính xác của hệ thống RAG.
- **Giải trình kỹ thuật**: 
  - Tích hợp và gọi các tính toán logic trong `RetrievalEvaluator` để đưa ra các điểm số `Hit Rate` và `MRR` (*Mean Reciprocal Rank*).
  - Tự code thuật toán lightweight (sử dụng Tokenizer và Bag-of-Words dạng sets) cho hai metrics: `faithfulness` (đánh giá câu trả lời có bám sát ngữ cảnh không) và `relevancy` (đo độ liên quan giữa câu trả lời, câu hỏi và đáp án mẫu).
  - Hàm `score` được thiết kế dưới dạng `async def`, giúp quá trình tính toán metrics không bị block khi hệ thống tích hợp gọi đồng loạt cho toàn bộ dataset.
- **Git Commit minh chứng**: 
  - `cd43e4121f380629d858c5ee3b91b9e37487a9fd` - "feat: retri metric engine" (Modified: `engine/evaluator.py`).

#### 2. Technical Depth (15/15)
- **Mức độ hiểu biết về chỉ số đánh giá (Metrics):**
  - **MRR (Mean reciprocal rank)**: Do trực tiếp xử lý truyền dữ liệu ID tìm kiếm, em hiểu rõ MRR đo lường thứ hạng của tài liệu chính xác đầu tiên được truy xuất. Thay vì chỉ quan tâm tài liệu có được xuất hiện trong top K không (Hit rate), MRR ưu tiên tài liệu đúng nằm ở những vị trí càng cao (gần top 1) càng tốt. 
  - **Cohen's Kappa & Position Bias**: Nhận thức được hệ thống LLM-as-a-judge sẽ gặp thiên kiến vị trí (Position Bias - xu hướng chọn câu trả lời đầu tiên hoặc cuối cùng ở multi-judge). Các chỉ số như Cohen's Kappa được nhóm thống nhất để theo dõi độ đồng thuận liên quan đến các judge khác nhau, giảm rủi ro thiên vị của AI.
- **Trade-off giữa Chi phí (Cost) và Chất lượng (Quality)**:
  - Việc đánh giá toàn bộ độ trung thực (faithfulness) và liên quan (relevancy) bằng LLM cho một benchmark đồ sộ sẽ gây tốn kém lượng lớn token và dễ gặp rate limit.
  - Sự đánh đổi được sử dụng: Implemented phương pháp string/token match (fast & free cost) như một baseline metric trong `evaluator.py`. Phương pháp này đạt tốc độ tính toán phần nghìn giây và chi phí bằng 0, bù đắp độ mượt hiệu năng và giảm tải tài chính, đánh đổi với độ hiểu sâu semantic mà các LLM judge thường làm.

#### 3. Problem Solving (10/10)
- **Vấn đề chia rẽ các chuỗi đo kiểm**: Khi lấy danh sách IDs và so khớp chuỗi String, có những đoạn nội dung rỗng do retriever lỗi hoặc thiếu ground truth.
- **Cách giải quyết**: Xử lý mượt mà các corner cases ngay trong hàm heuristic. 
  - Nếu `contexts` rỗng, trả về một điểm phạt cố định cho `faithfulness` là 0.35 (`if not contexts: return 0.35`).
  - Tránh lỗi chia cho zero nếu đáp án hoặc token truy xuất bị trắng bằng việc max margin (`max(1, len(e))`). 
  - Ứng dụng Regex `re.split(r"\W+", text.lower())` để bắt sát các token chữ cái và vứt bỏ tạp âm để có đánh giá giao thoa (intersection) chính xác cao, tạo ra hệ đo lường tương đối chuẩn với ít logic cồng kềnh.
