# Logo và ảnh của Nguyễn Hà

Logo gốc: `assets/nguyen-ha-logo.svg`. Bản PNG 512 × 512 dùng cho dữ liệu Organization; favicon PNG 48 × 48, SVG và Apple Touch Icon 180 × 180 cùng một biểu tượng NH và hai bánh xe, màu #ffa266.

Ảnh chia sẻ mặc định: `assets/nguyen-ha-journal-social.png` (1200 × 630). Trang chủ dùng ảnh phố Bà Triệu 1400 × 788, giữ credit Elliot Andrews / Unsplash. Không gắn ảnh minh họa phố vào schema của những bài không có ảnh liên quan.

Ảnh trong bài tương lai có thể khai báo trường `image` gồm `path`, `alt`, `width`, `height`. Đường dẫn là asset local bắt đầu bằng `/assets/`. Kích thước phải là kích thước tệp thật; alt mô tả nội dung nhìn thấy, không nhồi từ khóa. Trường này dùng cho ảnh chia sẻ và BlogPosting.image; biên tập viên phải chèn ảnh vào nội dung với img, alt và width/height tương ứng, ghi nguồn ảnh và chỉ dùng ảnh có quyền sử dụng.

Logo cạnh tên thương hiệu có alt rỗng để trình đọc màn hình không đọc tên hai lần. SVG có title và desc khi mở trực tiếp. Không dùng logo như ảnh nội dung bài viết.

Kiểm tra: `python3 scripts/build.py`, `python3 scripts/validate_factory_site.py`. Metadata được render sẵn trong HTML, không phụ thuộc JavaScript hoặc API.
