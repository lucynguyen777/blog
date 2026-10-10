"""
Site template & component engine for Nguyễn Hà Journal.
Loads components, injects central config & facts, handles SEO & JSON-LD schemas.
"""
from pathlib import Path
import json, html

ROOT = Path(__file__).resolve().parent.parent
E = html.escape

# Load central configurations
SITE_CFG = json.loads((ROOT / 'config/site-config.json').read_text()) if (ROOT / 'config/site-config.json').exists() else {}
FACTS = json.loads((ROOT / 'config/business-facts.json').read_text()) if (ROOT / 'config/business-facts.json').exists() else {}
SITE_INFO = json.loads((ROOT / 'content/site.json').read_text())

# Load component templates
PARTIALS_DIR = ROOT / 'templates/partials'
def load_partial(name):
    p = PARTIALS_DIR / f'{name}.html'
    return p.read_text(encoding='utf-8') if p.exists() else ''

PARTIAL_HEADER = load_partial('header')
PARTIAL_FOOTER = load_partial('footer')
PARTIAL_CONTACT_BOX = load_partial('contact_box')
PARTIAL_CARD = load_partial('card')
PARTIAL_CTA_BANNER = load_partial('cta_banner')
PARTIAL_AUTHOR_BOX = load_partial('author_box')
PARTIAL_RELATED_POSTS = load_partial('related_posts')
PARTIAL_PAGINATION = load_partial('pagination')
PARTIAL_WIDGETS = load_partial('widgets')

ICON_PATH = {
    'menu': '<path d="M4 7h16M4 12h16M4 17h16"/>',
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>',
    'moon': '<path d="M20 15.5A9 9 0 0 1 8.5 4 9 9 0 1 0 20 15.5Z"/>',
    'close': '<path d="m6 6 12 12M6 18 18 6"/>',
    'chat': '<path d="M21 11.5a8.5 8.5 0 0 1-9 8.5 10 10 0 0 1-3.5-.6L4 21v-5a8.5 8.5 0 1 1 17-4.5Z"/><path d="m7 14 4-4 3 3 3-3"/>',
    'phone': '<path d="M7 3H4a1 1 0 0 0-1 1c0 9.4 7.6 17 17 17a1 1 0 0 0 1-1v-3l-5-2-2 2a13 13 0 0 1-7-7l2-2-2-5Z"/>',
    'send': '<path d="m12 19 0-14M6 11l6-6 6 6"/>',
    'refresh': '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/>',
    'arrow_up': '<path d="m18 15-6-6-6 6"/>'
}

def icon(n):
    return f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">{ICON_PATH[n]}</svg>'

def render_contact_box():
    return PARTIAL_CONTACT_BOX.format(
        business_name=E(SITE_INFO['name']),
        business_address=E(SITE_INFO['address']),
        business_hours=E(SITE_INFO['hours']),
        business_phone=E(SITE_INFO['phone']),
        business_phone_clean=SITE_INFO['phone'].replace(' ', ''),
        business_email=E(SITE_INFO['email'])
    )

def render_header(top_links, hubs):
    feat = SITE_CFG.get('features', {})
    theme_btn = f'<button id="theme-toggle" class="icon-btn" aria-label="Chuyển sang chế độ tối">{icon("moon")}</button>' if feat.get('enable_theme_toggle', True) else ''
    util_links_html = ''.join(f'<a href="{u}">{E(t)}</a>' for t, u in top_links)
    support_links = [('FAQ', '/faq/'), ('Liên hệ', '/lien-he/'), ('Điều khoản dịch vụ', '/dieu-khoan-dich-vu/'), ('Chính sách bảo mật', '/chinh-sach-bao-mat/')]
    supp_links_html = ''.join(f'<a href="{u}">{E(t)}</a>' for t, u in support_links)
    
    cols_html = ''.join(
        '<details open><summary>' + E(h['label']) + '</summary><a class="hub-link" href="' + h['url'] + '">Tổng quan ' + E(h['label'].lower()) + '</a>' +
        ''.join('<a href="' + c['url'] + '">' + E(c['label']) + '</a>' for c in h['children']) + '</details>'
        for h in hubs
    )

    return PARTIAL_HEADER.format(
        brand_mark=E(SITE_CFG.get('site', {}).get('brand_mark', 'n.')),
        site_name=E(SITE_INFO['name']),
        brand_sub=E(SITE_CFG.get('site', {}).get('brand_sub', 'JOURNAL · HÀ NỘI')),
        theme_toggle_html=theme_btn,
        icon_menu=icon('menu'),
        icon_close=icon('close'),
        utility_links=util_links_html,
        menu_columns_html=cols_html,
        support_links=supp_links_html
    )

def render_footer(top_links, hubs, contact_box_html):
    util_links_html = ''.join(f'<a href="{u}">{E(t)}</a>' for t, u in top_links)
    support_links = [('FAQ', '/faq/'), ('Liên hệ', '/lien-he/'), ('Điều khoản dịch vụ', '/dieu-khoan-dich-vu/'), ('Chính sách bảo mật', '/chinh-sach-bao-mat/')]
    supp_links_html = ''.join(f'<a href="{u}">{E(t)}</a>' for t, u in support_links)

    cols_html = ''.join(
        '<div><h3><a href="' + h['url'] + '" style="color:var(--ink);font-weight:650">' + E(h['label']) + '</a></h3>' +
        ''.join('<a href="' + c['url'] + '">' + E(c['label']) + '</a>' for c in h['children']) + '</div>'
        for h in hubs
    )

    return PARTIAL_FOOTER.format(
        brand_mark=E(SITE_CFG.get('site', {}).get('brand_mark', 'n.')),
        site_name=E(SITE_INFO['name']),
        brand_sub=E(SITE_CFG.get('site', {}).get('brand_sub', 'JOURNAL · HÀ NỘI')),
        contact_box=contact_box_html,
        utility_links=util_links_html,
        footer_columns_html=cols_html,
        support_links=supp_links_html
    )

def render_card(p, hubs):
    hub_obj = next((h for h in hubs if h['slug'] == p['hub']), None)
    hub_label = hub_obj['label'] if hub_obj else 'Cẩm nang'
    date_display = p.get('publish_display', '')
    card_date_html = f' · {E(date_display)}' if date_display else ''
    return PARTIAL_CARD.format(
        card_url=p['url'],
        card_tone=p.get('tone', 'gold'),
        card_title=E(p['title']),
        card_hub_label=E(hub_label),
        card_excerpt=E(p['excerpt']),
        card_date=card_date_html
    )

def render_conditional_cta(hub_slug):
    feat = SITE_CFG.get('features', {})
    if not feat.get('enable_conditional_cta', True):
        return ''
    
    if hub_slug in ('thue-xe', 'thue-xe-may'):
        eyebrow = 'DỊCH VỤ THUÊ XE'
        title = 'Cần thuê xe máy nhận ngay tại Hà Nội?'
        desc = 'Xe số, xe ga, xe điện và 50cc sẵn sàng. Hỗ trợ giao xe tận nơi cho hợp đồng tuần và tháng.'
        primary_link = '/bang-gia/'
        primary_text = 'Xem bảng giá'
        secondary_link = '/lien-he/'
        secondary_text = 'Liên hệ cửa hàng'
        tone = 'gold'
    elif hub_slug in ('bao-duong', 'xe-may', 'xe-dien', 'xe-dap', 'o-to'):
        eyebrow = 'KỸ THUẬT & BẢO DƯỠNG'
        title = 'Kiểm tra kỹ thuật xe trước mỗi chuyến đi'
        desc = 'Lưu số kỹ thuật Nguyễn Hà để được hướng dẫn xử lý sự cố nhanh chóng trên đường.'
        primary_link = '/bao-duong/xe-may/kiem-tra-truoc-khi-nhan/'
        primary_text = 'Xem checklist xe'
        secondary_link = '/lien-he/'
        secondary_text = 'Hỏi tư vấn'
        tone = 'white'
    elif hub_slug in ('du-lich', 'kinh-nghiem'):
        eyebrow = 'KHÁM PHÁ HÀ NỘI'
        title = 'Chọn xe máy linh hoạt để vi vu phố cổ'
        desc = 'Chủ động lịch trình dạo phố Hồ Gươm, Hồ Tây với chi phí thuê minh bạch, xe bảo dưỡng tốt.'
        primary_link = '/thue-xe-may/ha-noi/'
        primary_text = 'Cẩm nang thuê xe'
        secondary_link = '/du-lich/ha-noi/'
        secondary_text = 'Lịch trình du lịch'
        tone = 'gold'
    else:
        eyebrow = 'NGUYỄN HÀ JOURNAL'
        title = 'Cần hỗ trợ thông tin hoặc tư vấn hành trình?'
        desc = 'Đội ngũ Nguyễn Hà luôn sẵn sàng giải đáp thắc mắc về phương tiện và thủ tục di chuyển.'
        primary_link = '/lien-he/'
        primary_text = 'Liên hệ hỗ trợ'
        secondary_link = '/bang-gia/'
        secondary_text = 'Bảng giá niêm yết'
        tone = 'gold'

    return PARTIAL_CTA_BANNER.format(
        cta_tone=tone,
        cta_eyebrow=eyebrow,
        cta_title=title,
        cta_desc=desc,
        cta_primary_link=primary_link,
        cta_primary_text=primary_text,
        cta_secondary_link=secondary_link,
        cta_secondary_text=secondary_text
    )

def render_author_box():
    return PARTIAL_AUTHOR_BOX.format(
        brand_mark=E(SITE_CFG.get('site', {}).get('brand_mark', 'n.')),
        site_name=E(SITE_INFO['name'])
    )

def render_pagination(base_url, current_page, total_pages):
    if total_pages <= 1:
        return ''
    links = []
    
    # Previous button
    if current_page > 1:
        prev_url = base_url if current_page == 2 else f'{base_url}trang-{current_page - 1}/'
        links.append(f'<a class="page-link prev" href="{prev_url}" aria-label="Trang trước">«</a>')
    
    # Page numbers
    for p in range(1, total_pages + 1):
        p_url = base_url if p == 1 else f'{base_url}trang-{p}/'
        if p == current_page:
            links.append(f'<span class="page-link active" aria-current="page">{p}</span>')
        else:
            links.append(f'<a class="page-link" href="{p_url}">{p}</a>')
            
    # Next button
    if current_page < total_pages:
        next_url = f'{base_url}trang-{current_page + 1}/'
        links.append(f'<a class="page-link next" href="{next_url}" aria-label="Trang sau">»</a>')
        
    return PARTIAL_PAGINATION.format(pagination_links=''.join(links))

def render_widgets():
    feat = SITE_CFG.get('features', {})
    back_to_top_btn = f'''<button class="float back-to-top" id="back-to-top" aria-label="Lên đầu trang nhanh" title="Lên đầu trang">{icon('arrow_up')}</button>''' if feat.get('enable_back_to_top', True) else ''
    call_btn = f'''<button class="float call-toggle" id="call-toggle" aria-label="Mở liên hệ nhanh" aria-expanded="false" aria-controls="quick-links">{icon('phone')}</button>''' if feat.get('enable_quick_call', True) else ''
    quick_nav = f'''<nav id="quick-links" class="quick-links" aria-label="Liên hệ nhanh" hidden><a href="tel:{SITE_INFO['phone'].replace(' ', '')}"><span>{icon('phone')}</span>Gọi {E(SITE_INFO['phone'])}</a><a href="{SITE_CFG.get('business', {}).get('zalo', 'https://zalo.me/0334699969')}" target="_blank" rel="noopener noreferrer"><span>Z</span>Nhắn Zalo</a><a href="{SITE_CFG.get('business', {}).get('whatsapp', 'https://wa.me/84334699969')}" target="_blank" rel="noopener noreferrer"><span>W</span>Nhắn WhatsApp</a></nav>''' if feat.get('enable_quick_call', True) else ''
    
    chat_btn = f'''<button class="float chat-toggle" id="chat-toggle" aria-label="Mở trợ lý Nguyễn Hà" aria-expanded="false" aria-controls="chat-panel">{icon('chat')}</button>''' if feat.get('enable_chatbot', True) else ''
    chat_panel = f'''<section class="chat-panel" id="chat-panel" aria-label="Trợ lý Nguyễn Hà" hidden><div class="chat-head"><div><strong>Trợ lý Nguyễn Hà</strong><small>Tra cứu nội dung blog</small></div><div class="chat-controls"><button class="icon-btn" id="chat-refresh" aria-label="Đọc lại dữ liệu blog">{icon('refresh')}</button><button class="icon-btn" id="chat-close" aria-label="Đóng trợ lý">{icon('close')}</button></div></div><div id="chat-messages" class="chat-messages" role="log" aria-live="polite" aria-relevant="additions"></div><form id="chat-form" class="chat-form"><input id="chat-input" name="question" aria-label="Câu hỏi cho trợ lý" placeholder="Bạn muốn tìm hiểu điều gì?" maxlength="500" autocomplete="off" required><button class="send-btn" aria-label="Gửi câu hỏi">{icon('send')}</button></form><p class="chat-disclaimer">Trả lời từ blog. Vui lòng liên hệ để xác nhận xe còn sẵn.</p></section>''' if feat.get('enable_chatbot', True) else ''

    return PARTIAL_WIDGETS.format(
        back_to_top_html=back_to_top_btn,
        call_toggle_html=call_btn,
        quick_links_html=quick_nav,
        chat_toggle_html=chat_btn,
        chat_panel_html=chat_panel
    )

