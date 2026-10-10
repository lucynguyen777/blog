# Xưởng nội dung local cho 20.000–50.000 bài

Xưởng chạy hoàn toàn bằng Python standard library và dữ liệu trong repo. Không gọi mô hình AI, API tìm kiếm, CMS hay dịch vụ viết bài. Vì vậy văn bản được tạo từ cấu trúc, facts và các khối biên tập local; chất lượng thực tế phụ thuộc vào việc tiếp tục làm giàu các khối này.

## Luồng mỗi lượt

`STOP CHECK → AUTO QUEUE → 2 bài → QA → 2 → QA → 2 → QA → 2 → QA → 2 → QA → 2 → QA → BUILD → COMMIT`

Một lượt tối đa 12 bài. GitHub Actions chạy phút 07 và 37 mỗi giờ. `workflow_dispatch` cho phép chạy 1–6 cặp. `concurrency` ngăn hai lượt viết đồng thời.

## Dữ liệu

- `content/articles/NH-xxxxx.json`: nguồn một bài, giúp git xử lý tốt hơn so với một file JSON khổng lồ.
- `data/factory-state.json`: con trỏ duy nhất và số liệu tiến độ.
- `data/factory-queue.jsonl`: nhật ký append-only cho bài PASS/REJECTED.
- `data/content-index.jsonl`: cache sinh lại được gồm URL, intent, số từ và hash nội dung. Đây không phải nguồn bài.
- `content/editorial-matrix.json`, `assets/search-index.json`, `sitemap.xml` (sitemap index → `sitemap-pages.xml` cho trang chủ/hub/trang tĩnh/`posts.json` và `sitemap-posts.xml` cho bài factory): dữ liệu dẫn xuất từ build. `lastmod` lấy từ ngày commit git cuối cùng của file nguồn (một lượt `git log`); nếu clone nông hoặc không có git thì dùng ngày dự phòng.

Không đẩy sẵn 50.000 dòng queue. Bộ lập kế hoạch dùng mixed-radix để tạo tuần tự hơn 50.000 tổ hợp ổn định từ chủ đề, xe, quận, đối tượng, bối cảnh và search intent. Cách này giữ commit nhỏ và cho phép dừng tức thì.

## QA 100 điểm, ngưỡng PASS 75

- Metadata: 15
- Cấu trúc và heading: 20
- Độ sâu 900–1.800 từ: 25
- Liên kết nội bộ: 15
- NAP/facts chuẩn: 10
- Khác biệt nội dung: 15

Bài bị chặn dù đủ điểm nếu trùng URL, trùng intent, quá giống bài đã có hoặc dưới 900 từ. Nhật ký vẫn ghi lý do để kiểm tra, nhưng bài bị chặn không được xuất bản.

## Điều khiển

```sh
# xem trạng thái
python3 scripts/content_factory.py status

# chạy thử, không ghi file
python3 scripts/content_factory.py run --dry-run

# chạy đúng 6 cặp
python3 scripts/content_factory.py run --limit 12

# tạo lại cache
python3 scripts/content_factory.py reindex

# dừng: tạo STOP_FACTORY ở thư mục gốc rồi commit
# chạy lại: xóa STOP_FACTORY rồi commit

# tắt bằng config: đặt "enabled": false trong config/content-factory.json
# (chặn mọi lượt chạy thật, kể cả workflow_dispatch; --dry-run vẫn chạy được)
```

`target_articles` đang để `null`, nên xưởng chỉ dừng bằng thao tác thủ công. Có thể đặt một số nguyên nếu muốn thêm giới hạn cứng. Trước các mốc 20.000, 30.000 và 50.000 cần xem báo cáo trùng lặp và chất lượng. GitHub Pages và trình duyệt không tải một JSON tìm kiếm chứa toàn bộ 50.000 bài; chỉ mục giao diện được giới hạn, còn cache JSONL giữ toàn bộ corpus.
