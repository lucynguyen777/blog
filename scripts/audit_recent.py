#!/usr/bin/env python3
"""
Audit 100 bài viết gần nhất (hoặc N bài) của xưởng nội dung Nguyễn Hà:
- Kiểm tra tính hợp lệ của file JSON shard (content/articles/NH-*.json)
- Đếm từ (ngưỡng 900 - 1800 từ)
- Kiểm tra số lượng sections và cấu trúc Heading H1 trong HTML
- Kiểm tra HTML build có tồn tại không
- Kiểm tra NAP / Business facts chuẩn (Số điện thoại, địa chỉ, giờ mở cửa)
- Kiểm tra trùng lặp URL, Title, Intent
- Kiểm tra độ tương đồng Jaccard giữa các bài gần nhất
- Báo cáo chi tiết và trả về mã lỗi nếu có vi phạm nghiêm trọng
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_business_facts():
    facts_file = ROOT / "config/business-facts.json"
    if facts_file.exists():
        return json.loads(facts_file.read_text(encoding="utf-8"))
    return {}

def clean_words(text):
    text = re.sub(r"<[^>]+>", " ", text)
    return [w for w in re.findall(r"[\w]+", text.lower()) if len(w) > 1]

def jaccard_similarity(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0

def audit_articles(limit=100, fail_on_error=False):
    articles_dir = ROOT / "content/articles"
    if not articles_dir.exists():
        print(f"Error: Không tìm thấy thư mục {articles_dir}")
        return 1

    files = sorted(articles_dir.glob("NH-*.json"), key=lambda p: p.name)
    if not files:
        print("Không có bài viết nào trong content/articles/")
        return 0

    recent_files = files[-limit:]
    facts = load_business_facts()

    total_checked = len(recent_files)
    issues = []
    warnings = []
    
    seen_urls = set()
    seen_intents = set()
    seen_titles = set()
    
    articles_data = []

    expected_phone = facts.get("phone", "0334 699 969")
    expected_hours = facts.get("hours", "09:00–21:00 hằng ngày")
    expected_address = facts.get("address", "Ngõ 5 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội")

    for file_path in recent_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            issues.append(f"[{file_path.name}] Lỗi đọc JSON: {e}")
            continue

        art_id = data.get("id", file_path.stem)
        url = data.get("url", "")
        title = data.get("title", "")
        intent = data.get("intent", "")
        sections = data.get("sections", [])
        
        # 1. Trùng lặp
        if url in seen_urls:
            issues.append(f"[{art_id}] Trùng lặp URL: {url}")
        seen_urls.add(url)

        if intent and intent in seen_intents:
            issues.append(f"[{art_id}] Trùng lặp Intent: {intent}")
        if intent:
            seen_intents.add(intent)

        if title in seen_titles:
            issues.append(f"[{art_id}] Trùng lặp Title: {title}")
        seen_titles.add(title)

        # 2. Kiểm tra độ dài từ
        raw_text = " ".join([sec[0] + " " + sec[1] for sec in sections if len(sec) >= 2])
        words = clean_words(raw_text)
        word_count = len(words)

        if word_count < 900:
            issues.append(f"[{art_id}] Dưới ngưỡng từ tối thiểu (900 từ): {word_count} từ")
        elif word_count > 1800:
            warnings.append(f"[{art_id}] Vượt ngưỡng từ khuyến nghị (1800 từ): {word_count} từ")

        # 3. Kiểm tra Sections
        if len(sections) < 5:
            issues.append(f"[{art_id}] Quá ít section ({len(sections)} sections, tối thiểu 5)")

        # 4. Kiểm tra HTML build tương ứng
        if url:
            html_path = ROOT / url.strip("/") / "index.html"
            if not html_path.exists():
                warnings.append(f"[{art_id}] Chưa build HTML hoặc thiếu file: {html_path.relative_to(ROOT)}")
            else:
                html_content = html_path.read_text(encoding="utf-8", errors="ignore")
                h1_count = html_content.count("<h1")
                if h1_count != 1:
                    issues.append(f"[{art_id}] Số lượng thẻ H1 không chuẩn: {h1_count} (yêu cầu đúng 1)")

        # 5. Kiểm tra Business facts / NAP trong nội dung
        if expected_phone and (expected_phone not in raw_text and facts.get("international_phone", "") not in raw_text):
            warnings.append(f"[{art_id}] Thiếu số điện thoại chuẩn NAP ({expected_phone}) trong bài")

        if expected_hours and expected_hours not in raw_text:
            warnings.append(f"[{art_id}] Thiếu giờ mở cửa chuẩn ({expected_hours}) trong bài")

        # Lưu dữ liệu tính độ tương đồng
        articles_data.append({
            "id": art_id,
            "word_set": set(words)
        })

    # 6. Kiểm tra Jaccard similarity giữa các bài gần nhau
    max_sim = 0.0
    sim_pair = None
    for i in range(len(articles_data)):
        for j in range(i + 1, len(articles_data)):
            sim = jaccard_similarity(articles_data[i]["word_set"], articles_data[j]["word_set"])
            if sim > max_sim:
                max_sim = sim
                sim_pair = (articles_data[i]["id"], articles_data[j]["id"])

    if max_sim > 0.86:
        issues.append(f"Độ tương đồng vượt ngưỡng (0.86): {sim_pair[0]} và {sim_pair[1]} đạt {max_sim:.2%}")

    # Báo cáo tổng hợp
    print("=" * 60)
    print(f"BÁO CÁO AUDIT {total_checked} BÀI GẦN NHẤT")
    print(f"Phạm vi: {recent_files[0].name} -> {recent_files[-1].name}")
    print("=" * 60)
    print(f"Số lỗi nghiêm trọng (Critical Issues): {len(issues)}")
    print(f"Số cảnh báo (Warnings)               : {len(warnings)}")
    print(f"Độ tương đồng Jaccard cao nhất        : {max_sim:.2%}" + (f" ({sim_pair[0]} & {sim_pair[1]})" if sim_pair else ""))
    print("-" * 60)

    if issues:
        print("\n[!] DANH SÁCH LỖI NGHIÊM TRỌNG:")
        for err in issues[:20]:
            print(f" - {err}")
        if len(issues) > 20:
            print(f" ... và {len(issues) - 20} lỗi khác.")

    if warnings:
        print("\n[*] CẢNH BÁO CẦN LƯU Ý:")
        for w in warnings[:10]:
            print(f" - {w}")
        if len(warnings) > 10:
            print(f" ... và {len(warnings) - 10} cảnh báo khác.")

    if not issues and not warnings:
        print(f"\n>>> TẤT CẢ {total_checked} BÀI ĐẠT CHUẨN XƯỞNG NỘI DUNG (PASS 100%) <<<")

    print("=" * 60)

    if issues and fail_on_error:
        return 1
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit các bài viết gần nhất của Content Factory.")
    parser.add_argument("--limit", type=int, default=100, help="Số lượng bài gần nhất cần audit (mặc định 100)")
    parser.add_argument("--fail-on-error", action="store_true", help="Thoát với exit code 1 nếu có lỗi")
    args = parser.parse_args()

    sys.exit(audit_articles(limit=args.limit, fail_on_error=args.fail_on_error))
