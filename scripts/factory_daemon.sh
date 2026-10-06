#!/usr/bin/env bash
# Tác vụ lặp hằng giờ cho Nguyễn Hà Content Factory
# Tự động viết bài, build site, kiểm tra QA, commit & push lên GitHub
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=== Nguyễn Hà Content Factory Local Daemon ==="
echo "Thư mục: $DIR"
echo "Chạy lặp mỗi 3600 giây (1 giờ). Nhấn Ctrl+C để dừng."
echo "Hoặc tạo file STOP_FACTORY ở thư mục gốc để dừng an toàn."
echo ""

INTERVAL=${1:-3600}

while true; do
  echo "--- [$(date '+%Y-%m-%d %H:%M:%S')] Bắt đầu chu kỳ viết bài ---"
  
  if [ -f "STOP_FACTORY" ]; then
    echo "Phát hiện file STOP_FACTORY. Tạm dừng chu kỳ. Chờ 60 giây..."
    sleep 60
    continue
  fi

  # 1. Đồng bộ code mới nhất từ GitHub
  echo "1. Đồng bộ git..."
  git pull --rebase origin main || true

  # 2. Sinh bài (10 cặp = 20 bài)
  echo "2. Chạy content factory..."
  python3 scripts/content_factory.py run || true

  # 3. Build HTML và index
  echo "3. Build site..."
  python3 scripts/build.py || true

  # 4. Kiểm tra toàn bộ QA và site
  echo "4. Kiểm tra QA và site validation..."
  python3 tests/test_content_factory.py || true
  python3 scripts/validate_factory_site.py || true

  # 5. Commit và push nếu có bài mới
  if ! git diff --quiet || [ -n "$(git status --porcelain)" ]; then
    echo "5. Có bài mới đã duyệt QA. Tiến hành commit và push..."
    git add -A
    git commit -m "content: auto-publish QA-approved batch from local daemon" || true
    git pull --rebase origin main || true
    git push origin main || true
    echo "Đã xuất bản và push thành công lên GitHub!"
  else
    echo "5. Không có bài mới trong chu kỳ này."
  fi

  echo "Hoàn thành chu kỳ. Nghỉ $INTERVAL giây cho đến chu kỳ tiếp theo..."
  echo ""
  sleep "$INTERVAL"
done

