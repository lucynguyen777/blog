# Quy ước mở rộng

1. Nguồn bài tách một file/bài; index JSONL là cache.
2. Build theo batch 12 bài và kiểm tra fail-closed.
3. Sitemap phải tách thành sitemap index khi chạm 50.000 URL hoặc giới hạn kích thước.
4. Search client chỉ tải shard cần thiết, không tải toàn bộ corpus.
5. Mỗi 1.000 bài phải chạy kiểm tra intent, duplicate, link và schema toàn kho trước khi tiếp tục.
6. Các facts thời gian thực như tồn xe không được sinh tự động.
