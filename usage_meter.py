"""Observed CLI token counters only: no estimates, prices or secret log bodies."""
import hashlib,json,re,datetime
from pathlib import Path

def integer(value):return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None

def counter(event,engine):
 if not isinstance(event,dict):return None
 source=None;usage=None
 if engine=='Codex' and event.get('type')=='turn.completed':usage=event.get('usage');source='codex.turn.completed'
 elif engine=='Claude Code' and event.get('type')=='result':usage=event.get('usage');source='claude.result'
 elif engine=='Gemini' and event.get('event')=='result':
  result=event.get('result',{});usage=result.get('usageMetadata') or result.get('usage');source='gemini.result'
 if not isinstance(usage,dict):return None
 if engine=='Gemini':
  inp=integer(usage.get('promptTokenCount'));cached=integer(usage.get('cachedContentTokenCount'));out=integer(usage.get('candidatesTokenCount'));write=None
 else:
  inp=integer(usage.get('input_tokens'));out=integer(usage.get('output_tokens'));cached=integer(usage.get('cached_input_tokens') if engine=='Codex' else usage.get('cache_read_input_tokens'));write=integer(usage.get('cache_write_input_tokens') if engine=='Codex' else usage.get('cache_creation_input_tokens'))
  # Claude input_tokens excludes read/creation counters; Codex includes cached input.
  if engine=='Claude Code' and inp is not None:inp=inp+cached+write if cached is not None and write is not None else None
 if engine in ('Codex','Gemini') and inp is not None and cached is not None and cached>inp:return None
 if inp is None and out is None:return None
 return {'input_tokens':inp,'cached_input_tokens':cached,'cache_write_input_tokens':write,'output_tokens':out,'source':source}

def snapshot(desk):
 with desk.connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS usage_logs(task_id TEXT,path TEXT,stamp TEXT,PRIMARY KEY(task_id,path))')
  c.execute('CREATE TABLE IF NOT EXISTS token_usage(task_id TEXT,path TEXT,event_index INTEGER,engine TEXT,stage TEXT,input_tokens INTEGER,cached_input_tokens INTEGER,cache_write_input_tokens INTEGER,output_tokens INTEGER,source TEXT,PRIMARY KEY(task_id,path,event_index))')
  tasks=[dict(r) for r in c.execute('SELECT id,project_id FROM tasks')]
 observed=set();unknown=[]
 for task in tasks:
  tid=task['id']
  if not re.fullmatch('task-[a-f0-9]{16}',tid):continue
  folder=desk.data/'requests'/tid;receipt=folder/'receipt.json'
  if not receipt.is_file() or receipt.is_symlink():continue
  try:engine=json.loads(receipt.read_text()).get('engine','')
  except (OSError,ValueError):continue
  logs=[folder/'cli.log']+sorted(folder.glob('.review-*/cli.log'))
  for log in logs:
   if not log.is_file() or log.is_symlink() or log.parent.is_symlink():continue
   path=str(log.relative_to(folder));stat=log.stat();stamp=str(stat.st_mtime_ns)+':'+str(stat.st_size)
   with desk.connect() as c:old=c.execute('SELECT stamp FROM usage_logs WHERE task_id=? AND path=?',(tid,path)).fetchone()
   if old and old[0]==stamp:continue
   rows=[];provider='Codex' if path.startswith('.review-') else engine
   with log.open(errors='replace') as stream:
    for index,line in enumerate(stream):
     try:event=json.loads(line)
     except ValueError:continue
     usage=counter(event,provider)
     if usage:rows.append((tid,path,index,provider,'review' if path.startswith('.review-') else 'execution',usage['input_tokens'],usage['cached_input_tokens'],usage['cache_write_input_tokens'],usage['output_tokens'],usage['source']))
   with desk.connect() as c:
    c.execute('DELETE FROM token_usage WHERE task_id=? AND path=?',(tid,path));c.executemany('INSERT INTO token_usage VALUES(?,?,?,?,?,?,?,?,?,?)',rows)
    c.execute('INSERT OR REPLACE INTO usage_logs VALUES(?,?,?)',(tid,path,stamp))
  with desk.connect() as c:count=c.execute('SELECT COUNT(*) FROM token_usage WHERE task_id=?',(tid,)).fetchone()[0]
  if count:observed.add(tid)
  else:unknown.append(tid)
 with desk.connect() as c:
  rows=[dict(r) for r in c.execute('SELECT t.project_id,u.engine,u.stage,COUNT(*) AS calls,SUM(u.input_tokens) AS input_tokens,SUM(u.cached_input_tokens) AS cached_input_tokens,SUM(u.output_tokens) AS output_tokens,SUM(u.cache_write_input_tokens) AS cache_write_input_tokens,SUM(CASE WHEN u.input_tokens IS NULL THEN 1 ELSE 0 END) AS unknown_input_calls,SUM(CASE WHEN u.cached_input_tokens IS NULL THEN 1 ELSE 0 END) AS unknown_cache_calls,SUM(CASE WHEN u.output_tokens IS NULL THEN 1 ELSE 0 END) AS unknown_output_calls FROM token_usage u JOIN tasks t ON t.id=u.task_id GROUP BY t.project_id,u.engine,u.stage')]
 return {'rows':rows,'observed_requests':len(observed),'unknown_requests':len(unknown),'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'保存済みCLIログで観測できた使用量。入力にはキャッシュ読取を含む。未取得はゼロではない。契約枠残量・請求額・保存されていない過去の使用量は含まない。'}
