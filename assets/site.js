/* Nguyễn Hà Journal — no external API or language model. Answers use local content only. */
(() => {
'use strict';
const $=id=>document.getElementById(id), root=document.documentElement;
const icons={sun:'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/></svg>',moon:'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15.5A9 9 0 0 1 8.5 4 9 9 0 1 0 20 15.5Z"/></svg>'};
function themeLabel(){const dark=root.dataset.theme==='dark';$('theme-toggle').innerHTML=icons[dark?'sun':'moon'];$('theme-toggle').setAttribute('aria-label','Chuyển sang chế độ '+(dark?'sáng':'tối'));}
themeLabel();$('theme-toggle').onclick=()=>{root.dataset.theme=root.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem('nguyenha-theme',root.dataset.theme)}catch{}themeLabel()};
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',e=>{let saved=false;try{saved=!!localStorage.getItem('nguyenha-theme')}catch{}if(!saved){root.dataset.theme=e.matches?'dark':'light';themeLabel()}});
const panels=[['site-menu','menu-toggle'],['chat-panel','chat-toggle'],['quick-links','call-toggle']];
function togglePanel(id,show,focus=true){const item=panels.find(p=>p[0]===id);if(!item)return;const node=$(id);if(show===undefined)show=node.hidden;
 if(show)panels.filter(p=>p[0]!==id).forEach(p=>togglePanel(p[0],false,false));
 node.hidden=!show;$(item[1]).setAttribute('aria-expanded',String(show));
 if(id==='site-menu'){$('menu-backdrop').hidden=!show;document.body.style.overflow=show?'hidden':'';if(show&&focus)$('menu-close').focus()}
 if(id==='chat-panel'&&show){openChat();if(focus)$('chat-input').focus()}
 if(!show&&focus)$(item[1]).focus();
}
$('menu-toggle').onclick=()=>togglePanel('site-menu');$('menu-close').onclick=()=>togglePanel('site-menu',false);$('menu-backdrop').onclick=()=>togglePanel('site-menu',false);
$('chat-toggle').onclick=()=>togglePanel('chat-panel');$('chat-close').onclick=()=>togglePanel('chat-panel',false);$('call-toggle').onclick=()=>togglePanel('quick-links');
if($('back-to-top'))$('back-to-top').onclick=()=>window.scrollTo({top:0,behavior:'smooth'});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){const p=panels.find(p=>!$(p[0]).hidden);if(p){togglePanel(p[0],false);e.preventDefault()}}
 if(e.key==='Tab'&&!$('site-menu').hidden){const nodes=[...$('site-menu').querySelectorAll('button,a,summary')].filter(x=>x.getClientRects().length);if(e.shiftKey&&document.activeElement===nodes[0]){nodes.at(-1).focus();e.preventDefault()}else if(!e.shiftKey&&document.activeElement===nodes.at(-1)){nodes[0].focus();e.preventDefault()}}
});
document.addEventListener('click',e=>{if(!$('quick-links').hidden&&!$('quick-links').contains(e.target)&&!$('call-toggle').contains(e.target))togglePanel('quick-links',false,false)});
const normalize=t=>String(t).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/[^a-z0-9\s]/g,' ').replace(/\s+/g,' ').trim();
const stops=new Set('toi ban minh cho cua va la co khong duoc thi o tai ve mot nhung cac nay kia muon hoi gi voi xin hay de nhu the bao nhieu lam nao'.split(' '));
const terms=t=>normalize(t).split(' ').filter(w=>w&&!stops.has(w));
let docs=[], site={}, initialized=false, indexPromise=null, busy=false, context={topic:'',hub:''};
const hubAliases=[['50cc',/50\s?cc|khong (can )?bang|no license/],['xe điện',/xe dien|electric|pin|sac/],['xe ga',/xe ga|vision|lead|air blade|scooter/],['xe số',/xe so|wave|sirius|blade/],['du lịch Hà Nội',/du lich|tham quan|ho tay|ho guom|hoan kiem|pho co|travel/]];
function sameOriginPath(raw){try{const u=new URL(raw,location.origin);return u.origin===location.origin?u.pathname+u.hash:null}catch{return null}}
function message(text,links=[],user=false){const box=document.createElement('div');box.className='message'+(user?' user':'');box.append(document.createTextNode(text));
 for(const doc of links.slice(0,3)){const path=sameOriginPath(doc.url);if(!path)continue;const a=document.createElement('a');a.href=path;a.textContent=doc.title||doc.heading;box.append(a)}
 $('chat-messages').append(box);$('chat-messages').scrollTop=$('chat-messages').scrollHeight;return box;
}
function suggested(){const box=document.createElement('div');box.className='suggestions';['Giá thuê 50cc','Thuê theo tháng','Địa chỉ cửa hàng','Khám phá Phố Cổ'].forEach(q=>{const b=document.createElement('button');b.type='button';b.textContent=q;b.onclick=()=>ask(q);box.append(b)});$('chat-messages').append(box)}
async function fetchTimed(url,type='json',timeout=8000){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeout);try{const r=await fetch(url,{signal:controller.signal,cache:'no-cache'});if(!r.ok)throw Error('HTTP '+r.status);return type==='json'?await r.json():await r.text()}finally{clearTimeout(timer)}}
function parseDoc(html,url){const dom=new DOMParser().parseFromString(html,'text/html');const a=dom.querySelector('article.article-body');if(!a)return null;return {url,title:dom.querySelector('h1')?.textContent?.trim()||'Bài viết',hub:'',excerpt:dom.querySelector('meta[name="description"]')?.content||'',keywords:'',text:a.textContent.replace(/\s+/g,' ').trim(),sections:[...a.querySelectorAll('section,details.faq-item')].map(s=>({heading:s.querySelector('h2,summary')?.textContent||'',text:s.textContent.replace(/\s+/g,' ').trim(),url:url+'#'+s.id}))}}
function currentDoc(){const a=document.querySelector('article.article-body');return a?parseDoc(document.documentElement.outerHTML,location.pathname):null}
function validDocs(input){return Array.isArray(input)?input.filter(d=>d&&typeof d.title==='string'&&typeof d.text==='string'&&sameOriginPath(d.url)).map(d=>({...d,url:sameOriginPath(d.url),sections:Array.isArray(d.sections)?d.sections:[]})):[]}
async function loadIndex(force=false){if(indexPromise&&!force)return indexPromise;indexPromise=(async()=>{try{const data=await fetchTimed('/assets/search-index.json');const incoming=validDocs(data.documents);if(!incoming.length)throw Error('empty');docs=incoming;site=data.site||{};const current=currentDoc();if(current)docs=docs.filter(d=>d.url!==current.url).concat(current);return true}catch{const current=currentDoc();if(!docs.length&&current)docs=[current];return false}})();return indexPromise}
async function openChat(){if(initialized)return;initialized=true;message('Chào bạn! Tôi có thể tìm thông tin thuê xe, bảng giá và bài viết trên blog Nguyễn Hà. Bạn muốn hỏi điều gì?');suggested();await loadIndex()}
function expand(q){return q.replace(/motorbike|motorcycle|bike rental/g,'thue xe may').replace(/monthly|month/g,'thang').replace(/weekly|week/g,'tuan').replace(/daily|day/g,'ngay').replace(/price|cost/g,'gia').replace(/deposit/g,'coc').replace(/address|location/g,'dia chi').replace(/opening hours|open time/g,'gio mo cua').replace(/electric/g,'xe dien').replace(/scooter/g,'xe ga');}
function search(query){const q=expand(normalize(query));const words=[...new Set(terms(q))];if(!words.length)return [];
 const prepared=docs.map(d=>({d,body:terms(d.text+' '+d.excerpt+' '+d.keywords),title:terms(d.title),flat:normalize(d.title+' '+d.keywords)}));const avg=prepared.reduce((n,p)=>n+p.body.length,0)/Math.max(1,prepared.length);
 const df=new Map(words.map(w=>[w,prepared.filter(p=>p.body.includes(w)||p.title.includes(w)).length]));
 return prepared.map(p=>{let score=0,hits=0;for(const w of words){const tf=p.body.filter(t=>t===w).length+4*p.title.filter(t=>t===w).length;if(!tf)continue;hits++;const idf=Math.log(1+(prepared.length-(df.get(w)||0)+.5)/((df.get(w)||0)+.5));score+=idf*(tf*2.2)/(tf+1.2*(.25+.75*p.body.length/Math.max(1,avg)))}
  for(let i=0;i<words.length-1;i++)if(p.flat.includes(words[i]+' '+words[i+1]))score+=2;
  if(context.hub&&p.d.hub===context.hub)score+=.3;return {...p.d,score:score*(.3+.7*hits/words.length),coverage:hits/words.length}}).filter(p=>p.score>.55&&p.coverage>=.34).sort((a,b)=>b.score-a.score).slice(0,3);
}
function find(url){return docs.find(d=>d.url===url)}
function section(url,regex){const d=find(url);const s=d?.sections.find(s=>regex.test(normalize(s.heading)));return s?{text:s.text.replace(/\s+/g,' ').trim(),links:[{title:s.heading,url:s.url}]}:null}
function answer(question){let q=expand(normalize(question));
 if(/^(chao|hello|hi|xin chao|hey|cam on|thanks)( ban)?$/.test(q))return {text:/cam on|thanks/.test(q)?'Rất vui được hỗ trợ bạn. Bạn cần tìm thêm bài viết hoặc thông tin thuê xe nào?':'Chào bạn! Bạn muốn xem giá thuê, tìm địa chỉ cửa hàng hay đọc cẩm nang Hà Nội?',links:[]};
 if(/xe dien.*50\s?cc|50\s?cc.*xe dien/.test(q)){const s=section('/thue-xe-dien/ha-noi/',/lam ro/);if(s)return s}
 const topic=hubAliases.find(([,r])=>r.test(q));if(topic)context.topic=topic[0];
 const followup=/^(con|the|vay|the con|gia|bao nhieu|tuan|thang|ngay)/.test(q)&&q.length<80;
 const currentTopic=topic?.[0]||(followup?context.topic:'');
 const contact=find('/lien-he/'),price=find('/bang-gia/'),rental=find('/thue-xe-may/ha-noi/');
 if(/dia chi|o dau|lien he|so dien thoai|hotline|zalo|whatsapp|email|gio mo|gio dong|may gio|mo cua/.test(q)){
  if(contact&&site.address)return {text:`${site.name}\nĐịa chỉ: ${site.address}\nGiờ mở cửa: ${site.hours}\nĐiện thoại / Zalo / WhatsApp: ${site.phone}\nEmail: ${site.email}`,links:[contact]};
 }
 if(/san bay|noi bai|giao xe|giao tan|nhan xe|ship|delivery|airport/.test(q)){const s=section('/thue-xe-may/ha-noi/',/giao xe/);if(s)return s}
 if(/coc|ho chieu|passport|giay to|thanh toan|payment|chuyen khoan/.test(q)){const s=section('/thue-xe-may/ha-noi/',/giay to/);if(s)return s}
 if(/tra som|hoan tien|qua gio|tre|tinh gio|tinh ngay|nua ngay|12 gio|1 gio/.test(q)){const s=section('/bang-gia/',/thoi gian/);if(s)return s}
 if(/gia|tien thue|bao nhieu|chi phi/.test(q)||(/^(con|the|vay|the con)/.test(q)&&/tuan|thang|ngay/.test(q))){
  const url=currentTopic==='50cc'?'/thue-xe-50cc/ha-noi/':currentTopic==='xe điện'?'/thue-xe-dien/ha-noi/':'/bang-gia/';
  let s=section(url,/gia/);if(s){context.hub='thue-xe';if(url==='/bang-gia/'&&price)return {text:currentTopic==='xe số'?'Xe số: 150–200 nghìn đồng/ngày; 700–800 nghìn đồng/tuần; 1–1,2 triệu đồng/tháng. Xác nhận giá theo xe còn sẵn với cửa hàng.':currentTopic==='xe ga'?'Xe ga: 150–200 nghìn đồng/ngày; 600 nghìn–1 triệu đồng/tuần; 1,2–2 triệu đồng/tháng. Xác nhận giá theo xe còn sẵn với cửa hàng.':'Xe số: 150–200 nghìn/ngày · 700–800 nghìn/tuần · 1–1,2 triệu/tháng.\nXe ga: 150–200 nghìn/ngày · 600 nghìn–1 triệu/tuần · 1,2–2 triệu/tháng.\nXe điện: ngày tùy mẫu · 600–800 nghìn/tuần · 1,5–1,8 triệu/tháng.\n50cc: 200 nghìn/ngày · 1 triệu/tuần · 2 triệu/tháng.\nĐơn vị: đồng. Tiền cọc được tính riêng.',links:[price]};return s}
 }
 if(/bang lai|giay phep|bao nhieu tuoi|luat|toc do|km h/.test(q)){const d=find('/luat-giao-thong/nguon-tra-cuu/');if(d)return {text:'Yêu cầu giấy phép và độ tuổi phụ thuộc đúng loại phương tiện và quy định đang có hiệu lực. Blog có hướng dẫn tra cứu nguồn chính thức; tôi chưa đủ dữ liệu để kết luận pháp lý cho trường hợp của bạn. Hãy đọc hướng dẫn và xác nhận trước khi lái.',links:[d,...(find('/thue-xe-50cc/ha-noi/')?[find('/thue-xe-50cc/ha-noi/')]:[])]}}
 if(/con xe|co xe|dat xe|book|available|vinfast|honda dien/.test(q)&&/con xe|dat xe|book|available|vinfast|honda dien/.test(q))return {text:'Blog không có dữ liệu tồn xe theo thời gian thực và không xác nhận đặt xe. Bạn hãy gọi hoặc nhắn 0334 699 969, cho biết loại xe và thời gian muốn thuê.',links:contact?[contact]:[]};
 if(/50\s?cc/.test(q)&&/co may|bao nhieu chiec|con khong/.test(q)){const s=section('/thue-xe-50cc/ha-noi/',/tai nguyen ha/);if(s)return s}
 const results=search(q+(followup&&currentTopic?' '+currentTopic:''));if(!results.length)return {text:'Tôi chưa tìm thấy thông tin đủ phù hợp trong blog. Bạn có thể hỏi cụ thể hơn về thuê xe, mẫu xe hoặc địa điểm Hà Nội; để xác nhận dịch vụ, liên hệ 0334 699 969.',links:contact?[contact]:[]};
 const top=results[0];context.hub=top.hub;const queryTerms=terms(q);const sections=top.sections.map(s=>({...s,score:terms(s.heading+' '+s.text).filter(t=>queryTerms.includes(t)).length})).sort((a,b)=>b.score-a.score);
 const snippet=(sections[0]?.score>0?sections[0].text:top.excerpt).replace(/\s+/g,' ').trim();
 return {text:snippet.length>620?snippet.slice(0,620).replace(/\s+\S*$/,'')+'…':snippet,links:results};
}
async function ask(question){question=String(question).trim().slice(0,500);if(!question||busy)return;busy=true;$('chat-input').value='';$('chat-form').querySelector('button').disabled=true;message(question,[],true);const wait=message('Đang tìm trong blog…');
 try{const ready=await loadIndex();if(!ready&&!docs.length){wait.remove();message('Tôi chưa đọc được dữ liệu blog. Bạn hãy thử nút làm mới hoặc liên hệ 0334 699 969.');return}const result=answer(question);wait.remove();message(result.text,result.links)}catch{wait.remove();message('Tôi chưa đọc được dữ liệu blog. Bạn hãy thử lại hoặc liên hệ 0334 699 969.')}finally{busy=false;$('chat-form').querySelector('button').disabled=false;$('chat-input').focus()}}
$('chat-form').addEventListener('submit',e=>{e.preventDefault();ask($('chat-input').value)});
// Refresh existing and newly published article pages from this origin's sitemap.
$('chat-refresh').onclick=async()=>{const b=$('chat-refresh');if(busy||b.disabled)return;b.disabled=true;try{const ok=await loadIndex(true);const xml=await fetchTimed('/sitemap.xml','text');const parsed=new DOMParser().parseFromString(xml,'application/xml');if(parsed.querySelector('parsererror'))throw Error('sitemap');
 const paths=[...parsed.querySelectorAll('loc')].map(n=>{try{const u=new URL(n.textContent);if(u.origin===location.origin||u.origin===site.url)return u.pathname}catch{}return null}).filter(Boolean).filter(x=>!['/','/lien-he/'].includes(x));const unique=[...new Set(paths)].slice(0,40);let count=0;const queue=[...unique];
 await Promise.all(Array.from({length:3},async()=>{while(queue.length){const url=queue.shift();try{const html=await fetchTimed(url,'text',5000);const d=parseDoc(html,url);if(d){const old=find(url);if(old){d.hub=old.hub;d.keywords=old.keywords}docs=docs.filter(x=>x.url!==url).concat(d);count++}}catch{}}}));
 message(count?`Đã đọc lại ${count} bài viết từ blog. Bạn muốn tìm nội dung nào?`:ok?'Đã cập nhật chỉ mục blog. Chưa đọc được thêm bài trực tiếp.':'Chưa cập nhật được dữ liệu. Bạn có thể thử lại khi kết nối ổn định.');
 }catch{message('Chưa cập nhật được dữ liệu blog. Tôi sẽ tiếp tục dùng nội dung đã đọc.')}finally{b.disabled=false}};
})();
