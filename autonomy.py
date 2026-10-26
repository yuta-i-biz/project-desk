"""Read the existing Plaud/night runner receipts; never start a second runner."""
import datetime as dt,json,re
from pathlib import Path
from urllib.parse import urlsplit
JST=dt.timezone(dt.timedelta(hours=9))
LABELS={'ai':'AIの実行対象','approval':'判断・承認が必要','data':'資料・接続が不足','repair':'AI側の修正・再検証','other':'他の担当者の対応','unknown':'未判定','done':'検品済み成果物あり'}

def records(v):return [x for x in v if isinstance(x,dict)] if isinstance(v,list) else []
def mapping(v):return v if isinstance(v,dict) else {}

def text(v,n=1000):return str(v or '')[:n]
def safe_url(v):
 try:
  u=urlsplit(str(v or ''))
  return str(v) if u.scheme=='https' and u.hostname in {'docs.google.com','drive.google.com','web.plaud.ai'} and not u.username else ''
 except ValueError:return ''
def latest(runtime,name,now):
 folder=runtime/name;paths=sorted(p for p in folder.glob('????-??-??.json') if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.json',p.name) and p.stem<=now.date().isoformat())
 if not paths:return {},{'name':name,'state':'missing','detail':'取得記録なし'}
 p=paths[-1]
 try:
  if p.is_symlink() or p.stat().st_size>16*1024*1024:raise ValueError()
  value=json.loads(p.read_text())
  if not isinstance(value,dict):raise ValueError()
  modified=dt.datetime.fromtimestamp(p.stat().st_mtime,JST);age=(now-modified).total_seconds()
  return value,{'name':name,'date':p.stem,'updated':modified.isoformat(),'state':'fresh' if 0<=age<=36*3600 else 'stale'}
 except (OSError,ValueError):return {},{'name':name,'state':'error','detail':'取得記録を読めません'}

def classify(triage,result):
 # A failed AI execution is not proof that a person must do the work.
 if triage.get('owner')=='other':return 'other'
 status=result.get('final_status')
 if status=='要データ':return 'data'
 if status=='要人力':return 'repair'
 if status=='コピー承認待ち':return 'approval'
 if status in {'済','完了','PASS'}:return 'done'
 if triage.get('llm_failed'):return 'unknown'
 if triage.get('category')=='ceo_only':return 'approval'
 if triage.get('category')=='delegation_draft':return 'other'
 if triage.get('category') in {'auto_run','ai_executable'}:return 'ai'
 return 'unknown'

def report(runtime,projects=(),tasks=(),now=None):
 runtime=Path(runtime);now=now or dt.datetime.now(JST)
 values={};sources=[]
 for name in ['plaud_fetch','plaud_llm','task_triage','night_exec']:
  value,source=latest(runtime,name,now);values[name]=value;sources.append(source)
 triage=values['task_triage'];night=values['night_exec'];rows=[]
 # Join only the same dated run and source namespace; reused IDs cannot inherit old success.
 same=triage.get('date') and triage.get('date')==night.get('date')
 results={(text(r.get('source')),text(r.get('task_id'))):r for r in records(night.get('results'))} if same else {}
 exact={}
 for t in tasks:
  if t.get('project_id'):exact.setdefault(text(t.get('title')).strip(),set()).add(t['project_id'])
 known=set();project_ids={p['id'] for p in projects}
 for item in records(triage.get('tasks'))+records(triage.get('owner_other')):
  if not isinstance(item,dict):continue
  key=(text(item.get('source')),text(item.get('id')))
  if key in known:continue
  known.add(key);tr=mapping(item.get('triage'));res=results.get(key,{})
  title=text(item.get('タスク名') or item.get('task_content') or item.get('title'),500)
  matches=exact.get(title.strip(),set());pid=next(iter(matches)) if len(matches)==1 else None
  if pid not in project_ids:pid=None
  kind=classify(tr,res)
  reason=' / '.join(text(x,700) for x in res.get('final_reasons',[])[:3]) or text(tr.get('reason'))
  rows.append({'id':key[0]+':'+key[1],'title':title,'project_id':pid,'group':kind,'reason':reason,'next_action':text(tr.get('execution_plan')),'required_data':[text(x,500) for x in res.get('required_data',[])[:10]],'url':safe_url(res.get('url')),'source':key[0],'source_date':triage.get('date'),'result_status':text(res.get('final_status')),'owner':text(tr.get('owner_name'))})
 # Preserve extraction provenance; a meeting's proposal is never silently treated as an instruction.
 meetings=[]
 for rec in records(values['plaud_llm'].get('extracted_recordings')):
  if not isinstance(rec,dict):continue
  meetings.append({'title':text(rec.get('title'),400),'url':safe_url(rec.get('url')),'ok':rec.get('ok') is True,'tasks':[{'title':text(t.get('task_content'),600),'type':text(t.get('type'),40),'assignee':text(t.get('assignee'),100),'deadline':text(t.get('deadline'),100),'evidence':text(t.get('source_utterance'),600)} for t in records(rec.get('tasks'))]})
 titles={r['title'].strip() for r in rows};unclassified=[];seen=set()
 for t in tasks:
  if t.get('status')=='完了' or t.get('title','').strip() in titles or t.get('id') in seen:continue
  title=text(t.get('title'),500);matches=exact.get(title.strip(),set());pid=t.get('project_id') or (next(iter(matches)) if len(matches)==1 else None)
  identity=(pid,title.strip())
  if identity in seen:continue
  seen.add(identity);seen.add(t.get('id'));unclassified.append({'id':t.get('id'),'title':title,'project_id':pid,'group':'unknown','reason':'既存の夜間仕分けに対応する記録がありません。AI不可と断定せず、案件資料・担当・完了条件の確認が必要です。'})
 return {'sources':sources,'rows':rows,'meetings':meetings,'unclassified':unclassified,'labels':LABELS,'coverage':'既存ランナーの取得済み記録。全案件の自動実行を保証するものではありません。','runner':'既存のMac mini夜間処理を継承。重複起動しません。','date_match':bool(same)}
