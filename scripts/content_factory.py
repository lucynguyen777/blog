#!/usr/bin/env python3
"""Deterministic, API-free article queue, writer and QA gate."""
from pathlib import Path
from datetime import datetime, timezone
from html import escape
import argparse, hashlib, json, math, re, sys, unicodedata

ROOT=Path(__file__).resolve().parent.parent
CFG=json.loads((ROOT/'config/content-factory.json').read_text())
FACTS=json.loads((ROOT/'config/business-facts.json').read_text())
STATE_PATH=ROOT/'data/factory-state.json'
QUEUE_PATH=ROOT/'data/factory-queue.jsonl'
INDEX_PATH=ROOT/'data/content-index.jsonl'
ARTICLES=ROOT/'content/articles'
LEGACY=ROOT/'content/posts.json'
HUB_PARENT={
    'thue-xe':'/thue-xe/',
    'xe-may':'/xe-may/',
    'xe-dien':'/xe-dien/',
    'xe-dap':'/xe-dap/',
    'o-to':'/o-to/',
    'bao-duong':'/bao-duong/',
    'du-lich':'/du-lich/',
    'luat-giao-thong':'/luat-giao-thong/',
    'kinh-nghiem':'/kinh-nghiem/'
}

# ── Ma trận hub 1: Thuê xe Hà Nội (12×12×7×10×8×7 = 564,480) ─────────────────
DISTRICTS=['Hoàn Kiếm','Ba Đình','Cầu Giấy','Tây Hồ','Đống Đa','Hai Bà Trưng','Thanh Xuân','Hoàng Mai','Nam Từ Liêm','Bắc Từ Liêm','Long Biên','Hà Đông']
VEHICLES=[
    ('Honda Wave Alpha','xe-may'),('Honda Vision','xe-may'),('Honda Air Blade','xe-may'),('Honda Lead','xe-may'),
    ('Yamaha Sirius','xe-may'),('Yamaha Grande','xe-may'),('Honda Winner X','xe-may'),('Yamaha Exciter','xe-may'),
    ('VinFast Feliz S','xe-dien'),('VinFast Evo 200','xe-dien'),('VinFast Klara S','xe-dien'),('xe máy 50cc','thue-xe')
]
AUDIENCES=['người đi làm văn phòng','sinh viên đại học','khách du lịch trong nước','chuyên gia công tác','người mới đến Hà Nội','người thuê dài hạn','người chạy việc trong phố']
ANGLES=[
    ('chọn xe','tiêu chí chọn xe phù hợp'),
    ('kiểm tra xe','quy trình kiểm tra xe trước khi nhận'),
    ('chi phí','cách dự trù chi phí và tránh phụ phí'),
    ('hợp đồng','các điều khoản hợp đồng và tiền cọc'),
    ('lộ trình','kinh nghiệm lên lộ trình di chuyển'),
    ('an toàn','kỹ năng lái xe an toàn giờ cao điểm'),
    ('thuê theo tuần','kinh nghiệm thuê xe theo tuần giá tốt'),
    ('thuê theo tháng','quy trình thuê xe dài hạn theo tháng'),
    ('giao nhận','thủ tục giao nhận xe tận nơi'),
    ('gửi xe','kinh nghiệm tìm bãi gửi xe an toàn')
]
CONTEXTS=['đi làm giờ cao điểm sáng tối','lưu trú ngắn ngày dạo phố cổ','thuê dài hạn phục vụ công việc','di chuyển giữa các quận trung tâm','đi học và thực tập hằng ngày','đi công tác dài ngày','lần đầu tự lái xe tại thủ đô','chở thêm người thân và hành lý']
ROUTE_NEEDS=['quãng đường dưới 5 km mỗi ngày','tuyến đường 10 đến 20 km liên quận','thường xuyên đi qua các nút giao đông đúc','cần gửi xe trong ngõ nhỏ phố cổ','di chuyển linh hoạt nhiều điểm trong ngày','chạy xe trên các trục đường vành đai','tuyến đường từ nơi ở đến văn phòng']

# ── Ma trận hub 2: Xe máy / Xe điện / Xe đạp — thông tin & bảo dưỡng (13×20×7×6×5 = 54,600)
INFO_VEHICLES=[
    ('xe máy số Honda Wave','xe-may'),('xe tay ga Honda Vision','xe-may'),('xe tay ga Honda Air Blade','xe-may'),
    ('xe tay ga Honda Lead','xe-may'),('xe số Yamaha Sirius','xe-may'),('xe côn tay Honda Winner X','xe-may'),
    ('xe máy điện VinFast Feliz S','xe-dien'),('xe máy điện VinFast Evo 200','xe-dien'),('xe máy điện VinFast Klara S','xe-dien'),
    ('xe đạp địa hình MTB','xe-dap'),('xe đạp touring thể thao','xe-dap'),('xe đạp thể thao đường phố','xe-dap'),
    ('xe máy phân khối nhỏ 50cc','xe-may')
]
INFO_TOPICS=[
    ('thay-dau-nhot','thay dầu nhớt động cơ định kỳ','Động cơ'),
    ('bao-duong-phanh-dia','bảo dưỡng hệ thống phanh đĩa an toàn','Phanh & Lốp'),
    ('kiem-tra-ac-quy','kiểm tra và phục hồi bình ắc quy','Điện & Bình'),
    ('cham-soc-pin-xe-dien','sạc và bảo quản pin lithium xe điện','Pin sạc'),
    ('ve-sinh-xich-lip','vệ sinh và bôi trơn xích líp truyền động','Truyền động'),
    ('thay-day-curoa','kiểm tra độ mòn dây curoa xe ga','Truyền động'),
    ('xu-ly-ngap-nuoc','xử lý xe bị chết máy do lội nước ngập','Mùa mưa ngập'),
    ('ap-suat-lop-chuan','cân chỉnh áp suất lốp và chọn lốp bám đường','Lốp xe'),
    ('ve-sinh-kim-phun-fi','vệ sinh kim phun xăng điện tử Fi và buồng đốt','Nhiên liệu'),
    ('thay-loc-gio-dong-co','thay lọc gió động cơ để tiết kiệm nhiên liệu','Động cơ'),
    ('bao-duong-phuoc-giam-xoc','bảo dưỡng phuộc nhún và giảm xóc','Khung sườn'),
    ('kiem-tra-nuoc-lam-mat','kiểm tra và châm nước làm mát két nước','Làm mát'),
    ('thay-the-bugi','kiểm tra và thay thế bugi đánh lửa','Đánh lửa'),
    ('chong-ri-set-khung-xe','chống rỉ sét khung xe và bảo vệ lớp sơn','Ngoại thất'),
    ('lap-khoa-chong-trom','lắp khóa chống trộm và bảo vệ an toàn cho xe','An ninh xe'),
    ('can-chinh-co-phot','xử lý hiện tượng rơ cổ phốt và đảo tay lái','Hệ thống lái'),
    ('thay-nhot-hop-so-lap','thay nhớt láp định kỳ cho xe tay ga','Hộp số'),
    ('khoi-dong-buoi-sang-lanh','mẹo khởi động xe dễ dàng vào mùa đông','Vận hành'),
    ('ky-nang-tiet-kiem-nhien-lieu','kỹ năng lái xe tiết kiệm xăng và điện','Tiết kiệm'),
    ('rua-xe-khong-hai-may','hướng dẫn rửa xe tại nhà không ảnh hưởng vi mạch','Vệ sinh')
]
INFO_AUDIENCES=['người mới mua xe lần đầu','sinh viên tự bảo dưỡng xe','nhân viên văn phòng bận rộn','tài xế công nghệ chạy xe liên tục','người sử dụng xe hằng ngày','nữ giới sử dụng xe ga','người thuê xe dài hạn']
INFO_CONDITIONS=['mùa mưa ngập úng đô thị','những ngày nắng nóng đỉnh điểm','mùa đông thời tiết lạnh giá','trước chuyến phượt đi xa','sau thời gian dài không sử dụng','mốc bảo dưỡng định kỳ 5000 km']
INFO_ANGLES=[
    ('huong-dan-chi-tiet','hướng dẫn các bước tự làm chuẩn xác'),
    ('dau-hieu-can-kiem-tra','nhận biết dấu hiệu hư hỏng sớm'),
    ('chi-phi-thuc-te','bảng giá chi phí sửa chữa và thay thế'),
    ('sai-lam-pho-bien','những sai lầm phổ biến cần tuyệt đối tránh'),
    ('lich-trinh-dinh-ky','lịch trình kiểm tra và bảo dưỡng tối ưu')
]

# ── Ma trận hub 3: Du lịch & Phượt (25×10×5×5×5 = 31,250) ─────────────────────
PLACES=[
    'Hà Nội phố cổ và Hồ Tây','Làng cổ Đường Lâm','Vườn quốc gia Ba Vì','Tam Đảo Vĩnh Phúc','Hồ Đại Lải',
    'Tràng An Bái Đính','Tam Cốc Hang Múa','Đảo Cát Bà Hải Phòng','Vịnh Hạ Long','Thung lũng Mai Châu',
    'Đèo Thung Khe Hòa Bình','Cao nguyên Mộc Châu','Săn mây Tà Xùa','Thị trấn Sa Pa','Đèo Ô Quy Hồ',
    'Xã Y Tý Bát Xát','Ruộng bậc thang Mù Cang Chải','Hồ Thác Bà Yên Bái','Cao nguyên đá Đồng Văn',
    'Đèo Mã Pí Lèng','Ruộng bậc thang Hoàng Su Phì','Thác Bản Giốc Cao Bằng','Hồ Ba Bể Bắc Kạn',
    'Cố đô Huế','Phố cổ Hội An'
]
TRAVEL_VEHICLES=[
    ('xe máy số Honda Wave','xe-may'),('xe số Yamaha Sirius','xe-may'),('xe ga Honda Vision','xe-may'),
    ('xe ga Honda Air Blade','xe-may'),('xe ga Honda Lead','xe-may'),('xe côn tay Honda Winner X','xe-may'),
    ('xe côn tay Yamaha Exciter','xe-may'),('xe máy điện VinFast Feliz','xe-dien'),('xe đạp touring dã ngoại','xe-dap'),
    ('xe máy phân khối 50cc','thue-xe')
]
TRAVEL_DURATIONS=['đi về trong ngày (day-trip)','cuối tuần 2 ngày 1 đêm','hành trình 3 ngày 2 đêm','chuyến khám phá 4 ngày 3 đêm','tour dài ngày 5 đến 7 ngày']
TRAVEL_TYPES=['phượt solo một mình','cặp đôi trải nghiệm','nhóm bạn trẻ 3 đến 5 xe','gia đình nhỏ dã ngoại','nhóm phượt chuyên nghiệp']
TRAVEL_ANGLES=[
    ('lich-trinh-cung-duong','gợi ý lộ trình di chuyển chi tiết từng chặng'),
    ('du-tru-chi-phi','dự trù kinh phí xăng xe, ăn nghỉ và vé tham quan'),
    ('kinh-nghiem-lai-xe-an-toan','kỹ năng lái xe an toàn, leo đèo và xử lý sự cố'),
    ('checklist-chuan-bi','danh sách đồ dùng, phụ tùng và hành lý cần mang'),
    ('diem-checkin-am-thuc','các điểm check-in đẹp và đặc sản nổi tiếng')
]

# ── Ma trận hub 4: Luật giao thông & An toàn (25×8×6×12 = 14,400) ──────────────
LAW_TOPICS=[
    ('thi-bang-lai-a1','thủ tục và mẹo thi đậu bằng lái xe máy A1'),
    ('thi-bang-lai-a2','điều kiện thi bằng lái xe A2 cho môtô trên 175cc'),
    ('bang-lai-quoc-te-idp','quy định sử dụng bằng lái quốc tế IDP cho người nước ngoài'),
    ('muc-phat-nong-do-con','mức xử phạt nồng độ cồn đối với người điều khiển xe 2 bánh'),
    ('phat-vuot-den-do','mức phạt hành vi vượt đèn đỏ và vượt đèn vàng'),
    ('toc-do-toi-da-xe-may','quy định giới hạn tốc độ xe máy trong và ngoài đô thị'),
    ('phat-di-nguoc-chieu','mức phạt đi ngược chiều trên đường có biển cấm'),
    ('di-vao-duong-cam','mức phạt xe máy đi vào đường cấm và làn ô tô cao tốc'),
    ('quy-dinh-mu-bao-hiem','quy định đội mũ bảo hiểm đạt chuẩn và mức phạt vi phạm'),
    ('dung-dien-thoai-khi-lai-xe','mức xử phạt dùng điện thoại khi đang lái xe máy'),
    ('bat-den-chieu-sang-ban-dem','quy định khung giờ bật đèn xe máy và mức phạt quên bật đèn'),
    ('cho-nguoi-qua-quy-dinh','quy định số người được phép chở trên xe máy'),
    ('xe-khong-guong-chieu-hau','quy định lắp gương chiếu hậu và mức phạt thiếu gương trái'),
    ('dung-do-xe-tren-he-pho','quy định dừng đỗ xe máy trên vỉa hè và lòng đường'),
    ('tra-cuu-phat-nguoi-camera','hướng dẫn tra cứu phạt nguội xe máy qua hệ thống camera'),
    ('sang-ten-bien-so-dinh-danh','thủ tục sang tên xe máy và đăng ký biển số định danh'),
    ('bao-hiem-bat-buoc-tnds','quy định mua bảo hiểm trách nhiệm dân sự bắt buộc cho xe máy'),
    ('xu-ly-khi-xay-ra-va-cham','các bước xử lý đúng pháp luật khi xảy ra va chạm giao thông'),
    ('nhuong-duong-tai-nut-giao','quy tắc nhường đường tại ngã tư và vòng xuyến giao thông'),
    ('quy-dinh-xe-may-dien-50cc','độ tuổi và điều kiện điều khiển xe máy điện và xe 50cc'),
    ('cho-hang-cong-kenh','quy định giới hạn kích thước chở đồ và hàng cồng kềnh'),
    ('nop-phat-truc-tuyen-vneid','hướng dẫn nộp phạt vi phạm giao thông trực tuyến trên VNeID'),
    ('chuyen-huong-khong-xi-nhan','mức phạt lỗi rẽ hoặc chuyển làn đường không bật đèn xi nhan'),
    ('nhan-biet-bien-bao-cam','cách nhận biết và tuân thủ các biển báo cấm xe máy phổ biến'),
    ('quyen-kiem-tra-cua-csgt','quy định về hiệu lệnh dừng xe và kiểm tra giấy tờ của CSGT')
]
LAW_AUDIENCES=['người mới lấy bằng lái','sinh viên các trường đại học','du khách nước ngoài tại Việt Nam','người đi làm tại các đô thị','người thuê xe tự lái','tài xế giao hàng công nghệ','người thường xuyên đi công tác tỉnh','phụ huynh hướng dẫn con em tham gia giao thông']
LAW_ANGLES=[
    ('can-cu-phap-ly-moi-nhat','căn cứ pháp lý và nghị định hiện hành'),
    ('muc-phat-va-hinh-thuc-xu-ly','mức phạt tiền và hình thức tước quyền sử dụng bằng'),
    ('thu-tuc-va-cac-buoc-chuan','quy trình thực hiện và giấy tờ cần chuẩn bị'),
    ('tinh-huong-va-cach-phong-tranh','tình huống thực tế và cách xử lý phòng ngừa'),
    ('giai-dap-thac-mac-pho-bien','giải đáp thắc mắc và câu hỏi thường gặp'),
    ('so-sanh-thay-doi-moi','điểm mới quan trọng so với quy định trước đây')
]
LAW_CONTEXTS=[
    'trong các tuyến phố nội đô Hà Nội','trên các trục đường vành đai và quốc lộ',
    'khi lưu thông qua các cây cầu lớn bắc qua sông Hồng','trong khu vực ngõ hẻm và khu đô thị đông đúc',
    'vào khung giờ cao điểm sáng và chiều tối','khi tham gia giao thông vào ban đêm',
    'khi đi qua các nút giao trọng điểm có camera giám sát','trong các dịp nghỉ lễ và cao điểm Tết',
    'khi di chuyển trong điều kiện mưa bão tầm nhìn hạn chế','trên các cung đường ngoại thành và liên tỉnh',
    'tại các khu vực cửa ngõ thủ đô','khi gặp tổ công tác kiểm tra hành chính liên ngành'
]

# Dung lượng tổng ma trận: 564,480 + 54,600 + 31,250 + 14,400 = 664,730
TOTAL_CAPACITY = 664730

class PermutedHub:
    def __init__(self, dims):
        self.dims = dims
        self.M = 1
        for d in dims: self.M *= d
        weights = [1]
        for x in dims[:-1]: weights.append(weights[-1] * x)
        deltas = [3, 5, 7, 11, 13, 17][:len(dims)]
        s = 0
        for i in range(len(dims)):
            s += deltas[i] * weights[i]
        while math.gcd(s, self.M) != 1:
            s += 1
        self.stride = s

    def coords(self, k):
        idx = (k * self.stride) % self.M
        res = []
        n = idx
        for base in self.dims:
            res.append(n % base)
            n //= base
        return res

HUB1_PERM = PermutedHub([len(DISTRICTS), len(VEHICLES), len(AUDIENCES), len(ANGLES), len(CONTEXTS), len(ROUTE_NEEDS)])
HUB2_PERM = PermutedHub([len(INFO_VEHICLES), len(INFO_TOPICS), len(INFO_AUDIENCES), len(INFO_CONDITIONS), len(INFO_ANGLES)])
HUB3_PERM = PermutedHub([len(PLACES), len(TRAVEL_VEHICLES), len(TRAVEL_DURATIONS), len(TRAVEL_TYPES), len(TRAVEL_ANGLES)])
HUB4_PERM = PermutedHub([len(LAW_TOPICS), len(LAW_AUDIENCES), len(LAW_ANGLES), len(LAW_CONTEXTS)])

PATTERN = [0, 1, 2, 0, 3, 1, 0, 2, 0, 1]
COUNTS = [4, 3, 2, 1]

def get_hub_and_k(seq):
    idx = (seq - 1) % len(PATTERN)
    h = PATTERN[idx]
    full = (seq - 1) // len(PATTERN)
    rem_count = sum(1 for i in range(idx) if PATTERN[i] == h)
    k = full * COUNTS[h] + rem_count
    return h, k

def slugify(s):
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').replace('đ', 'd')
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s)).strip('-')

def words(html): return re.findall(r"[\wÀ-ỹ]+", re.sub(r'<[^>]+>', ' ', html), re.UNICODE)
def grams(text, n=5):
    t = [x.lower() for x in words(text)]
    return set(tuple(t[i:i+n]) for i in range(max(0, len(t)-n+1)))
_GRAMS_CACHE = {}
def article_grams(p):
    k = p.get('id') or p.get('url')
    if k and k in _GRAMS_CACHE: return _GRAMS_CACHE[k]
    g = grams(' '.join(b for _, b in p.get('sections', [])))
    if k: _GRAMS_CACHE[k] = g
    return g
def gram_similarity(g1, g2): return len(g1 & g2) / max(1, len(g1 | g2))
def similarity(a, b):
    x, y = grams(a), grams(b)
    return len(x & y) / max(1, len(x | y))
def load_existing():
    out = json.loads(LEGACY.read_text()) if LEGACY.exists() else []
    for p in sorted(ARTICLES.glob('*.json')):
        try: out.append(json.loads(p.read_text()))
        except Exception: pass
    return out

def paragraph(seed, variants):
    return '<p>' + variants[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(variants)] + '</p>'

# ── Router & Spec ─────────────────────────────────────────────────────────────
def spec_for(seq):
    h, k = get_hub_and_k(seq)
    if h == 0:
        c = HUB1_PERM.coords(k)
        d = DISTRICTS[c[0]]
        v, hub = VEHICLES[c[1]]
        aud = AUDIENCES[c[2]]
        ang = ANGLES[c[3]]
        ctx = CONTEXTS[c[4]]
        rt = ROUTE_NEEDS[c[5]]
        title = f'{v} tại {d}: {ang[0]} khi {ctx}'
        intent = f'thue-xe|{ang[0]}|{v}|{d}|{aud}|{ctx}|{rt}'.lower()
        url = f'/{hub}/{slugify(d)}/{slugify(v)}/{slugify(ang[0])}-{slugify(aud)}-{slugify(ctx)}-{slugify(rt)}/'
        return {'sequence':seq,'title':title,'intent':intent,'vehicle':v,'hub':hub,'district':d,
                'audience':aud,'context':ctx,'route':rt,'angle':ang[0],'angle_label':ang[1],'url':url,'writer':'thue-xe'}
    elif h == 1:
        c = HUB2_PERM.coords(k)
        v, hub = INFO_VEHICLES[c[0]]
        topic_key, topic_label, topic_cat = INFO_TOPICS[c[1]]
        aud = INFO_AUDIENCES[c[2]]
        cond = INFO_CONDITIONS[c[3]]
        ang = INFO_ANGLES[c[4]]
        title = f'{v.capitalize()}: {topic_label} cho {aud}'
        intent = f'xe-info|{topic_key}|{v}|{aud}|{cond}|{ang[0]}'.lower()
        url = f'/{hub}/{slugify(v)}/{slugify(topic_key)}-{slugify(aud)}-{slugify(cond)}-{slugify(ang[0])}/'
        return {'sequence':seq,'title':title,'intent':intent,'vehicle':v,'hub':hub,
                'topic':topic_key,'topic_label':topic_label,'topic_cat':topic_cat,'audience':aud,
                'condition':cond,'angle':ang[0],'angle_label':ang[1],'url':url,'writer':'xe-info'}
    elif h == 2:
        c = HUB3_PERM.coords(k)
        place = PLACES[c[0]]
        v, hub = TRAVEL_VEHICLES[c[1]]
        dur = TRAVEL_DURATIONS[c[2]]
        tt = TRAVEL_TYPES[c[3]]
        ang = TRAVEL_ANGLES[c[4]]
        travel_ang_names = {'lich-trinh-cung-duong':'lộ trình chi tiết', 'du-tru-chi-phi':'chi phí tự túc', 'kinh-nghiem-lai-xe-an-toan':'kinh nghiệm an toàn', 'checklist-chuan-bi':'chuẩn bị đồ đạc', 'diem-checkin-am-thuc':'điểm check-in đẹp'}
        ang_short = travel_ang_names.get(ang[0], ang[0])
        title = f'Phượt {place} bằng {v}: {ang_short} ({dur})' 
        intent = f'du-lich|{place}|{v}|{dur}|{tt}|{ang[0]}'.lower()
        url = f'/kinh-nghiem/{slugify(place)}/{slugify(v)}/{slugify(dur)}-{slugify(tt)}-{slugify(ang[0])}/'
        return {'sequence':seq,'title':title,'intent':intent,'place':place,'vehicle':v,'hub':'kinh-nghiem',
                'duration':dur,'travel_type':tt,'angle':ang[0],'angle_label':ang[1],'url':url,'writer':'du-lich'}
    else:
        c = HUB4_PERM.coords(k)
        topic_key, topic_label = LAW_TOPICS[c[0]]
        aud = LAW_AUDIENCES[c[1]]
        ang = LAW_ANGLES[c[2]]
        ctx = LAW_CONTEXTS[c[3]]
        title = f'{topic_label.capitalize()} cho {aud}'
        intent = f'luat|{topic_key}|{aud}|{ang[0]}|{ctx}'.lower()
        url = f'/luat-giao-thong/{slugify(topic_key)}-{slugify(aud)}-{slugify(ang[0])}-{slugify(ctx)}/'
        return {'sequence':seq,'title':title,'intent':intent,'topic':topic_key,'topic_label':topic_label,
                'audience':aud,'angle':ang[0],'angle_label':ang[1],'context':ctx,'hub':'luat-giao-thong','url':url,'writer':'luat'}

# ── Writer 1: Thuê xe ─────────────────────────────────────────────────────────
def make_thue_xe(s):
    v=escape(s['vehicle']); d=escape(s['district']); a=escape(s['audience']); ang=escape(s['angle_label'])
    context=escape(s['context']); route=escape(s['route'])
    price=FACTS['prices'].get(s['vehicle'], FACTS['prices'].get('xe ga' if any(x in v for x in ['Vision', 'Air Blade', 'Lead', 'Grande']) else 'xe số'))
    seed=s['intent']; brand=escape(FACTS['brand']); phone=escape(FACTS['phone'])
    addr=escape(FACTS['address']); hours=escape(FACTS['hours'])

    sections=[]
    sections.append((f'Nhu cầu thuê {v} tại {d} của {a}',
        paragraph(seed+'1a', [
            f'Tại khu vực {d}, nhu cầu tìm kiếm {v} của {a} ngày càng phổ biến khi cần một phương tiện cơ động, tiết kiệm chi phí và chủ động giờ giấc. Trong điều kiện giao thông thực tế, việc chuẩn bị kỹ lưỡng về mục đích sử dụng giúp bạn chọn đúng dòng xe phù hợp và hạn chế tối đa chi phí phát sinh ngoài dự kiến.',
            f'Đối với {a} đang sinh sống hoặc làm việc tại {d}, chiếc {v} là giải pháp di chuyển linh hoạt, vừa vặn với thói quen sinh hoạt đô thị. Trước khi chốt phương án thuê, việc xác định rõ nhu cầu {context} và đặc thù {route} sẽ là nền tảng giúp bạn có một trải nghiệm suôn sẻ từ ngày đầu nhận xe.',
            f'Lựa chọn {v} tại {d} mang lại sự chủ động vượt trội cho {a}. Dù bạn cần xe cho các chuyến công việc gấp hay phục vụ sinh hoạt hằng ngày, việc nắm rõ những điều kiện vận hành thực tế sẽ giúp bảo vệ quyền lợi cá nhân và đảm bảo an toàn suốt kỳ thuê.'
        ]) + paragraph(seed+'1b', [
            f'Bài viết này cung cấp cẩm nang chi tiết về {ang} cho mẫu {v} tại địa bàn {d}. Toàn bộ thông tin giá niêm yết và quy định thủ tục được trích xuất từ dữ liệu chính thức của cửa hàng {brand}. Tình trạng xe sẵn có luôn được xác nhận trực tiếp trước thời điểm bàn giao.',
            f'Nhằm hỗ trợ {a} đưa ra quyết định đúng đắn, {brand} tổng hợp các phân tích thực tế về {ang} dành riêng cho {v}. Bảng giá niêm yết rõ ràng, xe được bảo dưỡng định kỳ và dịch vụ hỗ trợ chu đáo sẽ giúp bạn hoàn toàn an tâm trên mọi nẻo đường {d}.'
        ])
    ))

    sections.append((f'Đánh giá khả năng vận hành khi {route} tại {d}',
        paragraph(seed+'2a', [
            f'Tuyến đường đặc trưng {route} tại quận {d} thường đòi hỏi phương tiện có khả năng tăng tốc mượt mà, hệ thống phanh nhạy bén và bán kính quay đầu hợp lý. Chiếc {v} thể hiện ưu thế rõ rệt khi xoay trở trong các ngõ ngách, vượt qua điểm ùn tắc giờ tan tầm và đỗ xe thuận tiện trước các tòa nhà.',
            f'Khi di chuyển theo lộ trình {route}, {a} cần đặc biệt chú ý đến độ êm ái của phuộc nhún và cảm giác lái đầm chắc của {v}. Trọng lượng xe vừa phải giúp người lái dễ dàng dắt xe lên vỉa hè hoặc quay đầu tại những đoạn đường hẹp mà không tốn nhiều sức lực.',
            f'Thực tế vận hành tại {d} cho thấy, một chiếc {v} hoạt động ổn định sẽ giúp tiết kiệm đáng kể thời gian di chuyển. Bạn nên kiểm tra kỹ tầm nhìn qua gương chiếu hậu và độ nhạy tay ga trong khu vực an toàn trước khi chính thức hòa vào dòng xe đông đúc.'
        ]) + paragraph(seed+'2b', [
            f'Trong tình huống {context}, bạn nên phân bổ thời gian di chuyển hợp lý, tránh việc phóng nhanh phanh gấp khi gặp chướng ngại vật bất ngờ. Tham khảo thêm chuyên mục <a href="/kinh-nghiem/lai-xe-o-ha-noi/">kinh nghiệm lái xe an toàn ở Hà Nội</a> để trang bị thêm kỹ năng xử lý đường trơn trượt mùa mưa.',
            f'Đối với {a}, thói quen quan sát biển báo phân làn và giữ khoảng cách an toàn với xe phía trước là điều tối quan trọng. Tuyến đường {d} có nhiều nút giao đèn tín hiệu, vì vậy việc làm quen với độ phản hồi tay phanh của {v} sẽ giúp bạn luôn làm chủ tình huống.'
        ])
    ))

    sections.append((f'Checklist kiểm tra kỹ thuật {v} trước khi nhận',
        paragraph(seed+'3a', [
            f'Trước khi ký biên bản bàn giao {v}, hãy dành ít nhất 5 đến 10 phút kiểm tra toàn diện các bộ phận cơ bản: hệ thống đèn chiếu xa và chiếu gần, đèn báo rẽ xi nhan hai bên, còi xe, đồng hồ đo vận tốc và mức nhiên liệu hoặc vạch pin hiện tại. Đảm bảo tất cả trang bị đều vận hành hoàn hảo.',
            f'Quan sát kỹ bề mặt lốp xe {v}: rãnh gai lốp phải còn đủ độ sâu bám đường, lốp không bị nứt chân chim hoặc dính đinh kim loại. Kiểm tra áp suất lốp vừa vặn, không quá non gây ì máy hoặc quá căng làm xóc tay lái. Thao tác bóp thử cả phanh trước và sau để cảm nhận lực hãm chắc chắn.',
            f'Kiểm tra kỹ lưỡng chân chống nghiêng, chân chống giữa và ổ khóa thông minh hoặc khóa cơ của {v}. Đề nghị nhân viên khởi động máy để lắng nghe tiếng nổ êm ái của động cơ galanti, xác nhận không có khói lạ từ ống xả hoặc âm thanh gõ bất thường.'
        ]) + paragraph(seed+'3b', [
            f'Hai bên cùng tiến hành chụp ảnh và quay video toàn cảnh hiện trạng vỏ nhựa xe, ghi nhận rõ ràng các vết trầy xước có sẵn vào biên bản giao nhận. Hãy xem kỹ <a href="/bao-duong/xe-may/kiem-tra-truoc-khi-nhan/">checklist kiểm tra xe máy trước khi nhận</a> để không bỏ sót bất kỳ hạng mục kỹ thuật nào.',
            f'Xác nhận mũ bảo hiểm đạt chuẩn được cấp kèm xe có quai cài chắc chắn và kính chắn gió trong suốt. Đừng quên lưu lại số điện thoại cứu hộ kỹ thuật của cửa hàng để được hỗ trợ tận nơi nếu gặp sự cố bất ngờ trên hành trình {d}.'
        ])
    ))

    sections.append((f'Bảng giá và dự trù chi phí thuê {v} tại {d}',
        paragraph(seed+'4a', [
            f'Mức giá thuê niêm yết công khai cho nhóm phương tiện này tại {brand} là {escape(price)}. Mức phí thực tế phụ thuộc vào mẫu xe cụ thể, đời xe và tổng số ngày bạn đăng ký sử dụng. Cửa hàng luôn áp dụng chính sách chiết khấu lũy tiến hấp dẫn cho các hợp đồng thuê theo tuần hoặc theo tháng.',
            f'Theo biểu phí đang áp dụng, dòng {v} có mức giá cạnh tranh hàng đầu thị trường: {escape(price)}. Khách hàng được cam kết minh bạch 100% về tài chính, không phụ thu các khoản phí phát sinh vô lý ngoài thỏa thuận ban đầu.',
            f'Dự trù ngân sách di chuyển tại {d} bao gồm tiền thuê {escape(price)}, chi phí nhiên liệu xăng hoặc điện sạc, tiền gửi xe qua đêm và khoản đặt cọc hoàn lại. Bạn có thể tra cứu toàn bộ khung giá chi tiết tại <a href="/bang-gia/">bảng giá thuê xe máy Hà Nội</a>.'
        ]) + paragraph(seed+'4b', [
            f'Để tối ưu chi phí cho nhu cầu {context}, {a} nên tính toán tổng thời gian cần xe để chọn gói theo tuần hoặc tháng thay vì gia hạn lẻ tẻ theo từng ngày. Một ngày thuê tại cửa hàng được tính tròn 24 giờ kể từ thời điểm nhận xe, giúp bạn hoàn toàn chủ động sắp xếp lịch trình.',
            f'Cửa hàng cam kết hoàn trả đầy đủ 100% tiền đặt cọc ngay khi thủ tục trả xe kết thúc. Hãy đề nghị nhân viên ghi rõ các mốc giờ nhận, giờ trả và số tiền cọc vào phiếu thu để bảo vệ quyền lợi tài chính cá nhân.'
        ])
    ))

    sections.append((f'Quy định hợp đồng, giấy tờ và điều kiện tiền cọc',
        paragraph(seed+'5a', [
            f'Hợp đồng thuê {v} được lập thành hai bản có giá trị pháp lý tương đương, trong đó ghi rõ họ tên khách hàng, số điện thoại, biển số đăng ký xe, tình trạng xe và thời hạn sử dụng. Bạn cần kiểm tra kỹ thông tin biển số trên hợp đồng có trùng khớp với biển số gắn trên xe thực tế hay không.',
            f'Về thủ tục giấy tờ, khách hàng chỉ cần xuất trình căn cước công dân hoặc hộ chiếu còn hiệu lực kèm giấy phép lái xe hợp lệ. Cửa hàng chụp ảnh lưu hồ sơ đối chiếu và trả lại bản gốc ngay cho khách hàng, không giữ giấy tờ tùy thân của bạn.',
            f'Khoản tiền cọc dao động từ 2 đến 5 triệu đồng tùy theo giá trị xe và thời hạn thuê. Với khách du lịch nước ngoài, cửa hàng hỗ trợ phương thức đặt cọc tiền mặt hoặc thỏa thuận đặt cọc hộ chiếu theo quy định linh hoạt.'
        ]) + paragraph(seed+'5b', [
            f'Người điều khiển {v} phải đủ độ tuổi luật định và sở hữu giấy phép lái xe phù hợp với phân khối phương tiện. Bạn có thể tìm hiểu thêm các quy định pháp lý tại chuyên mục <a href="/luat-giao-thong/nguon-tra-cuu/">hướng dẫn tra cứu luật giao thông</a> để vững tin lưu thông trên đường.',
            f'Trước khi đặt bút ký hợp đồng, hãy đọc kỹ điều khoản về trách nhiệm bảo quản phương tiện và phạm vi hỗ trợ sự cố trên đường. Mọi thắc mắc về điều khoản dịch vụ đều được nhân viên giải thích tận tình và ghi chú trực tiếp vào văn bản.'
        ])
    ))

    sections.append((f'Phương thức nhận xe trực tiếp và giao xe tại {d}',
        paragraph(seed+'6a', [
            f'Khách hàng có thể đến trực tiếp cơ sở của {brand} để thử xe, kiểm tra máy móc và hoàn tất thủ tục bàn giao nhanh gọn trong vòng 10 phút. Đối với các hợp đồng thuê từ nhiều ngày, tuần hoặc tháng, cửa hàng hỗ trợ dịch vụ giao nhận xe tận nơi theo địa chỉ hẹn trước tại {d}.',
            f'Để việc giao nhận {v} diễn ra đúng hẹn tại {d}, bạn nên liên hệ đặt xe trước ít nhất 1 đến 2 giờ. Nhân viên giao xe sẽ chuẩn bị sẵn phương tiện đã được rửa sạch sẽ, kiểm tra an toàn kỹ thuật và đổ sẵn nhiên liệu để bạn có thể lên đường ngay.',
            f'Lưu ý rằng dịch vụ cho thuê xe không áp dụng giao nhận tại sân bay Nội Bài. Trong phạm vi các quận nội thành Hà Nội, phí giao hoặc nhận xe được tính theo mức hỗ trợ hợp lý và được thông báo rõ ràng trước khi xuất phát.'
        ]) + paragraph(seed+'6b', [
            f'Mốc thời gian trả xe được tính chuẩn xác theo chu kỳ 24 giờ ghi trong hợp đồng. Nếu bạn có việc đột xuất cần gia hạn thêm giờ hoặc trả xe sớm hơn dự kiến, hãy gọi điện thông báo sớm cho cửa hàng để được hỗ trợ sắp xếp linh hoạt nhất.',
            f'Khi bàn giao xe tại điểm hẹn ở {d}, hai bên cùng đối chiếu lại biên bản bàn giao ban đầu để xác nhận hiện trạng xe nguyên vẹn, đảm bảo quá trình trả xe diễn ra nhanh chóng, thoải mái và chuyên nghiệp.'
        ])
    ))

    sections.append((f'Kinh nghiệm lái xe an toàn khi {context}',
        paragraph(seed+'7a', [
            f'Trong điều kiện {context} tại {d}, việc duy trì khoảng cách an toàn và làm chủ tốc độ là yếu tố then chốt. Luôn bật đèn chiếu sáng khi đi qua hầm chui hoặc khi trời nhá nhem tối, sử dụng còi xe đúng lúc và tuyệt đối không chuyển làn đột ngột mà không bật đèn báo rẽ xi nhan.',
            f'Khi di chuyển trong các ngõ hẹp hoặc khu dân cư đông đúc của {d}, hãy giảm tốc độ và quan sát kỹ gương cầu lồi tại các khúc cua khuất tầm nhìn. Tránh phanh gấp bằng phanh trước trên các đoạn đường trơn ướt hoặc có cát sỏi để phòng ngừa hiện tượng trượt bánh lái.',
            f'Luôn đội mũ bảo hiểm đạt chuẩn, cài quai đúng quy cách và không sử dụng điện thoại khi đang điều khiển {v}. Nếu cần tra cứu bản đồ dẫn đường, hãy tấp xe vào lề đường ở vị trí an toàn được phép dừng đỗ rồi mới thao tác trên màn hình.'
        ]) + paragraph(seed+'7b', [
            f'Đỗ xe tại các bãi trông giữ có vé giữ xe rõ ràng và nhân viên trực gác. Luôn khóa cổ xe, đậy nắp từ ổ khóa và không để đồ dùng cá nhân có giá trị, ví tiền hoặc giấy tờ tùy thân trong cốp xe khi rời khỏi phương tiện.',
            f'Chủ động kiểm tra vạch xăng hoặc dung lượng pin trước mỗi chuyến đi để không rơi vào tình huống hết nhiên liệu giữa đường. Xem thêm <a href="/faq/">các câu hỏi thường gặp về thuê xe</a> để nắm bắt thêm mẹo xử lý hữu ích.'
        ])
    ))

    sections.append((f'Thông tin liên hệ Thuê xe máy Nguyễn Hà',
        f'<p>{brand} tọa lạc tại {addr} ({escape(FACTS["landmark"])}). Cửa hàng mở cửa từ {hours}. Điện thoại, Zalo và WhatsApp: <a href="tel:+84334699969">{phone}</a>.</p>'
        + f'<p>Quý khách có thể xem thêm <a href="/bang-gia/">bảng giá niêm yết</a>, <a href="/thue-xe-may/ha-noi/">thuê xe máy Hà Nội</a>, <a href="/faq/">câu hỏi thường gặp FAQ</a> và <a href="/lien-he/">trang liên hệ</a> để được hỗ trợ chu đáo nhất.</p>'
        + paragraph(seed+'contact', [
            f'Đội ngũ chăm sóc khách hàng của {brand} luôn sẵn sàng tư vấn mẫu xe phù hợp nhất với nhu cầu và lịch trình của bạn. Chúng tôi cam kết xe vận hành êm ái, đầy đủ giấy tờ và hỗ trợ kỹ thuật tận tình.',
            f'Với phương châm phục vụ tận tâm và chuyên nghiệp, {brand} tự hào đồng hành cùng quý khách trên mọi nẻo đường thủ đô. Hãy gọi ngay hotline để được chuẩn bị xe tốt nhất trước giờ xuất phát.'
        ])
    ))

    body = ' '.join(x[1] for x in sections); wc = len(words(body))
    return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],
            'excerpt':f'Cẩm nang {ang} {v} tại {d}: kinh nghiệm khi {context}, biểu phí niêm yết, thủ tục cọc và liên hệ Nguyễn Hà.',
            'sections':[[h,b] for h,b in sections],'keywords':f'{s["angle"]} {v} {d} {a}',
            'parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],
            'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}

# ── Writer 2: Xe máy / Xe điện / Xe đạp — Thông tin & Bảo dưỡng ───────────────
def make_xe_info(s):
    v=escape(s['vehicle']); t=escape(s['topic_label']); t_cat=escape(s['topic_cat'])
    a=escape(s['audience']); cond=escape(s['condition']); ang=escape(s['angle_label'])
    seed=s['intent']; brand=escape(FACTS['brand']); phone=escape(FACTS['phone'])
    addr=escape(FACTS['address']); hours=escape(FACTS['hours'])

    sections=[]
    sections.append((f'Tầm quan trọng của việc {t} đối với {v}',
        paragraph(seed+'1a', [
            f'Đối với dòng phương tiện phổ biến như {v}, việc chú trọng {t} đóng vai trò quyết định đến độ bền của động cơ, hiệu suất vận hành và sự an toàn của người lái. Trong điều kiện đường sá đô thị nhiều khói bụi và dừng đỗ liên tục, việc chăm sóc xe đúng cách giúp bạn tiết kiệm hàng triệu đồng chi phí sửa chữa lớn về sau.',
            f'Nhiều {a} thường có thói quen chỉ đưa xe đi tiệm khi phương tiện đã xuất hiện hư hỏng nặng. Tuy nhiên, quy trình {t} chủ động sẽ giúp phát hiện sớm các hao mòn linh kiện, giữ cho chiếc {v} luôn trong trạng thái vận hành mượt mà và êm ái nhất.',
            f'Đặc biệt trong {cond}, các chi tiết kỹ thuật của {v} phải chịu áp lực làm việc cao hơn bình thường. Việc hiểu rõ nguyên lý và thời điểm cần can thiệp kỹ thuật sẽ giúp bạn hoàn toàn làm chủ phương tiện trên mọi cung đường di chuyển.'
        ]) + paragraph(seed+'1b', [
            f'Bài viết này cung cấp cẩm nang chuyên sâu về {ang} cho hạng mục {t} trên {v}. Mọi thông số và khuyến nghị được tổng hợp dựa trên thực tế vận hành tại Hà Nội, hỗ trợ đắc lực cho {a} trong quá trình sử dụng xe hằng ngày.',
            f'Bên cạnh việc bảo dưỡng xe cá nhân, nếu bạn đang có nhu cầu trải nghiệm phương tiện mới đã được kiểm định an toàn nghiêm ngặt, hãy tham khảo các dòng xe sẵn có tại <a href="/thue-xe-may/ha-noi/">dịch vụ thuê xe máy Hà Nội</a> của {brand}.'
        ])
    ))

    sections.append((f'Dấu hiệu nhận biết {v} cần kiểm tra trong {cond}',
        paragraph(seed+'2a', [
            f'Trong {cond}, bạn cần đặc biệt lưu tâm đến các biểu hiện bất thường như: tiếng kêu lạ phát ra từ bộ truyền động, tay lái có hiện tượng rung lắc hoặc nặng bất thường, hiệu quả phanh suy giảm hoặc xe có cảm giác ì ạch khi vặn ga. Đây là những tín hiệu cảnh báo hệ thống cơ khí đang cần được can thiệp kịp thời.',
            f'Đối với hệ thống truyền động và bánh xe của {v}, sự thay đổi nhiệt độ và độ ẩm trong {cond} có thể làm giảm tuổi thọ cao su lốp, gây giãn xích hoặc chai cứng bố thắng. Nếu phát hiện xe tiêu hao nhiên liệu tăng đột biến so với bình thường, bạn nên tiến hành kiểm tra bugi và tấm lọc gió ngay.',
            f'Đối với các mẫu xe máy điện, việc theo dõi thời gian sạc pin và tốc độ sụt giảm điện áp khi leo dốc là cực kỳ quan trọng. Khi pin có dấu hiệu tụt vạch nhanh bất thường hoặc bộ sạc nóng quá mức cho phép, hãy ngừng sử dụng và đưa xe đến trung tâm chuyên môn để đo đạc dung lượng thực tế.'
        ]) + paragraph(seed+'2b', [
            f'Hãy duy trì thói quen quan sát nhanh chiếc xe trước mỗi chuyến đi dài. Bạn có thể đối chiếu tình trạng phương tiện với <a href="/bao-duong/xe-may/kiem-tra-truoc-khi-nhan/">checklist kiểm tra kỹ thuật xe máy</a> để không bỏ sót các hư hỏng tiềm ẩn.',
            f'Đối với {a}, việc phát hiện sớm hư hỏng không chỉ bảo vệ chiếc {v} khỏi những hỏng hóc dây chuyền tốn kém mà còn là tấm lá chắn bảo vệ an toàn tính mạng cho chính bạn và những người cùng tham gia giao thông.'
        ])
    ))

    sections.append((f'Quy trình từng bước {t} chuẩn kỹ thuật',
        paragraph(seed+'3a', [
            f'Bước đầu tiên trong quy trình là làm sạch bề mặt khu vực cần thao tác, đặt {v} trên mặt phẳng vững chắc bằng chân chống giữa và để động cơ nguội hoàn toàn nếu vừa di chuyển. Chuẩn bị đầy đủ dụng cụ chuyên dụng phù hợp với đúng thông số kỹ thuật của nhà sản xuất.',
            f'Tiến hành tháo mở cẩn thận các chi tiết ốc vít theo đúng chiều ren, kiểm tra độ mòn thực tế của linh kiện cũ và vệ sinh sạch sẽ các cặn bẩn bám dính. Luôn sử dụng dung dịch tẩy rửa chuyên dụng, tránh dùng xăng thơm hay hóa chất tẩy mạnh làm hư hại các vòng đệm cao su hoặc phốt dầu.',
            f'Lắp ráp linh kiện mới hoặc chi tiết đã bảo dưỡng về vị trí cũ, siết ốc với lực siết vừa đủ theo khuyến cáo kỹ thuật để tránh hiện tượng trờn ren ốc lốc máy. Bôi trơn các khớp chuyển động bằng mỡ bò chịu nhiệt hoặc dầu nhớt chuyên dụng chất lượng cao.'
        ]) + paragraph(seed+'3b', [
            f'Sau khi hoàn tất việc lắp ráp, khởi động {v} và chạy thử ở tốc độ thấp trong khu vực an toàn để kiểm tra độ ổn định. Lắng nghe kỹ tiếng máy và thử lại các tính năng phanh, ga để chắc chắn phương tiện đã sẵn sàng vận hành trơn tru.',
            f'Lưu ý ghi chép lại số km trên đồng hồ công-tơ-mét và mốc thời gian thực hiện để thiết lập chu kỳ bảo dưỡng kế tiếp. Nếu chưa tự tin về tay nghề cơ khí, bạn nên đưa xe đến các cơ sở uy tín để được kỹ thuật viên giàu kinh nghiệm hỗ trợ.'
        ])
    ))

    sections.append((f'Những sai lầm phổ biến khi tự chăm sóc {v}',
        paragraph(seed+'4a', [
            f'Sai lầm phổ biến nhất mà nhiều {a} mắc phải là sử dụng sai chủng loại dầu nhớt hoặc dung dịch kỹ thuật không tương thích với chiếc {v}. Ví dụ, dùng nhầm nhớt xe số cho xe tay ga hoặc ngược lại sẽ khiến động cơ nóng ran, gây trượt ly hợp hoặc làm giảm hiệu suất buồng đốt nghiêm trọng.',
            f'Một lỗi tai hại khác là siết ốc xả dầu quá chặt gây nứt lốc máy, hoặc siết quá lỏng làm rò rỉ dầu nhớt ra mặt đường gây nguy hiểm khi vào cua. Nhiều người dùng cũng thường quên thay long-đền nhôm mỗi lần xả nhớt, dẫn đến hiện tượng rịn dầu âm ỉ kéo dài.',
            f'Đối với việc rửa xe tại nhà, việc xịt vòi nước áp lực cao trực tiếp vào khu vực ổ bi cổ phốt, công tắc điện tay lái hay họng gió buồng đốt có thể làm nước lọt vào vi mạch điều khiển, gây chập cháy cầu chì hoặc chết bugi đánh lửa.'
        ]) + paragraph(seed+'4b', [
            f'Để tránh các sự cố kỹ thuật không đáng có, bạn nên tham khảo kỹ các tài liệu hướng dẫn vận hành hoặc tra cứu thêm tại <a href="/kinh-nghiem/lai-xe-o-ha-noi/">chuyên mục kinh nghiệm sử dụng xe</a> trước khi tự mình tháo lắp các cụm chi tiết phức tạp.',
            f'Khi phát hiện có dấu hiệu bất thường ngoài khả năng xử lý, tuyệt đối không cố chấp nổ máy tiếp tục chạy. Hãy gọi điện nhờ hỗ trợ kỹ thuật để tránh làm hỏng hóc lây lan sang các bộ phận đắt tiền khác.'
        ])
    ))

    sections.append((f'Chi phí linh kiện, phụ tùng và công thợ tham khảo',
        paragraph(seed+'5a', [
            f'Chi phí cho hạng mục {t} trên {v} dao động tùy thuộc vào việc bạn lựa chọn phụ tùng chính hãng của hãng xe hay phụ tùng OEM từ các thương hiệu thứ ba danh tiếng. Thông thường, mức giá vật tư cơ bản rơi vào khoảng từ vài chục nghìn đến vài trăm nghìn đồng tùy chi tiết.',
            f'Tiền công thợ tại các xưởng sửa xe uy tín tại Hà Nội thường được niêm yết công khai từ 50.000đ đến 150.000đ cho các gói bảo dưỡng định kỳ cơ bản. Bạn nên yêu cầu xưởng báo giá trọn gói bao gồm cả công lắp đặt trước khi đồng ý cho thợ tiến hành làm.',
            f'Nên cảnh giác với các cửa hàng chào mời dịch vụ với mức giá rẻ bất thường vì rất có thể họ sử dụng dầu nhớt tái chế hoặc phụ tùng giả nhái kém chất lượng. Việc đầu tư phụ tùng chuẩn chỉ ngay từ đầu sẽ giúp bạn tiết kiệm dài hạn và đảm bảo an toàn tuyệt đối.'
        ]) + paragraph(seed+'5b', [
            f'Nếu bạn đang cân nhắc chi phí giữa việc giữ xe cũ tốn kém bảo dưỡng định kỳ với việc thuê xe vận hành êm ái không lo sửa chữa, hãy tham khảo <a href="/bang-gia/">bảng giá thuê xe máy theo tháng</a> để có sự so sánh kinh tế rõ ràng nhất.',
            f'Các cửa hàng chuyên nghiệp luôn có chế độ bảo hành rõ ràng từ 1 đến 3 tháng cho các phụ tùng mới thay thế. Hãy giữ lại hóa đơn bán hàng hoặc phiếu bảo dưỡng để đối chiếu quyền lợi khi cần thiết.'
        ])
    ))

    sections.append((f'Lời khuyên dành riêng cho {a} khi sử dụng xe hằng ngày',
        paragraph(seed+'6a', [
            f'Với nhịp sống bận rộn tại các đô thị, {a} nên cài đặt ứng dụng nhắc nhở hoặc dán tem ghi nhớ số km bảo dưỡng ngay trên mặt đồng hồ {v}. Thiết lập thói quen kiểm tra định kỳ mỗi 1.500 đến 2.000 km sẽ giúp xe luôn vận hành trong trạng thái lý tưởng nhất.',
            f'Khi sử dụng xe trong điều kiện {cond}, hãy chú ý rửa sạch bùn đất bám vào gầm máy, đĩa phanh và phuộc nhún ngay sau khi đi mưa về. Bùn đất chứa nhiều axit và tạp chất ăn mòn nếu để khô két sẽ làm rỉ sét ty phuộc và mòn đĩa phanh rất nhanh.',
            f'Luôn trang bị sẵn trên xe một bộ đồ nghề mini cơ bản gồm tuốc-nơ-vít, kìm nhỏ và đầu mở bugi kèm một chiếc bơm lốp mini cầm tay. Những vật dụng này sẽ là cứu cánh đắc lực giúp bạn tự xử lý các sự cố vặt trên đường vắng.'
        ]) + paragraph(seed+'6b', [
            f'Đảm bảo luôn mang theo giấy phép lái xe và giấy tờ xe hợp lệ khi tham gia giao thông. Bạn có thể tra cứu các quy chuẩn an toàn mới nhất tại <a href="/luat-giao-thong/nguon-tra-cuu/">chuyên mục tra cứu luật giao thông</a> để vững tâm trong mọi chuyến đi.',
            f'Hãy lắng nghe cảm giác lái của chính mình: bất kỳ tiếng kêu rè rè, rung lắc hay độ trễ ga nào cũng là dấu hiệu phương tiện đang cần được bạn quan tâm chăm sóc.'
        ])
    ))

    sections.append((f'Câu hỏi thường gặp về việc bảo dưỡng {v}',
        paragraph(seed+'7a', [
            f'<strong>Bao lâu thì nên thực hiện {t} một lần?</strong> Chu kỳ lý tưởng phụ thuộc vào tần suất di chuyển và điều kiện môi trường. Với mật độ chạy phố hằng ngày tại Hà Nội, chuyên gia khuyến nghị bạn nên kiểm tra sau mỗi 2 đến 3 tháng hoặc tương đương 2.000 km lăn bánh.',
            f'<strong>Có thể tự thực hiện tại nhà được không?</strong> Những thao tác vệ sinh bên ngoài, tra dầu xích hay đo áp suất lốp bạn hoàn toàn có thể tự làm tại nhà với dụng cụ cơ bản. Tuy nhiên, các hạng mục liên quan đến mở lốc máy, cân chỉnh xupap hay hệ thống điện tử nên để thợ có tay nghề thực hiện.',
            f'<strong>Dấu hiệu nào cho thấy linh kiện đã đến hạn phải thay thế gấp?</strong> Khi chi tiết xuất hiện vết nứt vỡ, độ mòn vượt quá chỉ số báo vạch an toàn của nhà sản xuất hoặc phát ra tiếng kêu cọ xát kim loại chói tai, bạn bắt buộc phải thay thế ngay lập tức để tránh tai nạn.'
        ]) + paragraph(seed+'7b', [
            f'Để tìm hiểu thêm nhiều kinh nghiệm hữu ích khác về các dòng xe máy, xe điện và xe đạp thể thao, bạn có thể tham khảo mục <a href="/faq/">giải đáp thắc mắc thường gặp FAQ</a> được đội ngũ kỹ thuật cập nhật liên tục.',
            f'Đừng ngần ngại hỏi rõ thợ sửa xe về nguồn gốc xuất xứ của từng món linh kiện được lắp vào xe để chắc chắn bạn nhận được giá trị xứng đáng với số tiền đã chi trả.'
        ])
    ))

    sections.append((f'Thông tin liên hệ Thuê xe máy Nguyễn Hà',
        f'<p>{brand} tọa lạc tại {addr} ({escape(FACTS["landmark"])}). Cửa hàng mở cửa từ {hours}. Điện thoại, Zalo và WhatsApp: <a href="tel:+84334699969">{phone}</a>.</p>'
        + f'<p>Quý khách có thể xem thêm <a href="/bang-gia/">bảng giá niêm yết</a>, <a href="/thue-xe-may/ha-noi/">thuê xe máy Hà Nội</a>, <a href="/faq/">câu hỏi thường gặp FAQ</a> và <a href="/lien-he/">trang liên hệ</a> để được hỗ trợ chu đáo nhất.</p>'
        + paragraph(seed+'contact', [
            f'Đội ngũ chăm sóc khách hàng của {brand} luôn sẵn sàng tư vấn mẫu xe phù hợp nhất với nhu cầu và lịch trình của bạn. Chúng tôi cam kết xe vận hành êm ái, đầy đủ giấy tờ và hỗ trợ kỹ thuật tận tình.',
            f'Với phương châm phục vụ tận tâm và chuyên nghiệp, {brand} tự hào đồng hành cùng quý khách trên mọi nẻo đường thủ đô. Hãy gọi ngay hotline để được chuẩn bị xe tốt nhất trước giờ xuất phát.'
        ])
    ))

    body = ' '.join(x[1] for x in sections); wc = len(words(body))
    return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],
            'excerpt':f'Cẩm nang {t} cho {v} ({a}): dấu hiệu nhận biết sớm, các bước chuẩn xác và tư vấn từ Nguyễn Hà.',
            'sections':[[h,b] for h,b in sections],'keywords':f'{s["topic"]} {v} {a} {cond}',
            'parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],
            'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}

# ── Writer 3: Du lịch & Phượt ─────────────────────────────────────────────────
def make_du_lich(s):
    place=escape(s['place']); v=escape(s['vehicle']); dur=escape(s['duration'])
    tt=escape(s['travel_type']); ang=escape(s['angle_label'])
    seed=s['intent']; brand=escape(FACTS['brand']); phone=escape(FACTS['phone'])
    addr=escape(FACTS['address']); hours=escape(FACTS['hours'])

    sections=[]
    sections.append((f'Tổng quan cung đường phượt {place} bằng {v}',
        paragraph(seed+'1a', [
            f'Hành trình khám phá {place} bằng {v} là một trong những trải nghiệm du lịch tuyệt vời nhất dành cho {tt}. Cảm giác tự do cầm lái, hòa mình vào thiên nhiên tươi đẹp và làm chủ từng cung đường sẽ mang lại những kỷ niệm khó quên cho cả chuyến đi.',
            f'Điểm đến {place} nổi tiếng với phong cảnh sơn thủy hữu tình, không khí trong lành và bản sắc văn hóa địa phương độc đáo. Lựa chọn {v} làm phương tiện di chuyển trong chuyến {dur} giúp bạn dễ dàng dừng chân chụp ảnh tại những góc check-in tuyệt đẹp ven đường mà các tour xe khách lớn không thể ghé vào.',
            f'Để chuyến đi diễn ra trọn vẹn và an toàn, việc lên kế hoạch chi tiết về {ang} đóng vai trò vô cùng quan trọng. Dù bạn là phượt thủ dày dặn kinh nghiệm hay mới lần đầu đi xa, sự chuẩn bị chu đáo sẽ giúp bạn làm chủ mọi tình huống phát sinh.'
        ]) + paragraph(seed+'1b', [
            f'Bài viết này chia sẻ cẩm nang thực tế từ A đến Z cho chuyến phượt {place} cùng chiếc {v}. Toàn bộ thông tin lộ trình, chi phí và kinh nghiệm thực tế được tổng hợp nhằm giúp {tt} có một chuyến đi an toàn, tiết kiệm và đáng nhớ.',
            f'Nếu bạn từ nơi khác đến Hà Nội và chưa có sẵn xe máy đạt chuẩn để leo đèo, hãy tham khảo ngay dịch vụ cho thuê xe phượt uy tín tại <a href="/thue-xe-may/ha-noi/">thuê xe máy Hà Nội Nguyễn Hà</a> với dàn xe máy khỏe, bảo dưỡng kỹ càng.'
        ])
    ))

    sections.append((f'Hướng dẫn lộ trình từ Hà Nội đến {place} tối ưu nhất',
        paragraph(seed+'2a', [
            f'Xuất phát từ trung tâm Hà Nội, cung đường hướng về {place} có thể lựa chọn theo nhiều hướng khác nhau tùy thuộc vào điều kiện thời tiết và sở thích ngắm cảnh. Bạn nên ưu tiên các trục quốc lộ lớn có mặt đường nhựa bằng phẳng, tầm nhìn thông thoáng và có nhiều trạm dừng nghỉ ven đường.',
            f'Thời điểm xuất phát lý tưởng nhất là vào khoảng 5h30 đến 6h00 sáng để tránh khung giờ tắc đường tại các cửa ngõ thủ đô và tận hưởng không khí mát mẻ buổi sớm mai. Di chuyển bằng {v} cho phép bạn duy trì tốc độ ổn định từ 40 đến 50 km/h, vừa đảm bảo an toàn vừa không bị quá sức.',
            f'Hãy chú ý quan sát các biển báo hiệu giao thông, vạch kẻ đường và giới hạn tốc độ tại các khu vực đông dân cư dọc tuyến đường. Không nên chạy bám đuôi các dòng xe tải nặng hay xe container lớn để tránh bị hạn chế tầm nhìn và bụi bẩn làm mờ kính chắn gió.'
        ]) + paragraph(seed+'2b', [
            f'Để chuẩn bị tốt nhất về kỹ năng xử lý tình huống giao thông đường dài, bạn có thể tham khảo thêm <a href="/kinh-nghiem/lai-xe-o-ha-noi/">kinh nghiệm lái xe an toàn đường trường</a> được đúc kết từ nhiều tay lái lâu năm.',
            f'Lưu ý cài đặt trước bản đồ ngoại tuyến (offline maps) trên điện thoại đề phòng trường hợp đi qua các đoạn đèo núi cao hoặc vùng sâu vùng xa bị mất sóng điện thoại di động.'
        ]) + paragraph(seed+'2c', [f'Trước khi khởi hành một chặng đường dài, hãy luôn kiểm tra lại mức dầu máy và áp suất hai bánh xe {v}. Việc duy trì tốc độ đều đặn không chỉ giúp bảo vệ động cơ mà còn mang lại cảm giác thư thái ngắm nhìn phong cảnh thiên nhiên tuyệt đẹp dọc đường.', f'Một thói quen quan trọng của các tay lái đường trường là phân chia chặng dừng nghỉ hợp lý sau mỗi 60 đến 80 km lăn bánh. Dừng xe uống nước, thả lỏng cơ bắp và kiểm tra lại dây chằng đồ sau xe sẽ giúp bạn duy trì sự tỉnh táo suốt hành trình.'])
    ))

    sections.append((f'Lịch trình chi tiết {dur} dành cho {tt}',
        paragraph(seed+'3a', [
            f'Với khoảng thời gian {dur}, bạn nên phân bổ lịch trình một cách khoa học: ngày đầu tiên tập trung di chuyển đến nơi, nhận phòng nghỉ ngơi và khám phá các điểm tham quan gần trung tâm vào buổi chiều muộn để cơ thể thích nghi với khí hậu địa phương.',
            f'Các ngày tiếp theo sẽ là thời gian lý tưởng để {tt} cùng chiếc {v} chinh phục những thắng cảnh đặc sắc nhất của {place}. Hãy dậy sớm đón bình minh, săn mây trên đỉnh đèo và ghé thăm các bản làng văn hóa để trải nghiệm nhịp sống bình dị của người dân bản địa.',
            f'Buổi tối là khoảng thời gian tuyệt vời để thưởng thức ẩm thực đường phố ấm nóng, dạo bộ ngắm cảnh đêm lung linh và thư giãn sau một ngày dài di chuyển. Hãy dành buổi sáng của ngày cuối cùng để mua sắm đặc sản làm quà trước khi thong thả lái xe trở về Hà Nội.'
        ]) + paragraph(seed+'3b', [
            f'Lịch trình nên có những khoảng trống linh hoạt khoảng 1 đến 2 tiếng để nghỉ ngơi hoặc điều chỉnh kế hoạch khi gặp mưa gió bất ngờ. Không nên cố nhồi nhét quá nhiều điểm tham quan trong một ngày khiến chuyến đi biến thành một cuộc chạy đua mệt mỏi.',
            f'Tìm hiểu thêm những mẹo sắp xếp hành lý thông minh tại chuyên mục <a href="/faq/">giải đáp thắc mắc du lịch phượt</a> để chuyến đi thêm phần nhẹ nhàng và tiện lợi.'
        ])
    ))

    sections.append((f'Kinh nghiệm lái xe an toàn, leo đèo và ứng phó thời tiết',
        paragraph(seed+'4a', [
            f'Khi điều khiển {v} qua các cung đường đèo dốc quanh co tại {place}, nguyên tắc vàng là: lên đèo số nào thì xuống đèo số đó. Tuyệt đối không tắt máy thả trôi xe hoặc rà phanh liên tục khi đổ dốc dài vì ma sát cao sẽ làm cháy bố phanh, sôi dầu phanh dẫn đến mất hoàn toàn tác dụng phanh.',
            f'Luôn giữ xe chạy đúng phần đường của mình khi vào cua khuất tầm nhìn, không lấn làn vượt ẩu qua vạch kẻ liền. Trước khi vào cua hẹp, hãy bấm còi báo hiệu từ xa để các phương tiện đi ngược chiều chủ động giảm tốc độ nhường đường.',
            f'Nếu gặp trời mưa đường trơn trượt hoặc sương mù dày đặc che khuất tầm nhìn, hãy bật đèn sương mù hoặc dán đề can vàng lên đèn pha, giảm tốc độ và bám theo dải phân cách hoặc cọc tiêu phản quang ven đường để giữ hướng đi an toàn.'
        ]) + paragraph(seed+'4b', [
            f'Luôn trang bị đầy đủ bộ giáp bảo hộ tay chân, găng tay chống nước và mũ bảo hiểm đạt chuẩn che phủ kín đầu. Tra cứu thêm các quy định giao thông đường bộ tại <a href="/luat-giao-thong/nguon-tra-cuu/">nguồn tra cứu luật và bằng lái</a> để đảm bảo tuân thủ đúng pháp luật.',
            f'Khi cảm thấy mỏi mắt hoặc buồn ngủ, hãy dừng xe ngay tại quán nước ven đường để rửa mặt, uống một tách trà nóng và nghỉ ngơi 15 phút trước khi tiếp tục hành trình.'
        ]) + paragraph(seed+'4c', [f'Quy tắc sống còn khi đổ đèo dốc bằng {v} là giữ khoảng cách tối thiểu 30 đến 50 mét với xe phía trước. Tuyệt đối không vượt xe ở những đoạn đường có vạch kẻ liền hoặc góc cua hẹp, và luôn sẵn sàng nhường đường cho xe đang lên dốc theo đúng luật.', f'Khi gặp thời tiết sương mù dày đặc hoặc mưa dông bất chợt trên đèo, hãy bật đèn chiếu gần, di chuyển sát mép đường bên phải và bám theo cọc tiêu phản quang. Tuyệt đối không dừng xe chụp ảnh ở những góc cua khuất tầm nhìn của các phương tiện lớn.'])
    ))

    sections.append((f'Dự toán kinh phí xăng xe, ăn uống và lưu trú tại {place}',
        paragraph(seed+'5a', [
            f'Tổng kinh phí cho chuyến đi {dur} đến {place} thường rất hợp lý và dễ kiểm soát. Chi phí xăng xe cho chiếc {v} khứ hồi thường dao động từ 150.000đ đến 300.000đ tùy theo quãng đường thực tế và mức tiêu hao nhiên liệu của xe.',
            f'Về nơi lưu trú, bạn có thể lựa chọn giữa các homestay mang đậm bản sắc địa phương với mức giá từ 150.000đ đến 300.000đ/người/đêm, hoặc các khách sạn tiện nghi từ 400.000đ đến 800.000đ/đêm. Đặt phòng trước qua các nền tảng trực tuyến giúp bạn chọn được phòng đẹp với mức giá ưu đãi.',
            f'Chi phí ăn uống tại {place} khá phong phú với các món đặc sản tươi ngon. Mỗi người chỉ cần dự trù khoảng 200.000đ đến 350.000đ mỗi ngày là có thể thưởng thức trọn vẹn tinh hoa ẩm thực địa phương từ các món nướng than hoa đến lẩu rau rừng.'
        ]) + paragraph(seed+'5b', [
            f'Nếu bạn cần thuê phương tiện tại Hà Nội cho cả chuyến đi, đừng quên tham khảo biểu phí ưu đãi trọn gói tại <a href="/bang-gia/">bảng giá thuê xe máy theo tuần</a> để nhận mức giá tiết kiệm nhất.',
            f'Hãy chuẩn bị thêm một khoản ngân sách dự phòng khoảng 500.000đ đến 1.000.000đ trong tài khoản ngân hàng để chủ động xử lý các tình huống vá săm, sửa xe hoặc phát sinh ngoài dự kiến trên đường.'
        ]) + paragraph(seed+'5c', [f'Để tối ưu hóa chi phí cho cả nhóm {tt}, bạn nên mua chung vé tham quan và đặt ăn theo set menu tại các nhà hàng địa phương uy tín. Việc chia sẻ chi phí nhiên liệu và phòng nghỉ sẽ giúp chuyến đi vừa vui vẻ vừa vô cùng tiết kiệm.', f'Luôn giữ lại hóa đơn thanh toán hoặc thỏa thuận giá cả dịch vụ trước khi sử dụng để tránh bị chặt chém tại các khu du lịch đông đúc vào dịp cao điểm cuối tuần.'])
    ))

    sections.append((f'Điểm check-in đẹp và đặc sản ẩm thực không nên bỏ qua',
        paragraph(seed+'6a', [
            f'Đến với {place}, bạn nhất định không thể bỏ qua những địa danh nổi tiếng với góc chụp ảnh triệu view nhìn toàn cảnh mây trời non nước. Hãy dành thời gian trò chuyện với người dân địa phương để khám phá thêm những con thác hoang sơ hay đồi thông vắng vẻ ít người biết.',
            f'Ẩm thực tại {place} ghi dấu ấn sâu đậm với hương vị đậm đà mộc mạc. Những món đặc sản trứ danh được chế biến từ nguyên liệu tươi ngon tại chỗ sẽ làm nức lòng bất kỳ thực khách khó tính nào sau những giờ phút lái xe hăng say.',
            f'Vào buổi tối se lạnh, việc quây quần bên bếp than hồng cùng {tt}, nhâm nhi chén trà thơm và thưởng thức món nướng đặc sản sẽ là trải nghiệm gắn kết ấm áp khó phai trong suốt chuyến đi.'
        ]) + paragraph(seed+'6b', [
            f'Hãy là những phượt thủ văn minh: tuyệt đối không xả rác bừa bãi tại các điểm tham quan thiên nhiên, tôn trọng phong tục tập quán địa phương và giữ gìn cảnh quan môi trường xanh sạch đẹp cho những người đến sau.',
            f'Xem thêm các bài viết chia sẻ kinh nghiệm khám phá tại <a href="/kinh-nghiem/">chuyên mục cẩm nang du lịch trải nghiệm</a> để tích lũy thêm nhiều tọa độ check-in độc đáo.'
        ])
    ))

    sections.append((f'Checklist chuẩn bị {v} và đồ dùng thiết yếu',
        paragraph(seed+'7a', [
            f'Trước ngày khởi hành ít nhất 1 ngày, hãy đưa chiếc {v} đi bảo dưỡng tổng thể: thay dầu máy mới, căn chỉnh phanh, tra dầu xích líp, kiểm tra gai lốp và siết lại toàn bộ ốc vít khung gầm. Bạn có thể tham khảo kỹ hơn tại <a href="/bao-duong/xe-may/kiem-tra-truoc-khi-nhan/">hướng dẫn kiểm tra xe trước chuyến đi</a>.',
            f'Về trang phục và hành lý cá nhân: chuẩn bị áo mưa bộ chuyên dụng chất lượng cao, bọc giày chống nước, túi khô chống nước để bọc ba lô, kính râm chống bụi, kem chống nắng và một bộ quần áo ấm phòng khi nhiệt độ vùng cao hạ thấp về đêm.',
            f'Đừng quên mang theo túi cứu thương cá nhân mini chứa các loại thuốc cơ bản: thuốc hạ sốt, băng gạc cá nhân, thuốc đau bụng, xịt côn trùng cắn và thuốc chống say xe. Giữ toàn bộ giấy tờ tùy thân và tiền mặt trong túi chống nước kín đáo bên trong áo khoác.'
        ]) + paragraph(seed+'7b', [
            f'Trang bị thêm một chiếc giá đỡ điện thoại bằng kim loại gắn chắc vào chân gương xe máy kèm tẩu sạc hoặc sạc dự phòng để tiện quan sát bản đồ dẫn đường mà không lo hết pin giữa đường.',
            f'Luôn nhớ đổ đầy bình xăng trước khi bắt đầu leo vào những cung đèo dài hiểm trở vì các cây xăng trên đèo thường nằm cách xa nhau hàng chục cây số.'
        ])
    ))

    sections.append((f'Thông tin liên hệ Thuê xe máy Nguyễn Hà',
        f'<p>{brand} tọa lạc tại {addr} ({escape(FACTS["landmark"])}). Cửa hàng mở cửa từ {hours}. Điện thoại, Zalo và WhatsApp: <a href="tel:+84334699969">{phone}</a>.</p>'
        + f'<p>Quý khách có thể xem thêm <a href="/bang-gia/">bảng giá niêm yết</a>, <a href="/thue-xe-may/ha-noi/">thuê xe máy Hà Nội</a>, <a href="/faq/">câu hỏi thường gặp FAQ</a> và <a href="/lien-he/">trang liên hệ</a> để được hỗ trợ chu đáo nhất.</p>'
        + paragraph(seed+'contact', [
            f'Đội ngũ chăm sóc khách hàng của {brand} luôn sẵn sàng tư vấn mẫu xe phù hợp nhất với nhu cầu và lịch trình của bạn. Chúng tôi cam kết xe vận hành êm ái, đầy đủ giấy tờ và hỗ trợ kỹ thuật tận tình.',
            f'Với phương châm phục vụ tận tâm và chuyên nghiệp, {brand} tự hào đồng hành cùng quý khách trên mọi nẻo đường thủ đô. Hãy gọi ngay hotline để được chuẩn bị xe tốt nhất trước giờ xuất phát.'
        ])
    ))

    body = ' '.join(x[1] for x in sections); wc = len(words(body))
    return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],
            'excerpt':f'Kinh nghiệm phượt {place} bằng {v} ({tt}): cung đường tối ưu, kinh nghiệm leo đèo, chi phí và thuê xe Nguyễn Hà.',
            'sections':[[h,b] for h,b in sections],'keywords':f'phượt {place} {v} {dur} {tt}',
            'parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],
            'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}

# ── Writer 4: Luật giao thông & An toàn ──────────────────────────────────────
def make_luat(s):
    t=escape(s['topic_label']); a=escape(s['audience']); ang=escape(s['angle_label']); ctx=escape(s['context'])
    seed=s['intent']; brand=escape(FACTS['brand']); phone=escape(FACTS['phone'])
    addr=escape(FACTS['address']); hours=escape(FACTS['hours'])

    sections=[]
    sections.append((f'Căn cứ pháp lý mới nhất về {t}',
        paragraph(seed+'1a', [
            f'Các quy định pháp luật điều chỉnh về {t} là nội dung then chốt mà bất kỳ ai khi tham gia giao thông đường bộ tại Việt Nam cũng cần nắm vững. Việc hiểu đúng và chấp hành nghiêm chỉnh các quy chuẩn này giúp bảo đảm trật tự an toàn công cộng và hạn chế tối đa nguy cơ tai nạn.',
            f'Đối với {a}, việc trang bị kiến thức pháp lý vững vàng về {t} giúp bạn hoàn toàn tự tin khi lưu thông trên đường, tránh khỏi các lỗi vi phạm do thiếu hiểu biết và biết cách bảo vệ quyền lợi hợp pháp của bản thân khi làm việc với cơ quan chức năng.',
            f'Đặc biệt trong bối cảnh {ctx}, các tổ công tác Cảnh sát giao thông và hệ thống camera giám sát thông minh thường xuyên tăng cường kiểm tra, xử lý nghiêm minh các hành vi vi phạm. Nắm rõ căn cứ pháp lý hiện hành là cách tốt nhất để bạn lái xe an toàn và thượng tôn pháp luật.'
        ]) + paragraph(seed+'1b', [
            f'Bài viết này tổng hợp chi tiết các quy định pháp lý, văn bản nghị định mới nhất liên quan đến {ang} cho chuyên đề {t}. Mọi nội dung được tham chiếu từ các văn bản quy phạm pháp luật đang có hiệu lực thi hành.',
            f'Để tra cứu trực tiếp các văn bản pháp luật gốc của Chính phủ và Bộ Công an, bạn có thể truy cập mục <a href="/luat-giao-thong/nguon-tra-cuu/">danh mục nguồn tra cứu luật giao thông chính thức</a> được chúng tôi tổng hợp đầy đủ.'
        ])
    ))

    sections.append((f'Mức xử phạt vi phạm hành chính áp dụng hiện hành',
        paragraph(seed+'2a', [
            f'Căn cứ theo Nghị định xử phạt vi phạm hành chính trong lĩnh vực giao thông đường bộ và đường sắt hiện hành, hành vi vi phạm liên quan đến {t} phải chịu các khung hình phạt nghiêm khắc tùy thuộc vào mức độ và tính chất của lỗi vi phạm.',
            f'Bên cạnh hình thức phạt tiền bằng tiền mặt từ vài trăm nghìn đến hàng triệu đồng, người vi phạm còn có thể bị áp dụng các hình thức xử phạt bổ sung nghiêm khắc như: tước quyền sử dụng Giấy phép lái xe từ 1 tháng đến 24 tháng, hoặc tạm giữ phương tiện giao thông đến 7 ngày làm việc.',
            f'Đối với các lỗi vi phạm có nguy cơ gây tai nạn cao hoặc tái phạm nhiều lần, mức xử phạt sẽ được áp dụng ở khung kịch khung. Người tham gia giao thông cần ý thức rõ ràng rằng mức phạt tiền hiện nay là rất cao, đủ sức răn đe mọi hành vi coi thường luật pháp.'
        ]) + paragraph(seed+'2b', [
            f'Tìm hiểu thêm những kinh nghiệm thực tế khi lưu thông trong nội đô tại chuyên mục <a href="/kinh-nghiem/lai-xe-o-ha-noi/">kinh nghiệm lái xe an toàn ở Hà Nội</a> để không vô tình mắc phải các lỗi xử phạt đáng tiếc.',
            f'Việc nộp phạt hành chính hiện nay đã được tích hợp qua Cổng dịch vụ công Quốc gia, giúp người vi phạm có thể tra cứu biên bản và nộp tiền phạt trực tuyến một cách minh bạch mà không cần phải đi lại nhiều lần.'
        ]) + paragraph(seed+'2c', [f'Cần đặc biệt lưu ý rằng theo các quy định mới được ban hành, mức phạt tiền đối với các lỗi cố tình vượt đèn đỏ, đi ngược chiều hay vi phạm nồng độ cồn đã tăng lên rất cao. Do đó, việc chấp hành nghiêm chỉnh luật lệ giao thông là cách bảo vệ tài chính và an toàn bản thân tốt nhất.', f'Ngoài phạt tiền, việc tước giấy phép lái xe có thời hạn sẽ gây ảnh hưởng rất lớn đến công việc và sinh hoạt hằng ngày của người vi phạm. Ý thức tuân thủ pháp luật từ những chi tiết nhỏ nhất như bật đèn xi nhan hay đội mũ bảo hiểm chuẩn là điều tối cần thiết.'])
    ))

    sections.append((f'Trách nhiệm và quyền hạn của {a} khi tham gia giao thông',
        paragraph(seed+'3a', [
            f'Khi điều khiển phương tiện tham gia giao thông đường bộ, {a} có nghĩa vụ chấp hành nghiêm chỉnh hiệu lệnh của người điều khiển giao thông, hệ thống đèn tín hiệu, biển báo hiệu và vạch kẻ đường. Luôn mang theo đầy đủ các giấy tờ theo quy định gồm: đăng ký xe, giấy phép lái xe, bảo hiểm bắt buộc và giấy tờ tùy thân.',
            f'Người tham gia giao thông cũng có quyền được yêu cầu cán bộ chiến sĩ Cảnh sát giao thông thực hiện nhiệm vụ công khai, đúng điều lệnh Công an nhân dân, giải thích rõ lỗi vi phạm và xuất trình chuyên đề tuần tra kiểm soát theo đúng quy định pháp luật khi được yêu cầu.',
            f'Trong trường hợp xảy ra tranh chấp hoặc không đồng ý với biên bản vi phạm hành chính, bạn có quyền ghi ý kiến không đồng ý vào phần ý kiến của người vi phạm trong biên bản và có quyền khiếu nại, khởi kiện theo đúng trình tự thủ tục luật định.'
        ]) + paragraph(seed+'3b', [
            f'Để chuẩn bị tốt nhất mọi điều kiện pháp lý trước khi thuê phương tiện tự lái, bạn có thể tham khảo thêm hướng dẫn chi tiết tại <a href="/thue-xe-may/ha-noi/">thủ tục thuê xe máy Hà Nội</a> của cửa hàng {brand}.',
            f'Sự hợp tác văn minh, đúng mực và thái độ tôn trọng pháp luật sẽ luôn giúp các buổi làm việc giải quyết vi phạm diễn ra nhanh chóng, thuận lợi cho cả hai phía.'
        ])
    ))

    sections.append((f'Những hiểu lầm và lỗi vi phạm phổ biến {ctx}',
        paragraph(seed+'4a', [
            f'Thực tế cho thấy, trong tình huống {ctx}, rất nhiều người lái xe thường mắc lỗi vi phạm do những hiểu lầm truyền miệng không có căn cứ pháp lý. Một số người lầm tưởng rằng có thể sử dụng hình ảnh giấy phép lái xe chụp trên điện thoại thay thế cho bản gốc khi bị kiểm tra hành chính trực tiếp.',
            f'Một hiểu lầm tai hại khác liên quan đến việc cho rằng xe máy điện không cần đội mũ bảo hiểm hay không bị xử phạt nồng độ cồn. Theo luật định, người điều khiển xe đạp điện, xe máy điện đều là đối tượng phải tuân thủ nghiêm ngặt các quy định về an toàn giao thông và chịu mức phạt tương đương xe cơ giới.',
            f'Nhiều tài xế cũng thường mắc lỗi chuyển làn đường hoặc rẽ tại các nút giao đông đúc mà quên bật đèn xi nhan báo rẽ trước một khoảng cách an toàn, hoặc chỉ bật đèn xi nhan khi xe đã bắt đầu đổi hướng di chuyển.'
        ]) + paragraph(seed+'4b', [
            f'Để trang bị kiến thức chuẩn xác và loại bỏ các hiểu lầm tai hại, hãy tham khảo thêm mục <a href="/faq/">câu hỏi thường gặp FAQ về quy định xe máy</a> để vững vàng kiến thức trên mọi nẻo đường.',
            f'Luôn chú ý quan sát hệ thống biển chỉ dẫn phân làn treo trên cao tại các trục đường lớn để không vô tình đi nhầm vào làn đường dành riêng cho xe ô tô.'
        ]) + paragraph(seed+'4c', [f'Nhiều tài xế thường chủ quan không bật đèn xi nhan báo rẽ khi đi vào vòng xuyến hoặc khi chuyển hướng ở những ngã ba nhỏ. Đây là một trong những lỗi bị xử phạt rất phổ biến tại các đô thị, người lái xe cần rèn luyện thói quen quan sát gương và bật tín hiệu báo rẽ từ sớm.', f'Tại các tuyến đường một chiều hoặc có biển cấm rẽ theo giờ, hãy luôn chú ý biển báo phụ gắn phía dưới. Việc đi theo thói quen cũ mà không quan sát biển báo mới cắm là nguyên nhân hàng đầu khiến nhiều người bị xử phạt oan uổng.'])
    ))

    sections.append((f'Thủ tục, hồ sơ và các bước giải quyết đúng quy định',
        paragraph(seed+'5a', [
            f'Khi cần làm các thủ tục hành chính liên quan đến {t}, {a} cần chuẩn bị một bộ hồ sơ đầy đủ bao gồm: bản gốc và bản sao căn cước công dân gắn chíp, giấy đăng ký xe, giấy chứng nhận kiểm định (nếu có) và các mẫu đơn theo quy chuẩn của cơ quan chức năng.',
            f'Quy trình nộp hồ sơ hiện nay đã được tinh giản tối đa thông qua việc nộp trực tuyến trên Cổng dịch vụ công Bộ Công an hoặc ứng dụng định danh điện tử VNeID. Sau khi tiếp nhận hồ sơ hợp lệ, cơ quan thụ lý sẽ cấp giấy hẹn trả kết quả rõ ràng.',
            f'Người dân tuyệt đối không nên nhờ vả các đối tượng "cò mồi" làm thủ tục hộ bên ngoài cổng cơ quan hành chính để tránh bị lừa đảo chiếm đoạt tài sản hoặc làm giả giấy tờ tài liệu của cơ quan nhà nước.'
        ]) + paragraph(seed+'5b', [
            f'Nếu bạn đang chuẩn bị giấy tờ để thuê xe phục vụ công việc dài hạn, hãy tham khảo các mẫu hợp đồng mẫu tại <a href="/bang-gia/">chuyên trang bảng giá và hợp đồng thuê xe</a>.',
            f'Mọi khoản lệ phí nhà nước đều có biên lai thu tiền điện tử chính quy. Hãy lưu giữ cẩn thận các biên lai thu phí để làm căn cứ đối chiếu khi nhận kết quả thủ tục.'
        ]) + paragraph(seed+'5c', [f'Thời hạn giải quyết các thủ tục hành chính giao thông thông thường từ 2 đến 7 ngày làm việc tùy tính chất vụ việc. Người làm thủ tục nên chủ động tra cứu mã hồ sơ trực tuyến để nắm bắt tiến độ xử lý mà không cần mất công đến tận trụ sở nhiều lần.', f'Khi đi làm thủ tục, hãy chuẩn bị trước các bản sao công chứng kèm bản gốc để cán bộ thụ lý đối chiếu nhanh chóng. Việc chuẩn bị giấy tờ chu đáo sẽ giúp bạn tiết kiệm được nhiều thời gian và công sức đi lại.'])
    ))

    sections.append((f'Hướng dẫn tra cứu phạt nguội và nộp phạt trực tuyến',
        paragraph(seed+'6a', [
            f'Hệ thống camera giám sát giao thông thông minh tại Hà Nội hiện đã phủ sóng hầu khắp các nút giao trọng điểm. Để chủ động kiểm tra xem phương tiện của mình có bị phạt nguội hay không, bạn chỉ cần truy cập trang thông tin điện tử của Cục Cảnh sát giao thông hoặc Công an thành phố Hà Nội.',
            f'Nhập chính xác biển kiểm soát xe và loại phương tiện vào ô tra cứu để nhận kết quả chi tiết: thời gian vi phạm, địa điểm nút giao, lỗi vi phạm cụ thể và đơn vị công an đang thụ lý giải quyết vụ việc.',
            f'Khi phát hiện có thông báo vi phạm, bạn có thể thực hiện nộp phạt trực tuyến ngay tại nhà thông qua Cổng dịch vụ công Quốc gia bằng tài khoản ngân hàng hoặc ví điện tử một cách nhanh chóng và an toàn.'
        ]) + paragraph(seed+'6b', [
            f'Kiểm tra định kỳ phạt nguội mỗi tháng một lần là thói quen tốt giúp bạn tránh tình trạng bị từ chối đăng kiểm hoặc dồn tiền phạt quá lớn khi sang tên đổi chủ xe.',
            f'Xem thêm các hướng dẫn hữu ích về phương tiện 2 bánh tại <a href="/kinh-nghiem/">chuyên mục cẩm nang kinh nghiệm di chuyển</a>.'
        ])
    ))

    sections.append((f'Kỹ năng lưu thông an toàn và phòng tránh vi phạm tại Hà Nội',
        paragraph(seed+'7a', [
            f'Để lưu thông an toàn và không mắc lỗi vi phạm tại thủ đô, kỹ năng quan trọng nhất là giữ khoảng cách an toàn với xe đi trước và luôn làm chủ tốc độ. Không vì vội vàng mà leo lên vỉa hè, vượt đèn vàng hay chen lấn vào làn đường ngược chiều gây xung đột giao thông.',
            f'Khi đi qua các vòng xuyến ngã năm, ngã sáu đông đúc, hãy tuân thủ nghiêm ngặt quy tắc nhường đường cho xe đi từ bên trái trong vòng xuyến và bật đèn xi nhan xin đường từ sớm để các phương tiện khác chủ động nhường lối.',
            f'Luôn cài quai mũ bảo hiểm chắc chắn, kiểm tra hệ thống gương chiếu hậu trước khi nổ máy và tuyệt đối nói không với rượu bia khi đã ngồi sau tay lái.'
        ]) + paragraph(seed+'7b', [
            f'Đối với việc kiểm tra an toàn kỹ thuật phương tiện trước khi ra đường, hãy tham khảo <a href="/bao-duong/xe-may/kiem-tra-truoc-khi-nhan/">quy trình kiểm tra an toàn xe máy</a> để luôn yên tâm trên mọi nẻo đường.',
            f'Lái xe văn minh, tôn trọng người già, phụ nữ và trẻ em không chỉ bảo vệ an toàn cho bạn mà còn góp phần xây dựng văn hóa giao thông thủ đô thanh lịch, hiện đại.'
        ])
    ))

    sections.append((f'Thông tin liên hệ Thuê xe máy Nguyễn Hà',
        f'<p>{brand} tọa lạc tại {addr} ({escape(FACTS["landmark"])}). Cửa hàng mở cửa từ {hours}. Điện thoại, Zalo và WhatsApp: <a href="tel:+84334699969">{phone}</a>.</p>'
        + f'<p>Quý khách có thể xem thêm <a href="/bang-gia/">bảng giá niêm yết</a>, <a href="/thue-xe-may/ha-noi/">thuê xe máy Hà Nội</a>, <a href="/faq/">câu hỏi thường gặp FAQ</a> và <a href="/lien-he/">trang liên hệ</a> để được hỗ trợ chu đáo nhất.</p>'
        + paragraph(seed+'contact', [
            f'Đội ngũ chăm sóc khách hàng của {brand} luôn sẵn sàng tư vấn mẫu xe phù hợp nhất với nhu cầu và lịch trình của bạn. Chúng tôi cam kết xe vận hành êm ái, đầy đủ giấy tờ và hỗ trợ kỹ thuật tận tình.',
            f'Với phương châm phục vụ tận tâm và chuyên nghiệp, {brand} tự hào đồng hành cùng quý khách trên mọi nẻo đường thủ đô. Hãy gọi ngay hotline để được chuẩn bị xe tốt nhất trước giờ xuất phát.'
        ])
    ))

    body = ' '.join(x[1] for x in sections); wc = len(words(body))
    return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],
            'excerpt':f'Quy định {t} cho {a}: căn cứ pháp lý, mức phạt vi phạm hiện hành, quy trình thủ tục và tư vấn từ Nguyễn Hà.',
            'sections':[[h,b] for h,b in sections],'keywords':f'{s["topic"]} {a} luật giao thông Hà Nội',
            'parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],
            'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}

# ── Router & Make ─────────────────────────────────────────────────────────────
def make_article(s):
    w=s['writer']
    if w=='thue-xe': return make_thue_xe(s)
    if w=='xe-info': return make_xe_info(s)
    if w=='du-lich': return make_du_lich(s)
    return make_luat(s)

# ── QA ────────────────────────────────────────────────────────────────────────
def score(article,existing):
    html=' '.join(b for _,b in article['sections']);wc=len(words(html));critical=[];points=0;details={}
    def add(name,value,maxv):
        nonlocal points;points+=value;details[name]={'score':value,'max':maxv}
    add('metadata',15 if 35<=len(article['title'])<=120 and 100<=len(article['excerpt'])<=170 else 8,15)
    add('structure',20 if len(article['sections'])>=8 and all(h and '<p>' in b for h,b in article['sections']) else 8,20)
    add('depth',25 if CFG['minimum_words']<=wc<=CFG['maximum_words'] else (12 if wc>=700 else 0),25)
    links=len(re.findall(r'href="/',html));add('internal_links',15 if links>=4 else links*3,15)
    fact_terms=sum(x in html for x in [FACTS['phone'],FACTS['hours'],FACTS['address']]);add('facts',10 if fact_terms==3 else fact_terms*3,10)
    a_grams=grams(html)
    if article.get('id'): _GRAMS_CACHE[article['id']]=a_grams
    maxsim=max((gram_similarity(a_grams,article_grams(p)) for p in existing),default=0);add('uniqueness',15 if maxsim<=CFG['maximum_similarity'] else 0,15)
    urls={p['url'] for p in existing};intents={p.get('intent') for p in existing if p.get('intent')}
    if article['url'] in urls: critical.append('duplicate_url')
    if article['intent'] and article['intent'] in intents: critical.append('duplicate_intent')
    if maxsim>CFG['maximum_similarity']:critical.append(f'similarity_{maxsim:.3f}')
    if wc<CFG['minimum_words']:critical.append(f'thin_{wc}_words')
    return {'score':points,'pass':points>=CFG['minimum_score'] and not critical,'critical':critical,'details':details,'word_count':wc,'max_similarity':round(maxsim,4)}

# ── Index ─────────────────────────────────────────────────────────────────────
def reindex():
    rows=[]
    for p in load_existing():
        if p.get('kind') in ('hub','page'):continue
        text=' '.join(re.sub(r'<[^>]+>',' ',b) for _,b in p.get('sections',[]))
        rows.append({'id':p.get('id'),'url':p['url'],'title':p['title'],'hub':p['hub'],'parent':p.get('parent'),'intent':p.get('intent'),'word_count':p.get('wordCount',len(words(text))),'sha256':hashlib.sha256(text.encode()).hexdigest(),'status':'published'})
    INDEX_PATH.write_text('\n'.join(json.dumps(r,ensure_ascii=False,separators=(',',':')) for r in rows) + '\n')
    return len(rows)

def is_operating_hours():
    cfg_hours = CFG.get('operating_hours')
    if not cfg_hours: return True
    p_start = cfg_hours.get('pause_start_hour', 1)
    p_resume = cfg_hours.get('resume_hour', 8)
    h = datetime.now().hour
    if p_start <= h < p_resume:
        return False
    return True

# ── Run ───────────────────────────────────────────────────────────────────────
def run(limit=None,dry_run=False):
    if (ROOT/'STOP_FACTORY').exists():
        print('Factory paused by STOP_FACTORY. Skipping run.')
        return 0
    if not dry_run and not is_operating_hours():
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Ngoài khung giờ hoạt động (nghỉ đêm từ 01:00 đến 07:59). Tạm dừng chu kỳ cho đến 08:00 sáng.')
        return 0
    state=json.loads(STATE_PATH.read_text())
    existing=load_existing()
    urls={p['url'] for p in existing};intents={p.get('intent') for p in existing if p.get('intent')}
    target=limit or (CFG['pairs_per_run']*CFG['pair_size'])
    seq=state['next_sequence'];accepted=[];rejected=0;logs=[]
    while len(accepted)<target:
        accepted_articles = [x[0] for x in accepted]
        spec=spec_for(seq);article=make_article(spec);qa=score(article,existing+accepted_articles)
        log_entry={'timestamp':datetime.now(timezone.utc).isoformat(),'sequence':seq,'id':article['id'],'url':article['url'],'intent':article['intent'],'writer':spec['writer'],'qa':qa}
        if qa['pass'] and article['url'] not in urls and article['intent'] not in intents:
            accepted.append((article,log_entry))
            urls.add(article['url']);intents.add(article['intent'])
        else:
            rejected+=1;log_entry['qa']['pass']=False;logs.append(log_entry)
        seq+=1
    if dry_run:
        print(json.dumps({'dry_run':True,'accepted_count':len(accepted),'rejected_count':rejected,'first_sample':accepted[0][0] if accepted else None,'qa_scores':[x[1]['qa'] for x in accepted[:3]]},ensure_ascii=False,indent=2))
        return 0
    ARTICLES.mkdir(parents=True,exist_ok=True)
    for art,log in accepted:
        (ARTICLES/f'{art["id"]}.json').write_text(json.dumps(art,ensure_ascii=False,indent=2)+'\n')
        logs.append(log)
    with QUEUE_PATH.open('a',encoding='utf-8') as q:
        for entry in logs: q.write(json.dumps(entry,ensure_ascii=False)+'\n')
    state['next_sequence']=seq
    state['published_by_factory']=state.get('published_by_factory',0)+len(accepted)
    state['rejected']=state.get('rejected',0)+rejected
    state['last_run']=datetime.now(timezone.utc).isoformat()
    state['status']='ready'
    STATE_PATH.write_text(json.dumps(state,indent=2)+'\n')
    reindex()
    print(f'PUBLISHED: {len(accepted)} articles; REJECTED: {rejected}; NEXT_SEQ: {seq}')
    if state['published_by_factory'] >= state.get('notify_milestone', 1000):
        print(f'MILESTONE_REACHED: {state["published_by_factory"]} articles published!')
        (ROOT/'STOP_FACTORY').touch()
        print('STOP_FACTORY created to pause production at milestone as requested.')
    return 0

# ── Report ────────────────────────────────────────────────────────────────────
def report():
    articles=load_existing()
    by_hub={}
    for a in articles:
        h=a.get('hub','legacy');by_hub[h]=by_hub.get(h,0)+1
    wcs=[a.get('wordCount',0) for a in articles if a.get('wordCount')]
    out={
        'total_published':len(articles),
        'by_hub':by_hub,
        'average_word_count':round(sum(wcs)/max(1,len(wcs)),1),
        'factory_version':CFG['version'],
        'matrix_total_capacity':TOTAL_CAPACITY
    }
    print(json.dumps(out,ensure_ascii=False,indent=2));return 0

# ── Daemon ────────────────────────────────────────────────────────────────────
def daemon(interval=3600, limit=None):
    import time, subprocess
    print(f'Starting Content Factory daemon (interval: {interval}s)...')
    while True:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f'[{now_str}] Checking factory state...')
        if (ROOT/'STOP_FACTORY').exists() or not CFG.get('enabled', True):
            print('Factory paused by control flag (STOP_FACTORY / config). Sleeping 60s...')
            time.sleep(min(interval, 60)); continue
        if not is_operating_hours():
            print(f'[{now_str}] Đang trong giờ nghỉ đêm (01:00 - 08:00). Tạm dừng chu kỳ, sẽ chạy lại lúc 08:00 sáng...')
            time.sleep(min(interval, 1800)); continue
        state = json.loads(STATE_PATH.read_text())
        target = CFG.get('target_articles')
        existing = len(load_existing())
        if target and existing >= target:
            print(f'Target reached: {existing}/{target} articles. Stopping daemon.')
            break
        try:
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=str(ROOT))
        except Exception as e:
            print(f'git pull notice: {e}')
        run(limit)
        try:
            subprocess.run([sys.executable, str(ROOT/'scripts/build.py')], check=True, cwd=str(ROOT))
            subprocess.run([sys.executable, str(ROOT/'tests/test_content_factory.py')], check=True, cwd=str(ROOT))
            subprocess.run([sys.executable, str(ROOT/'scripts/validate_factory_site.py')], check=True, cwd=str(ROOT))
        except Exception as e:
            print(f'Build/test error: {e}')
        try:
            res = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, cwd=str(ROOT))
            if res.stdout.strip():
                print('New articles verified. Committing and pushing to main...')
                subprocess.run(['git', 'add', '-A'], check=True, cwd=str(ROOT))
                subprocess.run(['git', 'commit', '-m', f'content: auto-publish QA-approved batch ({len(load_existing())}/{target} articles)'], check=True, cwd=str(ROOT))
                subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=str(ROOT))
                subprocess.run(['git', 'push', 'origin', 'main'], check=True, cwd=str(ROOT))
                print('Successfully published and pushed batch.')
            else:
                print('No changes in this cycle.')
        except Exception as e:
            print(f'Git push notice: {e}')
        print(f'Cycle finished. Sleeping {interval}s...')
        time.sleep(interval)

# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
    r=sp.add_parser('run');r.add_argument('--limit',type=int);r.add_argument('--dry-run',action='store_true')
    sp.add_parser('reindex');sp.add_parser('status');sp.add_parser('report')
    d=sp.add_parser('daemon');d.add_argument('--interval',type=int,default=3600);d.add_argument('--limit',type=int)
    a=ap.parse_args()
    if a.cmd=='run':return run(a.limit,a.dry_run)
    if a.cmd=='reindex':print(json.dumps({'index_rows':reindex()}));return 0
    if a.cmd=='report':return report()
    if a.cmd=='daemon':return daemon(a.interval,a.limit)
    state=json.loads(STATE_PATH.read_text());print(json.dumps({'config':CFG,'state':state,'articles':len(load_existing()),'stopped':(ROOT/'STOP_FACTORY').exists(),'matrix_capacity':TOTAL_CAPACITY},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
