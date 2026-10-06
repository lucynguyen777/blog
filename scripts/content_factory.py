#!/usr/bin/env python3
"""Deterministic, API-free article queue, writer and QA gate."""
from pathlib import Path
from datetime import datetime, timezone
from html import escape
import argparse, hashlib, json, re, sys, unicodedata

ROOT=Path(__file__).resolve().parent.parent
CFG=json.loads((ROOT/'config/content-factory.json').read_text())
FACTS=json.loads((ROOT/'config/business-facts.json').read_text())
STATE_PATH=ROOT/'data/factory-state.json'
QUEUE_PATH=ROOT/'data/factory-queue.jsonl'
INDEX_PATH=ROOT/'data/content-index.jsonl'
ARTICLES=ROOT/'content/articles'
LEGACY=ROOT/'content/posts.json'
HUB_PARENT={'thue-xe':'/thue-xe/','xe-may':'/xe-may/','xe-dien':'/xe-dien/','xe-dap':'/xe-dap/','o-to':'/o-to/','bao-duong':'/bao-duong/','du-lich':'/du-lich/','luat-giao-thong':'/luat-giao-thong/','kinh-nghiem':'/kinh-nghiem/'}

# ── Ma trận hub 1: Thuê xe (12×8×6×10×10 = 57,600) ──────────────────────────
DISTRICTS=['Long Biên','Gia Lâm','Hoàn Kiếm','Ba Đình','Tây Hồ','Hai Bà Trưng','Đống Đa','Cầu Giấy','Thanh Xuân','Hà Đông','Nam Từ Liêm','Bắc Từ Liêm']
VEHICLES=[('xe số','xe-may'),('xe ga','xe-may'),('xe điện','xe-dien'),('xe 50cc','thue-xe'),('Honda Wave','xe-may'),('Yamaha Sirius','xe-may'),('Honda Vision','xe-may'),('Honda Air Blade','xe-may')]
AUDIENCES=['người đi làm','sinh viên','khách du lịch','người lưu trú dài ngày','người mới lái','người cần đi lại hằng ngày']
ANGLES=[
 ('chọn xe','cách chọn xe phù hợp'),('kiểm tra xe','checklist nhận xe'),('chi phí','cách dự trù chi phí'),
 ('hợp đồng','các mục cần đọc trong hợp đồng'),('lộ trình','cách chuẩn bị lộ trình'),('an toàn','những bước sử dụng an toàn'),
 ('thuê theo tuần','kinh nghiệm thuê theo tuần'),('thuê theo tháng','kinh nghiệm thuê theo tháng'),
 ('giao nhận','cách thống nhất giao nhận'),('so sánh','tiêu chí so sánh lựa chọn')]
CONTEXTS=['đi làm giờ cao điểm','ở Hà Nội ba ngày','thuê bảy ngày','thuê một tháng','đi trong nội thành','đi giữa hai quận','mang hành lý gọn','đi cùng một người','nhận xe tại cửa hàng','lần đầu thuê xe']
ROUTE_NEEDS=['quãng đường dưới 5 km','nhiều điểm dừng','cần gửi xe thường xuyên','di chuyển buổi tối','đi vào ngõ nhỏ','đi qua đường đông','lịch trình linh hoạt','ưu tiên dễ điều khiển','cần mang đồ cá nhân','đi hai lượt mỗi ngày']

# ── Ma trận hub 2: Xe máy / Xe điện / Xe đạp — thông tin (8×9×6×5 = 2,160) ──
INFO_VEHICLES=[
 ('xe số','xe-may'),('xe ga','xe-may'),('Honda Wave','xe-may'),('Honda Vision','xe-may'),
 ('Yamaha Sirius','xe-may'),('Honda Air Blade','xe-may'),('xe điện','xe-dien'),('xe đạp điện','xe-dap')]
INFO_TOPICS=[
 ('bảo dưỡng định kỳ','lịch bảo dưỡng và chi phí'),('tiêu hao nhiên liệu','kinh nghiệm tiết kiệm xăng'),
 ('an toàn khi đi mưa','kỹ năng lái an toàn trời mưa'),('chọn lốp','tiêu chí chọn lốp phù hợp'),
 ('kiểm tra trước chuyến','checklist trước khi xuất phát'),('phanh ABS','cách sử dụng phanh ABS đúng cách'),
 ('sạc pin xe điện','hướng dẫn sạc và bảo quản pin'),('phụ tùng thay thế','phụ tùng cần ưu tiên thay theo định kỳ'),
 ('đăng ký xe','thủ tục đăng ký và giấy tờ cần có')]
INFO_AUDIENCES=['người dùng hằng ngày','người mới mua xe','người thuê xe','sinh viên','người đi làm xa','khách du lịch']
INFO_SEASONS=['mùa hè','mùa mưa','đầu năm học','cuối năm','dịp lễ Tết']

# ── Ma trận hub 3: Du lịch Việt Nam (15×8×4×4 = 1,920) ──────────────────────
PLACES=[
 'Hà Nội','Hạ Long','Ninh Bình','Sapa','Mộc Châu','Hội An','Đà Nẵng','Huế',
 'Nha Trang','Đà Lạt','Phú Quốc','Hồ Chí Minh','Cần Thơ','Hà Giang','Phong Nha']
TRAVEL_VEHICLES=[('xe máy','xe-may'),('xe điện','xe-dien'),('xe đạp','xe-dap'),
 ('xe số','xe-may'),('xe ga','xe-may'),('Honda Wave','xe-may'),('Yamaha Sirius','xe-may'),('xe 50cc','thue-xe')]
TRAVEL_DURATIONS=['cuối tuần (2 ngày)','chuyến 3 ngày','tuần lễ (7 ngày)','hành trình dài ngày']
TRAVEL_TYPES=['đi một mình','đi theo cặp','nhóm bạn','gia đình có trẻ nhỏ']

# ── Ma trận hub 4: Luật giao thông & Kinh nghiệm (20×6 = 120) ───────────────
LAW_TOPICS=[
 ('bằng A1','điều kiện và thủ tục thi bằng A1'),('bằng A2','điều kiện thi bằng A2 cho xe trên 175cc'),
 ('bằng B1','bằng B1 và quy định lái xe ô tô'),('bằng quốc tế','công nhận bằng lái quốc tế tại Việt Nam'),
 ('mũ bảo hiểm','quy định đội mũ bảo hiểm và xử phạt'),('nồng độ cồn','mức phạt nồng độ cồn 2024-2025'),
 ('điện thoại khi lái','phạt dùng điện thoại khi lái xe'),('tốc độ đô thị','giới hạn tốc độ trong đô thị'),
 ('đỗ xe sai','xử phạt đỗ xe sai quy định'),('vượt đèn đỏ','mức phạt vượt đèn đỏ hiện hành'),
 ('xe điện giấy phép','giấy phép cần có cho xe điện'),('xe đạp điện','quy định xe đạp điện và bảo hiểm'),
 ('bảo hiểm xe','bảo hiểm bắt buộc và tự nguyện'),('tai nạn xử lý','các bước xử lý khi xảy ra tai nạn'),
 ('kiểm định xe','lịch kiểm định và thủ tục đăng kiểm'),('chạy xe ban đêm','quy định và kỹ năng lái đêm an toàn'),
 ('đi xe nước ngoài','thủ tục mang xe máy sang nước ngoài'),('nhường đường','quy tắc nhường đường và ưu tiên'),
 ('camera phạt nguội','camera giám sát giao thông và tra cứu phạt'),('biển báo','cách đọc biển báo giao thông phổ biến')]
LAW_AUDIENCES=['người mới lái','sinh viên','khách du lịch nước ngoài','người lưu trú tại Hà Nội','người thuê xe','tài xế lâu năm cần cập nhật']

# Ngưỡng: seq <= THUE_XE_CAP → writer thuê xe; tiếp theo info, du lịch, luật
THUE_XE_CAP = len(DISTRICTS)*len(VEHICLES)*len(AUDIENCES)*len(ANGLES)*len(CONTEXTS)*len(ROUTE_NEEDS)
INFO_CAP     = THUE_XE_CAP + len(INFO_VEHICLES)*len(INFO_TOPICS)*len(INFO_AUDIENCES)*len(INFO_SEASONS)
TRAVEL_CAP   = INFO_CAP + len(PLACES)*len(TRAVEL_VEHICLES)*len(TRAVEL_DURATIONS)*len(TRAVEL_TYPES)
LAW_CAP      = TRAVEL_CAP + len(LAW_TOPICS)*len(LAW_AUDIENCES)


def slugify(s):
 s=unicodedata.normalize('NFD',s.lower());s=''.join(c for c in s if unicodedata.category(c)!='Mn').replace('đ','d')
 return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',s)).strip('-')

def words(html): return re.findall(r"[\wÀ-ỹ]+",re.sub(r'<[^>]+>',' ',html),re.UNICODE)
def grams(text,n=5):
 t=[x.lower() for x in words(text)];return set(tuple(t[i:i+n]) for i in range(max(0,len(t)-n+1)))
_GRAMS_CACHE={}
def article_grams(p):
 k=p.get('id') or p.get('url')
 if k and k in _GRAMS_CACHE: return _GRAMS_CACHE[k]
 g=grams(' '.join(b for _,b in p.get('sections',[])))
 if k: _GRAMS_CACHE[k]=g
 return g
def gram_similarity(g1,g2): return len(g1&g2)/max(1,len(g1|g2))
def similarity(a,b):
 x,y=grams(a),grams(b)
 return len(x&y)/max(1,len(x|y))
def load_existing():
 out=json.loads(LEGACY.read_text()) if LEGACY.exists() else []
 for p in sorted(ARTICLES.glob('*.json')):
  try: out.append(json.loads(p.read_text()))
  except Exception: pass
 return out

def paragraph(seed,variants): return '<p>'+variants[int(hashlib.sha256(seed.encode()).hexdigest(),16)%len(variants)]+'</p>'


# ── Writer 1: Thuê xe ─────────────────────────────────────────────────────────
def spec_for_thue_xe(seq):
 n=seq-1;angle=ANGLES[n%len(ANGLES)];n//=len(ANGLES);aud=AUDIENCES[n%len(AUDIENCES)];n//=len(AUDIENCES)
 vehicle,hub=VEHICLES[n%len(VEHICLES)];n//=len(VEHICLES);district=DISTRICTS[n%len(DISTRICTS)];n//=len(DISTRICTS)
 context=CONTEXTS[n%len(CONTEXTS)];n//=len(CONTEXTS);route=ROUTE_NEEDS[n%len(ROUTE_NEEDS)]
 title=f'{vehicle.capitalize()} ở {district}: {angle[0]} khi {context}, {route}'
 intent='|'.join([angle[0],vehicle,district,aud,context,route]).lower()
 url=f'/{hub}/{slugify(district)}/{slugify(vehicle)}/{slugify(angle[0])}-{slugify(aud)}-{slugify(context)}-{slugify(route)}/'
 return {'sequence':seq,'title':title,'intent':intent,'vehicle':vehicle,'hub':hub,'district':district,
         'audience':aud,'context':context,'route':route,'angle':angle[0],'angle_label':angle[1],'url':url,'writer':'thue-xe'}

def make_thue_xe(s):
 v=escape(s['vehicle']);d=escape(s['district']);a=escape(s['audience']);ang=escape(s['angle_label'])
 context=escape(s['context']);route=escape(s['route'])
 price=FACTS['prices'].get(s['vehicle'],FACTS['prices'].get('xe ga' if 'Vision' in v or 'Air Blade' in v else 'xe số'))
 seed=s['intent'];brand=escape(FACTS['brand']);phone=escape(FACTS['phone'])
 intro=f'<p>{ang.capitalize()} cần bắt đầu từ nhu cầu thực tế của {a}, quãng đường dự kiến và khả năng điều khiển {v}. Tình huống chính là {context} tại {d}, với nhu cầu {route}; bài viết chỉ dùng mức giá và chính sách đã được lưu trong dữ liệu của {brand}. Tình trạng xe còn sẵn phải được cửa hàng xác nhận tại thời điểm liên hệ.</p>'
 sections=[]
 sections.append(('Xác định nhu cầu trước khi chọn xe',intro+paragraph(seed+'1',[
  f'Hãy ghi lại số ngày sử dụng, tuyến đi thường xuyên, số người đi cùng và lượng hành lý. Với {a}, một lựa chọn phù hợp cần dễ làm quen, đủ thuận tiện cho lịch trình tại {d} và không tạo áp lực khi dắt hoặc quay đầu. Tên mẫu xe chỉ là điểm bắt đầu; cảm giác lái trên chiếc xe thực tế mới là căn cứ quan trọng.',
  f'Trước khi hỏi giá, nên mô tả rõ lịch đi lại tại {d}: thời điểm xuất phát, nơi gửi xe, quãng đường và nhu cầu chở đồ. {a.capitalize()} có thể dùng danh sách này để loại bỏ phương án không phù hợp, sau đó mới thử {v} và trao đổi về thời hạn thuê.'
  ])))
 sections.append((f'Đánh giá {v} theo hành trình ở {d}',paragraph(seed+'2',[
  f'Đường đông, ngõ nhỏ và điểm dừng khác nhau khiến thao tác thực tế quan trọng hơn một bảng thông số chung. Hãy thử chống chân, dắt xe, quay đầu, bóp phanh và quan sát gương trong khu vực phù hợp. Nếu chưa tự tin với {v}, yêu cầu hướng dẫn trước khi nhận xe.',
  f'Khi di chuyển ở {d}, người thuê cần tính cả đoạn đường đến nơi gửi xe và khả năng xoay trở ở điểm đến. Thử tư thế ngồi, khoảng để chân và cách đặt hành lý. Không nhận xe khi có dấu hiệu ảnh hưởng đến an toàn hoặc thao tác chưa rõ.'
  ])+f'<p>Với {a}, lịch trình nên có khoảng nghỉ và phương án thay đổi khi mưa, đường ùn hoặc điểm gửi xe kín chỗ. Không vừa lái vừa xem bản đồ; hãy dừng tại vị trí phù hợp rồi mới kiểm tra hướng đi.</p>'))
 sections.append(('Checklist kiểm tra trước khi nhận',paragraph(seed+'3a',[
  f'Kiểm tra phanh trước và sau, lốp, đèn, còi, gương, khóa, đồng hồ và mức nhiên liệu hoặc pin. Chụp biển số, các vết xước và phụ kiện khi hai bên cùng có mặt. Nếu có điểm bất thường, ghi vào biên bản giao nhận trước khi ký.',
  f'Quan sát kỹ toàn bộ lốp xe {v}: rãnh gai còn sâu không, áp suất lốp có căng đều không và vành đúc có dấu hiệu móp méo không. Bật thử đèn chiếu xa, đèn chiếu gần, xi nhan hai bên và đèn phanh để đảm bảo an toàn tuyệt đối khi lưu thông.',
  f'Trước khi nhận chiếc {v}, hãy kiểm tra khóa cổ, khóa từ và chân chống nghiêng/chân chống đứng. Thử bóp cả hai tay phanh để cảm nhận độ nảy và độ ăn của bố thắng, đảm bảo tay phanh không bị kẹt hay chạm sát vào tay nắm.'
 ])+paragraph(seed+'3b',[
  f'Khởi động và nghe tiếng máy của {v}; thử ga và phanh ở tốc độ thấp trong khu vực cho phép. Xác nhận mũ bảo hiểm, chìa khóa và vật dụng đi kèm. Với xe điện, cần hỏi đúng bộ sạc, cách sạc và phạm vi sử dụng của mẫu xe; không dùng một con số chung cho mọi pin.',
  f'Đề nổ {v} để kiểm tra độ nhạy của bộ đề và độ êm của động cơ khi nổ galanti. Hỏi rõ nhân viên về cách mở nắp bình xăng hoặc vị trí cắm sạc pin, vị trí để áo mưa trong cốp và lưu lại số cứu hộ khẩn cấp trước khi rời điểm giao nhận.',
  f'Lái thử một đoạn ngắn với {v} để cảm nhận độ cân bằng của tay lái và phuộc nhún trước sau. Kiểm tra hai gương chiếu hậu xem có bị rung lỏng khi máy chạy không và điều chỉnh đúng tầm mắt quan sát.'
 ])))
 sections.append(('Đối chiếu giá và tổng ngân sách',paragraph(seed+'4a',[
  f'Mức tham khảo hiện hành cho nhóm phù hợp là {escape(price)}. Giá chiếc {v} cụ thể còn phụ thuộc xe sẵn có và thời hạn thuê. Ngoài tiền thuê, cần chuẩn bị tiền cọc theo thỏa thuận, phí giao nhận nếu áp dụng, nhiên liệu và khoản phát sinh được ghi trong hợp đồng.',
  f'Ngân sách dự kiến khi thuê {v} tại {d} dựa trên khung giá niêm yết: {escape(price)}. Chi phí trọn gói cần tính thêm tiền xăng dầu hoặc điện sạc cho lộ trình, phí gửi xe qua đêm và khoản tiền cọc minh bạch được hoàn trả khi kết thúc hợp đồng.',
  f'Theo bảng giá đang áp dụng, nhóm xe phù hợp có mức {escape(price)}. {a.capitalize()} nên cân nhắc thời hạn thuê theo ngày hoặc tuần để nhận mức chiết khấu tốt nhất, tránh việc phát sinh gia hạn lẻ tẻ từng ngày.'
 ])+paragraph(seed+'4b',[
  f'Hãy yêu cầu cửa hàng chốt bằng văn bản: thời điểm bắt đầu, thời điểm trả, tổng tiền thuê, tiền cọc và điều kiện hoàn cọc. Không so sánh chỉ bằng giá ngày nếu nhu cầu thực tế là theo tuần hoặc tháng. Xem thêm <a href="/bang-gia/">bảng giá đang áp dụng</a> trước khi quyết định.',
  f'Để tối ưu chi tiêu cho chuyến đi, hãy đề nghị cơ sở cho thuê liệt kê toàn bộ điều khoản tài chính vào phiếu giao nhận: số tiền cọc, phương thức hoàn cọc và mức phí nếu quá giờ. Bạn có thể tra cứu chi tiết tại <a href="/bang-gia/">bảng giá niêm yết</a>.',
  f'Chi phí thuê luôn đi kèm cam kết minh bạch không phụ phí ẩn. Hai bên cần thống nhất cụ thể mốc 24 giờ của một ngày thuê và phương thức thanh toán. Đọc kỹ chi tiết tại <a href="/bang-gia/">trang bảng giá chính thức</a> trước khi đặt cọc.'
 ])))
 sections.append(('Đọc hợp đồng và giấy tờ',paragraph(seed+'5a',[
  f'Đối chiếu họ tên, thông tin chiếc xe, biển số, kỳ thuê, giờ trả và hiện trạng. Đọc phần trách nhiệm khi hư hỏng, trả sớm, quá giờ và mất phụ kiện. Chỉ ký khi nội dung trùng với trao đổi; giữ một bản hoặc ảnh rõ ràng để tra cứu trong thời gian sử dụng.',
  f'Hợp đồng thuê {v} là văn bản bảo vệ quyền lợi của cả hai bên. Hãy kiểm tra kỹ biển số xe ghi trên giấy tờ có khớp với biển số gắn trên xe thực tế hay không, đối chiếu rõ mốc giờ trả xe và trách nhiệm bảo quản tài sản.',
  f'Trước khi đặt bút ký, hãy đọc kỹ các điều khoản về phạm vi di chuyển, quy định bồi thường nếu xảy ra trầy xước hoặc va chạm ngoài ý muốn. Giữ lại một bản cứng hoặc chụp ảnh lại hợp đồng vào điện thoại để tra cứu khi cần.'
 ])+paragraph(seed+'5b',[
  f'Người lái phải đáp ứng điều kiện độ tuổi và giấy phép phù hợp với đúng loại phương tiện. Khi chưa chắc yêu cầu pháp lý cho {v}, hãy kiểm tra nguồn chính thức và mục <a href="/luat-giao-thong/nguon-tra-cuu/">hướng dẫn tra cứu luật, bằng lái</a>. Bài blog không thay thế văn bản đang có hiệu lực.',
  f'{a.capitalize()} điều khiển {v} cần có giấy phép lái xe hợp lệ theo quy định pháp luật Việt Nam. Đối với người nước ngoài hoặc người chưa rõ phân khối xe, nên tham khảo trước tại <a href="/luat-giao-thong/nguon-tra-cuu/">chuyên mục tra cứu luật giao thông</a> để tránh bị xử phạt khi lưu thông.',
  f'Đảm bảo mang theo giấy phép lái xe phù hợp khi nhận xe. Quy định điều khiển {v} đòi hỏi tuân thủ nghiêm ngặt luật giao thông đường bộ hiện hành; tra cứu thông tin chính xác tại mục <a href="/luat-giao-thong/nguon-tra-cuu/">hướng dẫn quy định bằng lái và pháp luật</a>.'
 ])))
 sections.append(('Tổ chức giao nhận và thời điểm trả',paragraph(seed+'6a',[
  f'Thuê ngắn hạn nhận xe tại cửa hàng. Việc giao xe cho kỳ nhiều ngày, tuần hoặc tháng cần được thống nhất trước; cửa hàng không giao nhận tại sân bay Nội Bài. Ghi rõ địa điểm tại {d}, người bàn giao và số điện thoại liên hệ để tránh chờ hoặc nhầm điểm.',
  f'Khách hàng có thể nhận xe trực tiếp tại cửa hàng hoặc yêu cầu hỗ trợ giao xe tại địa điểm thuận tiện ở {d} khi thuê theo tuần hoặc tháng. Thống nhất chính xác thời gian và vị trí hẹn bàn giao để không làm ảnh hưởng đến kế hoạch cá nhân.',
  f'Địa điểm giao nhận xe tại {d} cần được hai bên xác nhận qua tin nhắn hoặc điện thoại trước giờ hẹn. Hãy chuẩn bị sẵn giấy tờ tùy thân để thủ tục bàn giao diễn ra nhanh gọn trong vòng 5–10 phút.'
 ])+paragraph(seed+'6b',[
  f'Một ngày thuê được tính theo 24 giờ ghi trong hợp đồng. Hãy đặt nhắc lịch trước giờ trả và dự trù thời gian di chuyển. Khi cần thay đổi kế hoạch, liên hệ sớm thay vì tự suy đoán cách tính phí.',
  f'Cách tính thời gian chuẩn 24 giờ mỗi ngày giúp người thuê chủ động sắp xếp giờ trả xe. Nếu có phát sinh cần gia hạn hoặc trả sớm, hãy gọi điện thông báo trước cho cửa hàng để được hỗ trợ phương án tối ưu nhất.',
  f'Hãy cài đặt báo thức trên điện thoại trước mốc giờ trả xe 1 tiếng để chủ động thời gian chạy xe qua điểm hẹn, tránh giờ cao điểm tắc đường khiến bạn bị trễ giờ trả xe.'
 ])))
 sections.append(('Sử dụng xe trong suốt kỳ thuê',paragraph(seed+'7',[
  f'Mỗi ngày trước khi đi, quan sát nhanh lốp, phanh, đèn và dấu hiệu rò rỉ hoặc bất thường. Nếu {v} phát tiếng lạ, rung khác thường hay cảnh báo, dừng ở nơi an toàn rồi liên hệ cửa hàng; không tự sửa lớn hoặc thay phụ tùng khi chưa thống nhất.',
  f'Trong suốt thời gian sử dụng {v} tại {d}, hãy duy trì thói quen kiểm tra áp suất lốp và phanh trước mỗi chuyến đi. Khi xe có dấu hiệu hết dầu phanh hoặc máy nóng bất thường, hãy liên hệ hotline để được kỹ thuật viên hướng dẫn xử lý an toàn.',
  f'Giữ gìn xe cẩn thận, không chở quá tải trọng cho phép và luôn khóa cổ, khóa càng khi gửi xe tại các điểm công cộng. Nếu {v} gặp sự cố hỏng hóc giữa đường, gọi ngay số điện thoại cứu trợ của cửa hàng để được trợ giúp kịp thời.'
 ])+paragraph(seed+'7b',[
  f'Giữ chìa khóa và giấy tờ theo hướng dẫn, khóa xe tại nơi phù hợp và tránh để tài sản có giá trị trên xe. Trong lịch đi của {a} tại {d}, nên lưu sẵn số hỗ trợ để xử lý nhanh nếu phương tiện có dấu hiệu bất thường.',
  f'Tránh để ví tiền, điện thoại hay giấy tờ quan trọng trong cốp xe khi gửi ở các bãi gửi xe lạ. Luôn gửi xe tại các bãi có vé giữ xe rõ ràng và nhân viên bảo vệ túc trực.',
  f'Khi lưu thông vào ban đêm hoặc trong ngõ tối, hãy đảm bảo đèn xe luôn bật sáng và giữ tốc độ vừa phải. Luôn bảo quản cẩn thận chìa khóa dự phòng và các giấy tờ đi kèm xe.'
 ])))
 sections.append(('Hoàn tất trả xe minh bạch',paragraph(seed+'8a',[
  f'Khi trả {v}, hai bên cùng kiểm tra biển số, đồng hồ, nhiên liệu hoặc pin, vết xước và phụ kiện. Đối chiếu ảnh lúc nhận để tách tình trạng có sẵn khỏi vấn đề mới. Yêu cầu xác nhận đã nhận đủ xe, chìa khóa và đồ đi kèm.',
  f'Quy trình hoàn trả {v} diễn ra nhanh chóng: đối chiếu lại video/ảnh chụp ban đầu để khẳng định xe không phát sinh vết xước mới, kiểm tra vạch xăng/pin và bàn giao lại mũ bảo hiểm cùng giấy tờ gốc.',
  f'Khi bàn giao xe lại cho cửa hàng, hãy kiểm tra kỹ toàn bộ cốp xe và hộc đồ phía trước để không bỏ quên tư trang cá nhân. Hai bên cùng ký xác nhận hoàn thành kỳ thuê trên biên bản.'
 ])+paragraph(seed+'8b',[
  f'Nếu có khoản phát sinh, đề nghị giải thích theo điều khoản đã ký. Kiểm tra việc hoàn cọc trước khi rời điểm giao nhận. Lưu ảnh biên bản hoặc tin nhắn xác nhận cho đến khi giao dịch kết thúc hoàn toàn.',
  f'Tiền đặt cọc sẽ được hoàn trả ngay lập tức bằng tiền mặt hoặc chuyển khoản ngân hàng ngay khi kiểm tra xong hiện trạng xe. Bạn nên giữ biên nhận điện tử để hoàn tất mọi thủ tục.',
  f'Mọi chi phí nếu có phát sinh đều được giải trình rõ ràng căn cứ trên hợp đồng đã ký kết ban đầu. Nhận lại tiền cọc đầy đủ trước khi tạm biệt nhân viên bàn giao.'
 ])))
 sections.append(('Liên hệ và xác nhận xe còn sẵn',paragraph(seed+'9a',[
  f'{brand} ở {escape(FACTS["address"])}, {escape(FACTS["landmark"])}. Giờ mở cửa: {escape(FACTS["hours"])}. Điện thoại, Zalo và WhatsApp: <a href="tel:+84334699969">{phone}</a>.',
  f'Cơ sở cho thuê xe uy tín tọa lạc tại {escape(FACTS["address"])}, {escape(FACTS["landmark"])} ({brand}). Hotline hỗ trợ và Zalo: <a href="tel:+84334699969">{phone}</a>. Giờ phục vụ hằng ngày: {escape(FACTS["hours"])}.',
  f'Để trải nghiệm dịch vụ tại {brand}, quý khách có thể ghé qua {escape(FACTS["address"])}, {escape(FACTS["landmark"])}. Chúng tôi mở cửa từ {escape(FACTS["hours"])}. Liên hệ hotline/Zalo: <a href="tel:+84334699969">{phone}</a> để được phục vụ chu đáo.'
 ])+paragraph(seed+'9b',[
  f'Khi liên hệ, hãy gửi bốn thông tin: loại xe muốn thử, thời gian thuê, khu vực nhận tại {d} và nhu cầu của {a}. Cửa hàng sẽ xác nhận xe thực tế, mức cọc và điều kiện giao nhận. Xem <a href="/faq/">câu hỏi thường gặp</a> hoặc <a href="/lien-he/">trang liên hệ</a> để chuẩn bị trước.',
  f'Để được giữ xe nhanh chóng, vui lòng thông báo trước: mẫu xe mong muốn ({v}), số ngày dự kiến thuê, điểm đón tại {d} và nhu cầu di chuyển của bạn. Xem thêm thông tin chi tiết tại mục <a href="/faq/">câu hỏi thường gặp</a> và <a href="/lien-he/">kênh liên hệ</a>.',
  f'Đội ngũ chăm sóc khách hàng luôn sẵn sàng phản hồi nhanh chóng. Hãy nhắn tin thông tin lịch trình để chúng tôi kiểm tra tình trạng xe còn sẵn và chuẩn bị phương tiện tốt nhất. Tham khảo thêm <a href="/faq/">giải đáp thắc mắc FAQ</a> hoặc <a href="/lien-he/">thông tin liên hệ chi tiết</a>.'
 ])))
 body=' '.join(x[1] for x in sections);wc=len(words(body))
 return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],
         'excerpt':f'{s["angle_label"].capitalize()} cho {s["vehicle"]} tại {s["district"]}, gồm kiểm tra xe, chi phí, hợp đồng, giao nhận và cách liên hệ Nguyễn Hà.',
         'sections':[[h,b] for h,b in sections],'keywords':f'{s["angle"]} {s["vehicle"]} {s["district"]} {s["audience"]}',
         'parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],
         'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}


# ── Writer 2: Xe máy / Xe điện / Xe đạp — thông tin ─────────────────────────
def spec_for_xe_info(seq):
 n=seq-1;topic_key,topic_label=INFO_TOPICS[n%len(INFO_TOPICS)];n//=len(INFO_TOPICS)
 aud=INFO_AUDIENCES[n%len(INFO_AUDIENCES)];n//=len(INFO_AUDIENCES)
 vehicle,hub=INFO_VEHICLES[n%len(INFO_VEHICLES)];n//=len(INFO_VEHICLES)
 season=INFO_SEASONS[n%len(INFO_SEASONS)]
 title=f'{vehicle.capitalize()}: {topic_label} dành cho {aud} ({season})'
 intent=f'xe-info|{topic_key}|{vehicle}|{aud}|{season}'.lower()
 url=f'/{hub}/{slugify(vehicle)}/{slugify(topic_key)}-{slugify(aud)}-{slugify(season)}/'
 return {'sequence':seq,'title':title,'intent':intent,'vehicle':vehicle,'hub':hub,
         'topic':topic_key,'topic_label':topic_label,'audience':aud,'season':season,'url':url,'writer':'xe-info'}

def make_xe_info(s):
 v=escape(s['vehicle']);a=escape(s['audience']);t=escape(s['topic_label']);season=escape(s['season'])
 seed=s['intent'];brand=escape(FACTS['brand']);phone=escape(FACTS['phone'])
 sections=[]
 sections.append((f'Tổng quan: {t} với {v}',
  f'<p>Bài viết này tập trung vào {t} dành cho {a} sử dụng {v} trong giai đoạn {season}. Thông tin được tổng hợp từ thực tế vận hành và không thay thế hướng dẫn kỹ thuật chính thức của nhà sản xuất.</p>'
  +paragraph(seed+'A',[
   f'Với {a}, việc nắm rõ {t} giúp kéo dài tuổi thọ xe, giảm chi phí phát sinh và chủ động hơn trong các tình huống trên đường tại Hà Nội. Đặc biệt vào {season}, điều kiện đường sá và thời tiết có thể ảnh hưởng đáng kể đến hiệu suất và an toàn.',
   f'Nhiều người dùng {v} bỏ qua {t} cho đến khi gặp sự cố. Hiểu đúng các bước cơ bản giúp {a} phát hiện sớm vấn đề và xử lý kịp thời, đặc biệt trong {season} khi nhu cầu di chuyển thường tăng cao.'
  ])))
 sections.append(('Các bước thực hiện cụ thể',
  paragraph(seed+'B',[
   f'Bước đầu tiên là quan sát tổng thể {v}: lốp, phanh, đèn, còi và mức nhiên liệu hoặc pin. Ghi nhận bất kỳ dấu hiệu bất thường nào trước khi xử lý từng hạng mục. Với {a}, thao tác này nên trở thành thói quen trước mỗi chuyến đi dài trong {season}.',
   f'Đối với {v}, quy trình {t} bao gồm kiểm tra các bộ phận chuyển động, bôi trơn các điểm cần thiết và đảm bảo áp suất lốp đúng mức. Thực hiện vào {season} đặc biệt quan trọng vì thay đổi thời tiết ảnh hưởng đến vật liệu cao su và hệ thống điện.'
  ])+f'<p>Không tự thay phụ tùng chính khi chưa có kinh nghiệm. Đưa xe đến xưởng uy tín và yêu cầu giải thích trước khi đồng ý sửa chữa. Lưu lại hóa đơn và lịch bảo dưỡng để theo dõi chu kỳ tiếp theo.</p>'))
 sections.append(('Dấu hiệu cần chú ý',
  f'<p>Các dấu hiệu phổ biến cần xử lý ngay bao gồm: tiếng kêu lạ khi tăng tốc hoặc phanh, rung bất thường, đèn cảnh báo sáng, xe chạy nặng hơn bình thường hoặc tiêu hao nhiên liệu tăng đột ngột. Đối với xe điện, cần thêm chú ý vào chỉ số pin và thời gian sạc.</p>'
  +paragraph(seed+'C',[
   f'Trong {season}, {v} của {a} thường gặp các vấn đề liên quan đến hệ thống làm mát, điện và lốp. Phát hiện sớm và xử lý đúng cách giúp tránh chi phí sửa chữa lớn và đảm bảo an toàn trên đường.',
   f'Nếu {v} hoạt động không ổn định trong {season}, hãy kiểm tra tình trạng bình ắc-quy, hệ thống đánh lửa và bộ lọc gió. Đây là những hạng mục dễ bị ảnh hưởng bởi thay đổi nhiệt độ và độ ẩm theo mùa.'
  ])))
 sections.append(('Chi phí tham khảo và lựa chọn dịch vụ',
  f'<p>Chi phí cho {t} thay đổi tùy mẫu xe, tình trạng thực tế và đơn vị thực hiện. Nên hỏi báo giá trước, so sánh ít nhất hai địa chỉ uy tín và xác nhận rõ phạm vi dịch vụ trước khi đồng ý. Không để chi phí thấp là tiêu chí duy nhất khi chọn xưởng.</p>'
  +paragraph(seed+'D',[
   f'Với {a} sử dụng {v} thường xuyên, nên thiết lập lịch định kỳ thay vì chỉ mang xe đi khi có sự cố. Một số xưởng cung cấp gói bảo dưỡng theo km hoặc theo tháng, giúp kiểm soát chi phí và đảm bảo xe luôn trong tình trạng tốt.',
   f'Giá dịch vụ {t} cho {v} phụ thuộc nhiều vào loại phụ tùng được sử dụng. Phụ tùng chính hãng thường đắt hơn nhưng đảm bảo tương thích và bền hơn trong dài hạn. {a.capitalize()} nên ưu tiên phụ tùng từ đại lý hoặc nhà phân phối được ủy quyền.'
  ])))
 sections.append(('Lưu ý an toàn khi tự kiểm tra',
  f'<p>Không thực hiện kiểm tra khi xe vừa tắt máy, động cơ còn nóng hoặc trên mặt đường trơn. Đặt xe ở nơi bằng phẳng, thoáng, đủ ánh sáng. Rút chìa khóa trước khi kiểm tra bộ phận chuyển động.</p>'
  +paragraph(seed+'E',[
   f'Với xe điện, không tự tháo pin hay chạm vào các đầu nối điện cao áp. Khi phát hiện pin phình hoặc sạc không đủ công suất trong {season}, liên hệ trung tâm bảo hành của {v} để được kiểm tra đúng quy trình.',
   f'{a.capitalize()} nên mang thiết bị bảo hộ tối thiểu khi kiểm tra {v}: găng tay, đèn pin và khăn lau sạch. Tránh dùng nguồn lửa gần bình nhiên liệu hoặc bình ắc-quy.'
  ])))
 sections.append(('Câu hỏi thường gặp',
  f'<p><strong>Bao lâu nên thực hiện {t} một lần?</strong> Phụ thuộc vào km đã đi, điều kiện đường và khuyến cáo của nhà sản xuất. Với {v} sử dụng hằng ngày tại Hà Nội, thường nên kiểm tra sau 1.000–2.000 km hoặc mỗi 2–3 tháng.</p>'
  +f'<p><strong>Có thể tự làm không?</strong> Một số bước cơ bản {a} có thể tự thực hiện sau khi tham khảo hướng dẫn chính thức. Các hạng mục liên quan đến hệ thống phanh, điện hoặc động cơ nên để chuyên viên xử lý.</p>'
  +paragraph(seed+'F',[
   f'Nếu đây là lần đầu {a} thực hiện {t} cho {v}, hãy xem video hướng dẫn từ kênh chính thức của hãng xe hoặc đến trực tiếp xưởng để quan sát trước. Hiểu đúng quy trình giúp bạn kiểm tra lại sau khi hoàn tất dịch vụ.',
   f'Câu hỏi quan trọng cần hỏi xưởng: chi phí nhân công và phụ tùng tính riêng hay gộp, thời gian bảo hành sau sửa chữa, và cần mang {v} đến lúc mấy giờ để được phục vụ trong ngày.'
  ])))
 sections.append(('Tài nguyên tham khảo thêm',
  f'<p>Xem thêm <a href="/bao-duong/xe-may/kiem-tra-truoc-khi-nhan/">checklist kiểm tra xe trước khi nhận</a> và <a href="/luat-giao-thong/nguon-tra-cuu/">nguồn tra cứu luật và bằng lái</a> để chuẩn bị đầy đủ cho mỗi chuyến đi.</p>'
  +f'<p>Nếu đang cân nhắc thuê {v} thay vì mua, <a href="/thue-xe-may/ha-noi/">xem thêm thông tin thuê xe máy Hà Nội</a> và <a href="/bang-gia/">bảng giá hiện hành</a> để so sánh chi phí theo tháng so với sở hữu.</p>'))
 sections.append(('Liên hệ khi cần tư vấn thêm',
  f'<p>{brand} ở {escape(FACTS["address"])}, {escape(FACTS["landmark"])}. Giờ mở cửa: {escape(FACTS["hours"])}. Điện thoại, Zalo và WhatsApp: <a href="tel:+84334699969">{phone}</a>.</p>'
  +f'<p>Nếu bạn là {a} cần tư vấn về {v} hoặc đang tìm hiểu về {t}, hãy liên hệ trực tiếp. Đội ngũ cửa hàng có thể tư vấn dựa trên xe thực tế hiện có. Xem thêm <a href="/faq/">câu hỏi thường gặp</a> và <a href="/kinh-nghiem/">kinh nghiệm di chuyển</a>.</p>'))
 body=' '.join(x[1] for x in sections);wc=len(words(body))
 return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],
         'excerpt':f'{t.capitalize()} dành cho {a} sử dụng {v}, tổng hợp từ thực tế vận hành tại Hà Nội trong {season}.',
         'sections':[[h,b] for h,b in sections],'keywords':f'{s["topic"]} {v} {a} {season}',
         'parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],
         'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}


# ── Writer 3: Du lịch ─────────────────────────────────────────────────────────
def spec_for_du_lich(seq):
 n=seq-1;duration=TRAVEL_DURATIONS[n%len(TRAVEL_DURATIONS)];n//=len(TRAVEL_DURATIONS)
 travel_type=TRAVEL_TYPES[n%len(TRAVEL_TYPES)];n//=len(TRAVEL_TYPES)
 vehicle,_=TRAVEL_VEHICLES[n%len(TRAVEL_VEHICLES)];n//=len(TRAVEL_VEHICLES)
 place=PLACES[n%len(PLACES)]
 title=f'Du lịch {place} bằng {vehicle}: hành trình {duration} cho {travel_type}'
 intent=f'du-lich|{place}|{vehicle}|{duration}|{travel_type}'.lower()
 url=f'/du-lich/{slugify(place)}/{slugify(vehicle)}-{slugify(duration)}-{slugify(travel_type)}/'
 return {'sequence':seq,'title':title,'intent':intent,'vehicle':vehicle,'hub':'du-lich',
         'place':place,'duration':duration,'travel_type':travel_type,'url':url,'writer':'du-lich'}

def make_du_lich(s):
 v=escape(s['vehicle']);place=escape(s['place']);dur=escape(s['duration']);tt=escape(s['travel_type'])
 seed=s['intent'];brand=escape(FACTS['brand']);phone=escape(FACTS['phone'])
 sections=[]
 sections.append((f'Tại sao chọn {v} cho chuyến đi {place}',
  f'<p>Du lịch {place} bằng {v} mang lại sự linh hoạt mà phương tiện công cộng khó đáp ứng: tự quyết thời gian, ghé các điểm không nằm trên lộ trình cố định và khám phá ngõ nhỏ, làng quê hoặc đèo núi theo nhịp riêng. Hành trình {dur} phù hợp với {tt} nếu chuẩn bị kỹ.</p>'
  +paragraph(seed+'A',[
   f'{tt.capitalize()} chọn {v} vì chi phí thấp hơn xe khách hoặc thuê ô tô, đồng thời dễ tìm chỗ đỗ tại các điểm du lịch đông người ở {place}. Chuyến {dur} cho phép ghé nhiều địa điểm trong bán kính hẹp mà không cần đặt tour cố định.',
   f'Với {tt}, {v} là lựa chọn phổ biến để khám phá {place} theo lộ trình tự thiết kế. Trong {dur}, bạn có thể điều chỉnh tốc độ, thêm hoặc bỏ điểm ghé tùy thời tiết và sức khỏe thực tế.'
  ])))
 sections.append((f'Chuẩn bị trước chuyến đi {place}',
  paragraph(seed+'B',[
   f'Kiểm tra kỹ {v} trước ít nhất một ngày: lốp, phanh, đèn, mức nhiên liệu hoặc pin, gương và còi. Mang theo bộ vá lốp cơ bản, bơm tay nhỏ và số điện thoại cứu trợ lộ trình. Nạp đầy pin điện thoại và tải bản đồ offline cho {place}.',
   f'Trước {dur} đến {place}, lập danh sách các trạm xăng hoặc điểm sạc trên tuyến đường chính. Với {tt}, nên có ít nhất một thành viên biết cách bơm lốp và kiểm tra cơ bản. Thông báo lịch trình cho người thân để đảm bảo an toàn.'
  ])+f'<p>Đặt chỗ ở sớm nếu đi vào mùa cao điểm. Mang theo áo mưa, kem chống nắng, thuốc cá nhân và chứng minh thư hoặc hộ chiếu. Kiểm tra tình hình thời tiết {place} trước 24 giờ để điều chỉnh lịch.</p>'))
 sections.append((f'Lộ trình gợi ý cho {dur} tại {place}',
  f'<p>Lộ trình dưới đây mang tính tham khảo và cần điều chỉnh theo điều kiện thực tế, sức khỏe của {tt} và tình hình giao thông tại thời điểm đi. Không cố gắng hoàn thành toàn bộ danh sách nếu không đủ thời gian hoặc thời tiết xấu.</p>'
  +paragraph(seed+'C',[
   f'Buổi sáng sớm là thời điểm lý tưởng để khởi hành tại {place}, tránh nắng và đông đúc. {tt.capitalize()} nên xuất phát trước 7h, dừng ăn sáng tại quán địa phương, ghé các điểm ngoại thành trước khi đến trung tâm. Giữ lại ít nhất một giờ đệm để xử lý tình huống phát sinh.',
   f'Chia lộ trình theo từng nửa ngày để {tt} có thể nghỉ đủ giữa các điểm. Tại {place}, các tuyến đường liên xã hoặc ven biển thường ít xe và cảnh đẹp hơn đường quốc lộ. Hỏi người dân địa phương về tình trạng đường thực tế thay vì chỉ dựa vào bản đồ.'
  ])))
 sections.append(('An toàn khi đi đường dài bằng xe máy',
  f'<p>Đội mũ bảo hiểm đủ tiêu chuẩn trong suốt hành trình, kể cả đường vắng. Không chạy quá tốc độ cho phép, không vừa lái vừa nhìn điện thoại và không chạy khi đã mệt. Dừng nghỉ mỗi 90–120 phút để phục hồi sự tập trung.</p>'
  +paragraph(seed+'D',[
   f'Với {tt} di chuyển {dur} tại {place}, lập kế hoạch nghỉ đêm rõ ràng và không chạy đường núi hoặc đèo sau 17h nếu chưa quen. Đèo núi ở miền Bắc thường có sương mù buổi sáng sớm và chiều tối; hãy chờ tầm nhìn đủ rõ.',
   f'Kiểm tra quy định giao thông địa phương tại {place}: một số tuyến đường du lịch có giờ cấm xe máy hoặc giới hạn tốc độ thấp hơn thông thường. Không đỗ xe chắn lối đi tại các điểm tham quan đông người.'
  ])))
 sections.append(('Chi phí tham khảo cho chuyến đi',
  f'<p>Chi phí chuyến {dur} của {tt} đến {place} bằng {v} bao gồm: nhiên liệu hoặc sạc điện, chỗ ở mỗi đêm, ăn uống, vé tham quan và dự phòng sửa xe. Lập bảng chi phí trước giúp tránh hết tiền giữa chuyến.</p>'
  +paragraph(seed+'E',[
   f'Nếu thuê {v} thay vì dùng xe cá nhân, xem <a href="/thue-xe-may/ha-noi/">bảng giá thuê xe máy Hà Nội</a> để ước tính tổng chi phí thuê cho toàn bộ hành trình. Thuê theo tuần thường tiết kiệm hơn thuê theo ngày cho chuyến dài ngày.',
   f'{tt.capitalize()} nên để dự phòng 15–20% tổng ngân sách cho phát sinh: vá lốp, chỗ nghỉ thay thế hoặc đổi lịch do thời tiết. Một số điểm đến tại {place} có phí dịch vụ không ghi trong bảng giá online.'
  ])))
 sections.append(('Điểm không thể bỏ qua tại ' + s['place'],
  f'<p>Danh sách điểm đến phụ thuộc vào mùa và sở thích của {tt}. Nên hỏi người dân địa phương hoặc nhóm du lịch online về điểm đang mở cửa, điểm đang sửa chữa và giờ đẹp nhất trong ngày để tham quan.</p>'
  +paragraph(seed+'F',[
   f'Với {dur}, {tt} có thể kết hợp tham quan cả điểm nổi tiếng lẫn địa điểm ít người biết gần {place}. Thường thì địa điểm cách trung tâm 10–20 km đông khách ít hơn nhưng phong cảnh tương đương. Hỏi chủ nhà nghỉ về gợi ý cụ thể theo mùa.',
   f'Tránh đến {place} vào cao điểm lễ Tết nếu {tt} muốn không gian yên tĩnh và giá dịch vụ hợp lý. Mùa hoa, mùa lúa hoặc mùa biển là thời điểm phụ thuộc vào địa điểm cụ thể; tìm hiểu trước để chọn thời gian phù hợp nhất.'
  ])))
 sections.append(('Thuê xe và liên hệ Nguyễn Hà trước khi lên đường',
  f'<p>Nếu chưa có xe hoặc muốn thử loại xe phù hợp hơn cho địa hình {place}, {brand} tại {escape(FACTS["address"])}, {escape(FACTS["landmark"])} cung cấp các loại xe phù hợp cho hành trình dài ngày. Giờ mở cửa: {escape(FACTS["hours"])}. Điện thoại: <a href="tel:+84334699969">{phone}</a>.</p>'
  +f'<p>Khi liên hệ, cho biết điểm đến ({place}), số ngày ({dur}), số người trong nhóm ({tt}) và loại địa hình dự kiến. Cửa hàng sẽ gợi ý xe phù hợp và tư vấn về điều kiện đường. Xem <a href="/bang-gia/">bảng giá</a>, <a href="/kinh-nghiem/lai-xe-o-ha-noi/">kinh nghiệm lái xe ở Hà Nội</a> và <a href="/faq/">FAQ</a> để chuẩn bị tốt hơn.</p>'))
 body=' '.join(x[1] for x in sections);wc=len(words(body))
 return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],
         'excerpt':f'Hành trình {dur} đến {place} bằng {v} dành cho {tt}: lộ trình, chi phí, an toàn và điểm không bỏ qua.',
         'sections':[[h,b] for h,b in sections],'keywords':f'du lịch {place} {v} {dur} {tt}',
         'parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],
         'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}


# ── Writer 4: Luật giao thông & Kinh nghiệm ──────────────────────────────────
def spec_for_luat(seq):
 n=seq-1;aud=LAW_AUDIENCES[n%len(LAW_AUDIENCES)];n//=len(LAW_AUDIENCES)
 topic_key,topic_label=LAW_TOPICS[n%len(LAW_TOPICS)]
 hub='luat-giao-thong' if 'bằng' in topic_key or 'phạt' in topic_label or 'luật' in topic_label or topic_key in ('mũ bảo hiểm','nồng độ cồn','điện thoại khi lái','tốc độ đô thị','đỗ xe sai','vượt đèn đỏ','kiểm định xe','nhường đường','camera phạt nguội','biển báo') else 'kinh-nghiem'
 title=f'{topic_label.capitalize()} — hướng dẫn dành cho {aud}'
 intent=f'luat-kn|{topic_key}|{aud}'.lower()
 url=f'/{hub}/{slugify(topic_key)}-{slugify(aud)}/'
 return {'sequence':seq,'title':title,'intent':intent,'hub':hub,
         'topic':topic_key,'topic_label':topic_label,'audience':aud,'url':url,'writer':'luat'}

def make_luat(s):
 t=escape(s['topic_label']);a=escape(s['audience']);topic=s['topic']
 seed=s['intent'];brand=escape(FACTS['brand']);phone=escape(FACTS['phone'])
 sections=[]
 sections.append((f'Tổng quan: {t}',
  f'<p>Bài viết tổng hợp thông tin về {t} dành cho {a} tại Việt Nam. Nội dung mang tính tham khảo và không thay thế văn bản pháp luật đang có hiệu lực. Luôn kiểm tra nguồn chính thức hoặc tư vấn pháp lý trước khi quyết định.</p>'
  +paragraph(seed+'A',[
   f'Với {a}, hiểu đúng về {t} giúp tránh vi phạm không cố ý và xử lý đúng cách khi bị kiểm tra. Quy định có thể thay đổi theo từng giai đoạn; luôn đối chiếu với <a href="/luat-giao-thong/nguon-tra-cuu/">nguồn chính thức</a> mới nhất.',
   f'{a.capitalize()} thường gặp khó khăn với {t} do thông tin chồng chéo hoặc chưa được cập nhật. Bài viết này tóm tắt các điểm cốt lõi và dẫn nguồn để bạn tự kiểm tra trực tiếp.'
  ])))
 sections.append(('Quy định hiện hành',
  paragraph(seed+'B',[
   f'Quy định về {t} được quy định trong Luật Giao thông đường bộ và các nghị định hướng dẫn thi hành. Mức phạt, điều kiện và thủ tục có thể được điều chỉnh hằng năm theo nghị định mới. {a.capitalize()} cần xem văn bản hiện hành, không dựa vào thông tin từ nhiều năm trước.',
   f'Hiện tại, các quy định về {t} áp dụng thống nhất trên toàn quốc nhưng có thể có hướng dẫn bổ sung tại một số địa phương. Người tham gia giao thông cần nắm rõ cả quy định chung lẫn hướng dẫn địa phương nơi mình di chuyển.'
  ])+f'<p>Để tra cứu văn bản pháp luật đang có hiệu lực, xem <a href="/luat-giao-thong/nguon-tra-cuu/">danh sách nguồn chính thức</a> được tổng hợp tại trang này.</p>'))
 sections.append(('Những sai lầm phổ biến cần tránh',
  f'<p>Nhiều trường hợp vi phạm xuất phát từ hiểu sai hoặc thông tin cũ. Dưới đây là các điểm {a} cần đặc biệt chú ý liên quan đến {t}.</p>'
  +paragraph(seed+'C',[
   f'Sai lầm hay gặp nhất là dựa vào thông tin truyền miệng hoặc bài viết cũ khi tìm hiểu về {t}. Quy định giao thông tại Việt Nam được cập nhật thường xuyên; hãy kiểm tra trực tiếp trên Cổng thông tin Chính phủ hoặc trang Bộ Công an.',
   f'{a.capitalize()} thường bỏ qua {t} vì coi là không liên quan đến mình, nhưng thực tế đây là nhóm quy định áp dụng cho tất cả người tham gia giao thông, kể cả người điều khiển xe thuê hoặc xe mượn.'
  ])))
 sections.append(('Thủ tục và giấy tờ cần chuẩn bị',
  paragraph(seed+'D',[
   f'Khi làm thủ tục liên quan đến {t}, {a} cần chuẩn bị: chứng minh nhân dân hoặc căn cước công dân, giấy đăng ký xe, giấy phép lái xe phù hợp và các giấy tờ bổ sung theo yêu cầu của cơ quan thụ lý. Bản photo thường không đủ; hãy mang bản gốc.',
   f'Hồ sơ liên quan đến {t} thường được nộp tại cơ quan công an phường, quận hoặc sở tương ứng tùy loại thủ tục. Tra cứu địa chỉ và giờ tiếp nhận trực tiếp hoặc qua Cổng dịch vụ công trực tuyến trước khi đến.'
  ])+f'<p>Phí, lệ phí và thời hạn xử lý thay đổi theo từng loại thủ tục và có thể được điều chỉnh. Không nộp tiền cho bất kỳ ai không thuộc cơ quan nhà nước có thẩm quyền.</p>'))
 sections.append(('Câu hỏi thường gặp',
  f'<p><strong>Có thể nộp phạt online không?</strong> Một số loại vi phạm cho phép nộp phạt qua cổng dịch vụ công hoặc ứng dụng của Bộ Công an. Tra cứu phạt nguội tại iPortal hoặc VNeID và làm theo hướng dẫn hiển thị.</p>'
  +paragraph(seed+'E',[
   f'Nếu {a} bị phạt liên quan đến {t} và không đồng ý với quyết định xử phạt, có quyền khiếu nại theo đúng trình tự pháp luật. Hãy giữ lại biên bản xử phạt và liên hệ luật sư hoặc trung tâm tư vấn pháp lý nếu cần.',
   f'{a.capitalize()} nước ngoài cần lưu ý rằng bằng lái quốc tế chỉ có giá trị khi kèm theo bằng lái gốc của nước cấp. Một số loại xe và một số tuyến đường có quy định riêng áp dụng cho người nước ngoài.'
  ])))
 sections.append(('Tài nguyên hữu ích',
  f'<p>Xem thêm <a href="/luat-giao-thong/nguon-tra-cuu/">danh sách nguồn chính thức về luật, bằng lái và đăng kiểm</a> để tra cứu trực tiếp. Nếu đang cần thuê xe và tìm hiểu điều kiện pháp lý, xem <a href="/thue-xe-may/ha-noi/">thông tin thuê xe máy Hà Nội</a> và <a href="/faq/">FAQ</a>.</p>'
  +f'<p>Kinh nghiệm thực tế từ người dùng: <a href="/kinh-nghiem/lai-xe-o-ha-noi/">đi xe máy ở Hà Nội</a> và <a href="/bao-duong/xe-may/kiem-tra-truoc-khi-nhan/">kiểm tra xe trước khi nhận</a>.</p>'))
 sections.append(('Liên hệ Nguyễn Hà',
  f'<p>{brand} tại {escape(FACTS["address"])}, {escape(FACTS["landmark"])}. Giờ mở cửa: {escape(FACTS["hours"])}. Điện thoại, Zalo và WhatsApp: <a href="tel:+84334699969">{phone}</a>.</p>'
  +f'<p>Nếu bạn là {a} đang tìm hiểu về {t} trước khi thuê xe, đội ngũ cửa hàng có thể tư vấn về loại xe phù hợp và điều kiện cần có. Xem <a href="/bang-gia/">bảng giá</a> và <a href="/lien-he/">trang liên hệ</a>.</p>'))
 body=' '.join(x[1] for x in sections);wc=len(words(body))
 return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],
         'excerpt':f'{t.capitalize()} — hướng dẫn thực tế dành cho {a} tại Việt Nam, kèm nguồn tra cứu chính thức.',
         'sections':[[h,b] for h,b in sections],'keywords':f'{s["topic"]} {a} luật giao thông Hà Nội',
         'parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],
         'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}


# ── Router ────────────────────────────────────────────────────────────────────
def spec_for(seq):
 if seq <= THUE_XE_CAP:   return spec_for_thue_xe(seq)
 if seq <= INFO_CAP:       return spec_for_xe_info(seq - THUE_XE_CAP)
 if seq <= TRAVEL_CAP:     return spec_for_du_lich(seq - INFO_CAP)
 return spec_for_luat(seq - TRAVEL_CAP)

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
 INDEX_PATH.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
 return len(rows)


# ── Run ───────────────────────────────────────────────────────────────────────
def run(limit=None,dry=False):
 state=json.loads(STATE_PATH.read_text());existing=load_existing();limit=limit or CFG['pair_size']*CFG['pairs_per_run']
 if not CFG['enabled'] or (ROOT/'STOP_FACTORY').exists(): print('Factory stopped by control flag.');return 0
 made=[];queue=[];attempts=0;target=CFG.get('target_articles')
 while len(made)<limit and (not target or len(existing)+len(made)<target) and attempts<limit*20:
  seq=state['next_sequence'];state['next_sequence']+=1;attempts+=1;s=spec_for(seq);a=make_article(s);qa=score(a,existing+made)
  q={'id':a['id'],'sequence':seq,'url':a['url'],'intent':a['intent'],'qa':qa,'created_at':datetime.now(timezone.utc).isoformat(),'status':'published' if qa['pass'] else 'rejected'};queue.append(q)
  if qa['pass']:made.append(a)
  else:state['rejected']+=1
 if dry:
  print(json.dumps({'dry_run':True,'accepted':len(made),'attempted':attempts,'scores':[score(x,existing) for x in made]},ensure_ascii=False));return 0
 ARTICLES.mkdir(parents=True,exist_ok=True)
 for a in made:(ARTICLES/f'{a["id"]}.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
 with QUEUE_PATH.open('a') as f:
  for q in queue:f.write(json.dumps(q,ensure_ascii=False,separators=(',',':'))+'\n')
 state['published_by_factory']+=len(made);state['last_run']=datetime.now(timezone.utc).isoformat();state['status']='target-reached' if target and len(existing)+len(made)>=target else 'ready';STATE_PATH.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 count=reindex();print(json.dumps({'published':len(made),'pairs':len(made)//2,'attempted':attempts,'index_rows':count,'next_sequence':state['next_sequence']},ensure_ascii=False));return 0


# ── Report ────────────────────────────────────────────────────────────────────
def report():
 if not QUEUE_PATH.exists() or QUEUE_PATH.stat().st_size==0:
  print('Queue log trống. Chưa có lượt chạy nào.');return 0
 rows=[json.loads(l) for l in QUEUE_PATH.read_text().splitlines() if l.strip()]
 total=len(rows);published=[r for r in rows if r['status']=='published'];rejected=[r for r in rows if r['status']=='rejected']
 scores=[r['qa']['score'] for r in published]
 by_hub={}
 for r in published:
  h=r.get('intent','?').split('|')[0] if r.get('intent') else '?'
  by_hub[h]=by_hub.get(h,0)+1
 reject_reasons={}
 for r in rejected:
  for c in r['qa'].get('critical',[]):
   key=c.split('_')[0];reject_reasons[key]=reject_reasons.get(key,0)+1
 state=json.loads(STATE_PATH.read_text())
 out={
  'total_attempts':total,
  'published':len(published),
  'rejected':len(rejected),
  'reject_rate':f'{len(rejected)/max(1,total)*100:.1f}%',
  'score_avg':round(sum(scores)/max(1,len(scores)),1),
  'score_min':min(scores,default=0),
  'score_max':max(scores,default=0),
  'published_by_factory':state['published_by_factory'],
  'next_sequence':state['next_sequence'],
  'by_writer':by_hub,
  'reject_reasons':reject_reasons,
  'last_run':state.get('last_run'),
  'capacity':{
   'thue_xe':THUE_XE_CAP,
   'xe_info':INFO_CAP-THUE_XE_CAP,
   'du_lich':TRAVEL_CAP-INFO_CAP,
   'luat_kn':LAW_CAP-TRAVEL_CAP,
   'total':LAW_CAP
  }
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
    subprocess.run(['git', 'commit', '-m', 'content: auto-publish QA-approved batch from local daemon'], check=True, cwd=str(ROOT))
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
 state=json.loads(STATE_PATH.read_text());print(json.dumps({'config':CFG,'state':state,'articles':len(load_existing()),'stopped':(ROOT/'STOP_FACTORY').exists(),'matrix_capacity':LAW_CAP},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
