# Nguyễn Hà Journal

Blog tĩnh cho **https://thuha.rentbikehanoi.com**, tương thích GitHub Pages. Không cần API key, dịch vụ AI hay cơ sở dữ liệu ngoài.

## Xưởng nội dung liên tục

Workflow `.github/workflows/content-factory.yml` tự tạo hàng đợi và xuất bản tối đa 6 cặp, mỗi cặp 2 bài, trong một lượt. Writer deterministic chỉ dùng Python và dữ liệu local; bài phải đạt ít nhất 75 điểm và không có lỗi critical. Nguồn mới được chia nhỏ trong `content/articles/`; `data/content-index.jsonl` là cache có thể dựng lại. Xem `docs/CONTENT-FACTORY.md` để chạy, dừng và khôi phục.

## Nội dung và ma trận

- `content/site.json`: thông tin cửa hàng. Địa chỉ và giờ mở cửa dùng yêu cầu mới nhất: 24F ngõ 5 Nguyễn Văn Cừ; 08:00–17:00.
- `content/posts.json`: bài viết đã xuất bản; mỗi dòng khai báo URL, Hub, trang pillar cha, từ khóa, mô tả và các section HTML.
- `content/editorial-matrix.json`: ma trận bài hiện có, sinh khi build. Không phải 500 hay 20.000 bài đã viết.
- Chín Hub: Thuê xe; Xe máy; Xe điện; Xe đạp; Ô tô; Sửa chữa & bảo dưỡng; Du lịch Việt Nam; Luật & bằng lái; Kinh nghiệm di chuyển.
- Menu và footer dùng chung NAV trong bộ dựng; không sửa độc lập.
- Chuyên mục trống đặt `noindex,follow`, không đưa vào sitemap. URL thật, metadata, canonical, breadcrumb và BlogPosting được xuất thành HTML.

## Thêm bài

Thêm một object vào `content/posts.json`, dùng URL duy nhất dạng `/du-lich/ha-noi/ten-bai/`; khai báo `hub`, `parent`, `sections` (cặp tiêu đề + nội dung HTML) và `keywords`. Không tạo riêng các bài cùng search intent chỉ đổi từ khóa. Có bài thông tin riêng mới mở các trang địa phương; không tạo tổ hợp loại xe × địa điểm × thời gian tự động.

Chạy Python 3, không cần dependency:

```sh
python3 scripts/build.py
python3 -m http.server 8080
```

Commit cả nguồn và HTML được tạo. GitHub Pages dùng nhánh `main`, thư mục `/ (root)` đã có, giữ `CNAME`. Không cần GitHub Actions để hiển thị. Nếu sửa bài trực tiếp trong HTML, chatbot có thể đọc qua nút làm mới, nhưng lần build tiếp theo sẽ dựng lại từ `posts.json`.

## Trợ lý local

Chatbot là hệ thống truy xuất nội dung local, không phải mô hình ngôn ngữ. Đọc chỉ mục `assets/search-index.json` (dựng bằng cách cào HTML đã render), nhận diện intent, chuẩn hóa tiếng Việt không dấu, mở rộng từ đồng nghĩa, xếp hạng BM25 và giữ chủ đề câu hỏi tiếp nối. Trả lời gắn link nguồn. Không biết tồn xe thời gian thực, không tạo đặt xe, không tự kết luận pháp lý.

Nút làm mới đọc sitemap và cào tối đa 40 URL với 3 tác vụ đồng thời, timeout từng trang; không gọi API bên ngoài. Site lớn cần rebuild chỉ mục cho toàn bộ nội dung; không cào 20.000 trang trong trình duyệt mỗi lượt hỏi. Dữ liệu hội thoại chỉ tồn tại trong tab; lựa chọn màu sáng/tối lưu cục bộ. Mất kết nối hiển thị thông báo hoặc dùng dữ liệu đã đọc.

Ảnh Hà Nội: Elliot Andrews / Unsplash, nguồn https://unsplash.com/@elliot_ra8. Ảnh là ảnh biên tập, không đại diện đội xe cửa hàng. File WebP tối ưu được lưu trong repo.
