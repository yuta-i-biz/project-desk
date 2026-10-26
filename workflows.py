"""Durable, user-approved sequential drafts. Never execute imported task titles."""
import argparse,datetime,json,secrets,threading,time
from pathlib import Path
KINDS={'analysis','draft'}
STOP_WORDS=('送信して','送って','削除して','上書きして','公開して','デプロイして','支払って','契約して','採用を決め','価格を決め')

def init(desk):
 with desk.connect() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS work_plans(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,title TEXT NOT NULL,state TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS work_steps(plan_id TEXT NOT NULL,position INTEGER NOT NULL,prompt TEXT NOT NULL,criteria TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',task_id TEXT,reason TEXT NOT NULL DEFAULT '',PRIMARY KEY(plan_id,position));''')

def create(desk,payload):
 init(desk);pid=payload.get('project_id');steps=payload.get('steps');title=payload.get('title','連続する調査・下書き')
 if pid not in desk.project_ids() or not isinstance(title,str) or not title.strip() or len(title)>160:raise ValueError('案件と工程名を確認してください。')
 if not isinstance(steps,list) or not 1<=len(steps)<=8:raise ValueError('工程は1〜8件にしてください。')
 checked=[]
 for s in steps:
  if not isinstance(s,dict) or s.get('kind') not in KINDS:raise ValueError('自動工程は調査・新規下書きだけです。')
  prompt=s.get('prompt');criteria=s.get('criteria')
  if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=5000 or not isinstance(criteria,str) or not 1<=len(criteria.strip())<=1000:raise ValueError('各工程の依頼と完了条件が必要です。')
  if any(w in prompt for w in STOP_WORDS):raise ValueError('原本変更・送信・判断等を含む工程は自動実行へ登録できません。')
  checked.append((prompt.strip(),criteria.strip(),s['kind']))
 ident='plan-'+secrets.token_hex(8)
 with desk.connect() as c:
  c.execute('INSERT INTO work_plans VALUES(?,?,?,?,?)',(ident,pid,title,'draft',datetime.datetime.now(datetime.timezone.utc).isoformat()))
  c.executemany('INSERT INTO work_steps(plan_id,position,prompt,criteria,kind) VALUES(?,?,?,?,?)',[(ident,i,*s) for i,s in enumerate(checked)])
 return {'id':ident,'state':'draft'}

def plans(desk):
 init(desk)
 with desk.connect() as c:
  rows=[dict(r) for r in c.execute('SELECT * FROM work_plans ORDER BY created DESC')]
  for r in rows:r['steps']=[dict(s) for s in c.execute('SELECT * FROM work_steps WHERE plan_id=? ORDER BY position',(r['id'],))]
 return rows

def approve(desk,payload):
 init(desk)
 if payload.get('confirmed') is not True:raise ValueError('工程と完了条件の確認が必要です。')
 with desk.connect() as c:
  r=c.execute("UPDATE work_plans SET state='active' WHERE id=? AND state='draft'",(payload.get('id'),))
  if r.rowcount!=1:raise ValueError('承認できる工程案が見つかりません。')
 return {'ok':True}

def pause(desk,ident):
 init(desk)
 with desk.connect() as c:c.execute("UPDATE work_plans SET state='paused' WHERE id=? AND state IN ('active','draft')",(ident,))
 return {'ok':True}

def recover(desk):
 init(desk)
 with desk.connect() as c:
  ids=[r[0] for r in c.execute("SELECT DISTINCT plan_id FROM work_steps WHERE state='dispatching'")]
  c.execute("UPDATE work_steps SET state='held',reason='再起動前の受付結果が未確認。自動再実行せず履歴を確認してください。' WHERE state='dispatching'")
  for ident in ids:c.execute("UPDATE work_plans SET state='held' WHERE id=?",(ident,))
 for plan in plans(desk):
  for step in plan['steps']:
   if step['state']=='running' and not (desk.data/'requests'/str(step['task_id'])/'receipt.json').exists():
    with desk.connect() as c:
     c.execute("UPDATE work_steps SET state='held',reason='再起動前の実行結果を確認できません。自動再実行しません。' WHERE plan_id=? AND position=?",(plan['id'],step['position']));c.execute("UPDATE work_plans SET state='held' WHERE id=?",(plan['id'],))

def tick(desk,submitter=None):
 init(desk)
 from execution import submit
 submitter=submitter or submit
 for plan in plans(desk):
  if plan['state']!='active':continue
  step=next((s for s in plan['steps'] if s['state']!='done'),None)
  if step is None:
   with desk.connect() as c:c.execute("UPDATE work_plans SET state='complete' WHERE id=? AND state='active'",(plan['id'],))
   continue
  if step['state']=='running':
   receipt=desk.data/'requests'/str(step['task_id'])/'receipt.json'
   if not receipt.exists():
    with desk.connect() as c:
     task=c.execute('SELECT status FROM tasks WHERE id=?',(step['task_id'],)).fetchone()
     if task is None or task[0] in ('保留','確認待ち','完了'):
      c.execute("UPDATE work_steps SET state='held',reason='実行結果が取得できず停止しています。自動再実行しません。' WHERE plan_id=? AND position=?",(plan['id'],step['position']));c.execute("UPDATE work_plans SET state='held' WHERE id=?",(plan['id'],))
    continue
   try:r=json.loads(receipt.read_text())
   except (OSError,ValueError):continue
   passed=r.get('execution_status')=='succeeded' and r.get('review',{}).get('status')=='reviewed'
   with desk.connect() as c:
    c.execute("UPDATE work_steps SET state=?,reason=? WHERE plan_id=? AND position=? AND state='running'",('done' if passed else 'held','' if passed else '実行または独立した検品が未完了。次工程は開始しません。',plan['id'],step['position']))
    if not passed:c.execute("UPDATE work_plans SET state='held' WHERE id=?",(plan['id'],))
   continue
  if step['state']!='pending':continue
  # Commit the dispatch claim first. A crash here must never cause a replay.
  with desk.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   active=c.execute('SELECT state FROM work_plans WHERE id=?',(plan['id'],)).fetchone()
   if not active or active[0]!='active':continue
   claim=c.execute("UPDATE work_steps SET state='dispatching' WHERE plan_id=? AND position=? AND state='pending'",(plan['id'],step['position']))
   if claim.rowcount!=1:continue
  prompt='承認済み工程 '+str(step['position']+1)+'。調査・新規下書きだけを専用フォルダで作成。外部送信・原本変更・本番公開・金銭や人事判断は禁止。\n依頼:\n'+step['prompt']+'\n完了条件（独立検品で照合）:\n'+step['criteria']
  try:
   r=submitter(desk,{'project_id':plan['project_id'],'prompt':prompt,'engine':'Codex','_autonomous':True})
   with desk.connect() as c:c.execute("UPDATE work_steps SET state='running',task_id=? WHERE plan_id=? AND position=? AND state='dispatching'",(r['task_id'],plan['id'],step['position']))
  except Exception:
   with desk.connect() as c:
    c.execute("UPDATE work_steps SET state='held',reason='受付結果が未確認です。自動再実行しません。' WHERE plan_id=? AND position=?",(plan['id'],step['position']));c.execute("UPDATE work_plans SET state='held' WHERE id=?",(plan['id'],))

def loop(desk,stop):
 recover(desk)
 while not stop.is_set():
  try:tick(desk)
  except Exception:
   # Do not spin forever or retry an uncertain dispatch silently.
   with desk.connect() as c:
    c.execute("UPDATE work_plans SET state='held' WHERE state='active'")
    c.execute("UPDATE work_steps SET state='held',reason='工程管理処理の確認が必要です。自動再実行しません。' WHERE state IN ('pending','dispatching') AND plan_id IN (SELECT id FROM work_plans WHERE state='held')")
  stop.wait(5)
