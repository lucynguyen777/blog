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


def slugify(s):
 s=unicodedata.normalize('NFD',s.lower());s=''.join(c for c in s if unicodedata.category(c)!='Mn').replace('đ','d')
 return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',s)).strip('-')

def words(html): return re.findall(r"[\wÀ-ỹ]+",re.sub(r'<[^>]+>',' ',html),re.UNICODE)
def grams(text,n=5):
 t=[x.lower() for x in words(text)];return set(tuple(t[i:i+n]) for i in range(max(0,len(t)-n+1)))
def similarity(a,b):
 x,y=grams(a),grams(b)
 return len(x&y)/max(1,len(x|y))
def load_existing():
 out=json.loads(LEGACY.read_text()) if LEGACY.exists() else []
 for p in sorted(ARTICLES.glob('*.json')):
  try: out.append(json.loads(p.read_text()))
  except Exception: pass
 return out

def spec_for(seq):
 # Mixed-radix enumeration gives stable, collision-free combinations.
 n=seq-1;angle=ANGLES[n%len(ANGLES)];n//=len(ANGLES);aud=AUDIENCES[n%len(AUDIENCES)];n//=len(AUDIENCES);vehicle,hub=VEHICLES[n%len(VEHICLES)];n//=len(VEHICLES);district=DISTRICTS[n%len(DISTRICTS)];n//=len(DISTRICTS);context=CONTEXTS[n%len(CONTEXTS)];n//=len(CONTEXTS);route=ROUTE_NEEDS[n%len(ROUTE_NEEDS)]
 title=f'{vehicle.capitalize()} ở {district}: {angle[0]} khi {context}, {route}'
 intent='|'.join([angle[0],vehicle,district,aud,context,route]).lower()
 url=f'/{hub}/{slugify(district)}/{slugify(vehicle)}/{slugify(angle[0])}-{slugify(aud)}-{slugify(context)}-{slugify(route)}/'
 return {'sequence':seq,'title':title,'intent':intent,'vehicle':vehicle,'hub':hub,'district':district,'audience':aud,'context':context,'route':route,'angle':angle[0],'angle_label':angle[1],'url':url}

def paragraph(seed,variants): return '<p>'+variants[int(hashlib.sha256(seed.encode()).hexdigest(),16)%len(variants)]+'</p>'
def make_article(s):
 v=escape(s['vehicle']);d=escape(s['district']);a=escape(s['audience']);ang=escape(s['angle_label']);context=escape(s['context']);route=escape(s['route'])
 price=FACTS['prices'].get(s['vehicle'],FACTS['prices'].get('xe ga' if 'Vision' in v or 'Air Blade' in v else 'xe số'))
 seed=s['intent']; brand=escape(FACTS['brand']); phone=escape(FACTS['phone'])
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
 sections.append(('Checklist kiểm tra trước khi nhận',f'<p>Kiểm tra phanh trước và sau, lốp, đèn, còi, gương, khóa, đồng hồ và mức nhiên liệu hoặc pin. Chụp biển số, các vết xước và phụ kiện khi hai bên cùng có mặt. Nếu có điểm bất thường, ghi vào biên bản giao nhận trước khi ký.</p><p>Khởi động và nghe tiếng máy của {v}; thử ga và phanh ở tốc độ thấp trong khu vực cho phép. Xác nhận mũ bảo hiểm, chìa khóa và vật dụng đi kèm. Với xe điện, cần hỏi đúng bộ sạc, cách sạc và phạm vi sử dụng của mẫu xe; không dùng một con số chung cho mọi pin.</p>'))
 sections.append(('Đối chiếu giá và tổng ngân sách',f'<p>Mức tham khảo hiện hành cho nhóm phù hợp là {escape(price)}. Giá chiếc {v} cụ thể còn phụ thuộc xe sẵn có và thời hạn thuê. Ngoài tiền thuê, cần chuẩn bị tiền cọc theo thỏa thuận, phí giao nhận nếu áp dụng, nhiên liệu và khoản phát sinh được ghi trong hợp đồng.</p><p>Hãy yêu cầu cửa hàng chốt bằng văn bản: thời điểm bắt đầu, thời điểm trả, tổng tiền thuê, tiền cọc và điều kiện hoàn cọc. Không so sánh chỉ bằng giá ngày nếu nhu cầu thực tế là theo tuần hoặc tháng. Xem thêm <a href="/bang-gia/">bảng giá đang áp dụng</a> trước khi quyết định.</p>'))
 sections.append(('Đọc hợp đồng và giấy tờ',f'<p>Đối chiếu họ tên, thông tin chiếc xe, biển số, kỳ thuê, giờ trả và hiện trạng. Đọc phần trách nhiệm khi hư hỏng, trả sớm, quá giờ và mất phụ kiện. Chỉ ký khi nội dung trùng với trao đổi; giữ một bản hoặc ảnh rõ ràng để tra cứu trong thời gian sử dụng.</p><p>Người lái phải đáp ứng điều kiện độ tuổi và giấy phép phù hợp với đúng loại phương tiện. Khi chưa chắc yêu cầu pháp lý cho {v}, hãy kiểm tra nguồn chính thức và mục <a href="/luat-giao-thong/nguon-tra-cuu/">hướng dẫn tra cứu luật, bằng lái</a>. Bài blog không thay thế văn bản đang có hiệu lực.</p>'))
 sections.append(('Tổ chức giao nhận và thời điểm trả',f'<p>Thuê ngắn hạn nhận xe tại cửa hàng. Việc giao xe cho kỳ nhiều ngày, tuần hoặc tháng cần được thống nhất trước; cửa hàng không giao nhận tại sân bay Nội Bài. Ghi rõ địa điểm tại {d}, người bàn giao và số điện thoại liên hệ để tránh chờ hoặc nhầm điểm.</p><p>Một ngày thuê được tính theo 24 giờ ghi trong hợp đồng. Hãy đặt nhắc lịch trước giờ trả và dự trù thời gian di chuyển. Khi cần thay đổi kế hoạch, liên hệ sớm thay vì tự suy đoán cách tính phí.</p>'))
 sections.append(('Sử dụng xe trong suốt kỳ thuê',paragraph(seed+'7',[
 f'Mỗi ngày trước khi đi, quan sát nhanh lốp, phanh, đèn và dấu hiệu rò rỉ hoặc bất thường. Nếu {v} phát tiếng lạ, rung khác thường hay cảnh báo, dừng ở nơi an toàn rồi liên hệ cửa hàng; không tự sửa lớn hoặc thay phụ tùng khi chưa thống nhất.',
 f'Giữ chìa khóa và giấy tờ theo hướng dẫn, khóa xe tại nơi phù hợp và tránh để tài sản có giá trị trên xe. Trong lịch đi của {a} tại {d}, nên lưu sẵn số hỗ trợ để xử lý nhanh nếu phương tiện có dấu hiệu bất thường.'
 ])+f'<p>Không chở quá nhu cầu đã trao đổi, không giao xe cho người không có trong thỏa thuận và tuân thủ biển báo tại thời điểm thực tế. Mọi chi phí do hư hỏng cần được hai bên đối chiếu theo hợp đồng và hiện trạng đã ghi nhận.</p>'))
 sections.append(('Hoàn tất trả xe minh bạch',f'<p>Khi trả {v}, hai bên cùng kiểm tra biển số, đồng hồ, nhiên liệu hoặc pin, vết xước và phụ kiện. Đối chiếu ảnh lúc nhận để tách tình trạng có sẵn khỏi vấn đề mới. Yêu cầu xác nhận đã nhận đủ xe, chìa khóa và đồ đi kèm.</p><p>Nếu có khoản phát sinh, đề nghị giải thích theo điều khoản đã ký. Kiểm tra việc hoàn cọc trước khi rời điểm giao nhận. Lưu ảnh biên bản hoặc tin nhắn xác nhận cho đến khi giao dịch kết thúc hoàn toàn.</p>'))
 sections.append(('Liên hệ và xác nhận xe còn sẵn',f'<p>{brand} ở {escape(FACTS["address"])}, {escape(FACTS["landmark"])}. Giờ mở cửa: {escape(FACTS["hours"])}. Điện thoại, Zalo và WhatsApp: <a href="tel:+84334699969">{phone}</a>.</p><p>Khi liên hệ, hãy gửi bốn thông tin: loại xe muốn thử, thời gian thuê, khu vực nhận tại {d} và nhu cầu của {a}. Cửa hàng sẽ xác nhận xe thực tế, mức cọc và điều kiện giao nhận. Xem <a href="/faq/">câu hỏi thường gặp</a> hoặc <a href="/lien-he/">trang liên hệ</a> để chuẩn bị trước.</p>'))
 body=' '.join(x[1] for x in sections); wc=len(words(body))
 return {'id':f'NH-{s["sequence"]:05d}','url':s['url'],'title':s['title'],'hub':s['hub'],'excerpt':f'{s["angle_label"].capitalize()} cho {s["vehicle"]} tại {s["district"]}, gồm kiểm tra xe, chi phí, hợp đồng, giao nhận và cách liên hệ Nguyễn Hà.','sections':[[h,b] for h,b in sections],'keywords':f'{s["angle"]} {s["vehicle"]} {s["district"]} {s["audience"]}','parent':HUB_PARENT[s['hub']],'kind':'article','art':f'{s["sequence"]:05d}','tone':['gold','black','white'][s['sequence']%3],'wordCount':wc,'intent':s['intent'],'factoryVersion':CFG['version']}

def score(article,existing):
 html=' '.join(b for _,b in article['sections']);wc=len(words(html));critical=[];points=0;details={}
 def add(name,value,maxv):
  nonlocal points;points+=value;details[name]={'score':value,'max':maxv}
 add('metadata',15 if 35<=len(article['title'])<=120 and 100<=len(article['excerpt'])<=170 else 8,15)
 add('structure',20 if len(article['sections'])>=8 and all(h and '<p>' in b for h,b in article['sections']) else 8,20)
 add('depth',25 if CFG['minimum_words']<=wc<=CFG['maximum_words'] else (12 if wc>=700 else 0),25)
 links=len(re.findall(r'href="/',html));add('internal_links',15 if links>=4 else links*3,15)
 fact_terms=sum(x in html for x in [FACTS['phone'],FACTS['hours'],FACTS['address']]);add('facts',10 if fact_terms==3 else fact_terms*3,10)
 maxsim=max((similarity(html,' '.join(b for _,b in p.get('sections',[]))) for p in existing),default=0);add('uniqueness',15 if maxsim<=CFG['maximum_similarity'] else 0,15)
 urls={p['url'] for p in existing};intents={p.get('intent') for p in existing}
 if article['url'] in urls: critical.append('duplicate_url')
 if article['intent'] in intents: critical.append('duplicate_intent')
 if maxsim>CFG['maximum_similarity']:critical.append(f'similarity_{maxsim:.3f}')
 if wc<CFG['minimum_words']:critical.append(f'thin_{wc}_words')
 return {'score':points,'pass':points>=CFG['minimum_score'] and not critical,'critical':critical,'details':details,'word_count':wc,'max_similarity':round(maxsim,4)}

def reindex():
 rows=[]
 for p in load_existing():
  if p.get('kind') in ('hub','page'):continue
  text=' '.join(re.sub(r'<[^>]+>',' ',b) for _,b in p.get('sections',[]))
  rows.append({'id':p.get('id'),'url':p['url'],'title':p['title'],'hub':p['hub'],'parent':p.get('parent'),'intent':p.get('intent'),'word_count':p.get('wordCount',len(words(text))),'sha256':hashlib.sha256(text.encode()).hexdigest(),'status':'published'})
 INDEX_PATH.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
 return len(rows)

def run(limit=None,dry=False):
 state=json.loads(STATE_PATH.read_text());existing=load_existing();limit=limit or CFG['pair_size']*CFG['pairs_per_run']
 if not CFG['enabled'] or (ROOT/'STOP_FACTORY').exists(): print('Factory stopped by control flag.');return 0
 made=[];queue=[];attempts=0
 while len(made)<limit and len(existing)+len(made)<CFG['target_articles'] and attempts<limit*20:
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
 state['published_by_factory']+=len(made);state['last_run']=datetime.now(timezone.utc).isoformat();state['status']='target-reached' if len(existing)+len(made)>=CFG['target_articles'] else 'ready';STATE_PATH.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 count=reindex();print(json.dumps({'published':len(made),'pairs':len(made)//2,'attempted':attempts,'index_rows':count,'next_sequence':state['next_sequence']},ensure_ascii=False));return 0

def main():
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
 r=sp.add_parser('run');r.add_argument('--limit',type=int);r.add_argument('--dry-run',action='store_true')
 sp.add_parser('reindex');sp.add_parser('status')
 a=ap.parse_args()
 if a.cmd=='run':return run(a.limit,a.dry_run)
 if a.cmd=='reindex':print(json.dumps({'index_rows':reindex()}));return 0
 state=json.loads(STATE_PATH.read_text());print(json.dumps({'config':CFG,'state':state,'articles':len(load_existing()),'stopped':(ROOT/'STOP_FACTORY').exists()},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
