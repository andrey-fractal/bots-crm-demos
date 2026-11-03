"""Веб-стенд для трёх демо: та же логика, что в Telegram-ботах, но без токенов. Запуск: uvicorn playground:app --port 8000"""
import asyncio

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from crm_notify import server as crm
from crm_notify.events import parse_amo, parse_bitrix
from leads_bot.amocrm import LocalCRM, manager_text
from leads_bot.core import LeadDialog
from support_bot.core import SupportBot

app = FastAPI()
support = SupportBot()
local_crm = LocalCRM()
dialogs: dict[str, LeadDialog] = {}
manager_inbox: list[str] = []

SAMPLES = {
    "amo_add": ("amo", "leads[add][0][id]=24101&leads[add][0][name]=Офис на Тверской, 12 бутылей в неделю&leads[add][0][price]=42000"
                       "&leads[add][0][responsible_user_id]=8812345&account[subdomain]=rodnik"),
    "amo_status": ("amo", "leads[status][0][id]=24087&leads[status][0][name]=Кафе «Север»&leads[status][0][price]=18500"
                          "&leads[status][0][status_id]=61523&leads[status][0][responsible_user_id]=8812345&account[subdomain]=rodnik"),
    "bitrix_add": ("bitrix", "event=ONCRMDEALADD&data[FIELDS][ID]=512&auth[domain]=rodnik.bitrix24.ru"),
}


class Msg(BaseModel):
    text: str
    sid: str = "web"


@app.post("/api/support")
async def api_support(m: Msg):
    a = await asyncio.to_thread(support.ask, m.text, m.sid)
    op = f"Обращение #{a.ticket_id}\nКлиент: {m.sid}\n«{m.text}»" if a.handoff else None
    return {"text": a.text, "sources": a.sources[:1], "handoff": a.handoff, "operator": op}


@app.post("/api/crm/{sample}")
def api_crm(sample: str):
    kind, body = SAMPLES[sample]
    crm.SEEN.clear()
    events = parse_amo(body, crm.AMO_STAGES, crm.AMO_USERS) if kind == "amo" else parse_bitrix(body, crm.bitrix_deal)
    crm.handle(events)
    return {"outbox": crm.OUTBOX}


@app.post("/api/leads")
def api_leads(m: Msg):
    def submit(lead):
        lead_id = local_crm.create_lead(lead)
        manager_inbox.append(manager_text(lead_id, lead))
        return lead_id

    r = dialogs.setdefault(m.sid, LeadDialog(submit)).handle(m.text)
    return {"text": r.text, "buttons": r.buttons, "manager": manager_inbox}


@app.get("/{page}", response_class=HTMLResponse)
def page(page: str):
    return (PAGE.replace("__PAGE__", page if page in ("support", "crm", "leads") else "support"))


PAGE = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Демо-стенд</title>
<style>
body{margin:0;font:15px/1.4 "Segoe UI",system-ui,sans-serif;background:#e7ebf0;color:#111;padding:28px}#app{display:flex;gap:32px;justify-content:center;align-items:flex-start}
.col{display:flex;flex-direction:column;gap:10px}.cap{font-weight:600;color:#475569;font-size:14px;padding-left:4px}
.phone{width:400px;height:680px;background:#fff;border-radius:22px;box-shadow:0 8px 30px #0002;display:flex;flex-direction:column;overflow:hidden}
.top{background:#517da2;color:#fff;padding:14px 18px;display:flex;gap:12px;align-items:center}
.ava{width:38px;height:38px;border-radius:50%;background:#7fb1dd;display:flex;align-items:center;justify-content:center;font-weight:700}
.top b{display:block}.top small{opacity:.8}
.chat{flex:1;scrollbar-width:none;overflow-y:auto;padding:14px;background:#cfdfc2 linear-gradient(#d6e5c8,#c4d8b4);display:flex;flex-direction:column;gap:8px}
.m{max-width:82%;padding:8px 12px;border-radius:14px;white-space:pre-wrap;box-shadow:0 1px 1px #0002}
.in{background:#fff;align-self:flex-start;border-bottom-left-radius:4px}.out{background:#e1fec6;align-self:flex-end;border-bottom-right-radius:4px}
.src{font-size:12px;color:#5b7a99;margin-top:4px}.m a{color:#2b6cb0}
.kb{display:flex;flex-direction:column;gap:6px;padding:8px;background:#f1f3f5}.kb button{border:0;background:#fff;border-radius:8px;padding:9px;font:inherit;color:#2b6cb0;box-shadow:0 1px 1px #0002;cursor:pointer}
form{display:flex;border-top:1px solid #ddd}form input{flex:1;border:0;padding:14px;font:inherit;outline:0}form button{border:0;background:none;color:#517da2;font-weight:600;padding:0 16px;cursor:pointer}
.panel{width:330px;background:#fff;border-radius:16px;box-shadow:0 8px 30px #0001;padding:16px}.panel button{display:block;width:100%;margin:6px 0;padding:10px;border:1px solid #cbd5e1;background:#f8fafc;border-radius:8px;font:inherit;cursor:pointer;text-align:left}
.typing{font-style:italic;color:#64748b}
</style></head><body><div id="app"></div><script>
const P="__PAGE__";const app=document.getElementById('app');
const esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function phone(title,sub,letter){const c=document.createElement('div');c.className='phone';
 c.innerHTML=`<div class="top"><div class="ava">${letter}</div><div><b>${title}</b><small>${sub}</small></div></div><div class="chat"></div><div class="kb"></div>`;return c}
function add(chat,cls,html){const d=document.createElement('div');d.className='m '+cls;d.innerHTML=html;chat.appendChild(d);chat.scrollTop=1e9;return d}
async function post(u,b){return (await fetch(u,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b||{})})).json()}
function col(cap,el){const c=document.createElement('div');c.className='col';c.innerHTML=`<div class="cap">${cap}</div>`;c.appendChild(el);app.appendChild(c);return el}
function input(ph,onsend){const f=document.createElement('form');f.innerHTML=`<input placeholder="Сообщение"><button>➤</button>`;
 f.onsubmit=e=>{e.preventDefault();const i=f.querySelector('input');if(i.value.trim()){onsend(i.value.trim());i.value=''}};ph.appendChild(f)}
if(P==='support'){const ph=col('Клиент · Telegram',phone('Родник · поддержка','бот','Р'));const chat=ph.querySelector('.chat');
 add(chat,'in','Здравствуйте! Я бот поддержки «Родник». Спросите про доставку, оплату, залог или кулеры.');
 window.ask=async q=>{add(chat,'out',esc(q));const t=add(chat,'in typing','печатает…');const r=await post('/api/support',{text:q,sid:'@olga_k'});
  t.className='m in';t.innerHTML=esc(r.text)+(r.sources.length?`<div class="src">📄 ${r.sources.map(esc).join(' · ')}</div>`:'');
  if(r.operator)add(ochat,'in',esc(r.operator))};
 const op=col('Оператор · Telegram',phone('Родник · обращения','передано ботом','О'));const ochat=op.querySelector('.chat');op.querySelector('.kb').remove();
 input(ph,ask)}
if(P==='crm'){const pan=document.createElement('div');pan.className='panel';
 pan.innerHTML='<b>События CRM (вебхуки)</b><button data-s="amo_add">amoCRM: новая сделка</button><button data-s="amo_status">amoCRM: сделка перешла на этап</button><button data-s="bitrix_add">Bitrix24: новая сделка</button>';
 col('CRM',pan);const ph=col('Менеджер · Telegram',phone('Продажи «Родник»','группа · 4 участника','П'));const chat=ph.querySelector('.chat');let n=0;
 pan.querySelectorAll('button').forEach(b=>b.onclick=async()=>{const r=await post('/api/crm/'+b.dataset.s);r.outbox.slice(n).forEach(t=>add(chat,'in',t));n=r.outbox.length})}
if(P==='leads'){const ph=col('Клиент · Telegram',phone('Родник · заявки','бот','Р'));const chat=ph.querySelector('.chat'),kb=ph.querySelector('.kb');
 const mg=col('Менеджер · Telegram',phone('Родник · заявки','уведомления менеджеру','Р'));const mchat=mg.querySelector('.chat');let n=0;
 window.say=async t=>{if(t!=='/start')add(chat,'out',esc(t));const r=await post('/api/leads',{text:t,sid:'demo'});add(chat,'in',esc(r.text));
  kb.innerHTML='';r.buttons.forEach(b=>{const x=document.createElement('button');x.textContent=b;x.onclick=()=>say(b);kb.appendChild(x)});
  r.manager.slice(n).forEach(m=>add(mchat,'in',esc(m)));n=r.manager.length};
 input(ph,say);say('/start')}
</script></body></html>"""
