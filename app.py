#!/usr/bin/env python3
"""Local project desk. Existing Claude files are read-only; writes stay in data/."""
import argparse
import datetime as dt
import hashlib
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs,quote,unquote

ROOT = Path(__file__).resolve().parent
JST = dt.timezone(dt.timedelta(hours=9))
STATES = ('未着手', '作業中', '確認待ち', '保留', '完了')
MAX_BODY = 32768

def now():
    return dt.datetime.now(JST).isoformat(timespec='seconds')

def uid(prefix, text):
    return prefix + hashlib.sha256(text.encode()).hexdigest()[:20]

def normalized(text):
    text = unicodedata.normalize('NFKC', str(text))
    return re.sub(r'[\s【】\[\]]', '', text).casefold().replace('モノ_ループ', 'モノ・ループ')

def named(title, fallback='未分類'):
    match = re.match(r'^【([^：:】]+)[：:]([^】]+)】', title)
    if match:
        return match[1].replace('モノ_ループ', 'モノ・ループ'), match[2].strip()
    return fallback, title.strip()

def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default

def excerpts(path):
    # Large notes are searched line-by-line for relevant sections; never read whole files.
    wanted = ('目的', '現在地', '次アクション', '未解決', '再開のしかた')
    found = {}; heading = None; used = 0; truncated = path.stat().st_size > 50000
    with path.open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            if line.startswith('#'):
                heading = next((k for k in wanted if re.match(r'^#{1,3}\s*'+re.escape(k)+r'(?:\s|[（(]|$)', line)), None)
                used = 0
            elif heading and used < 1100:
                clean = line.strip()
                if clean and not re.search(r'token|password|secret|api[_ -]?key|Bearer\s',clean,re.I):
                    clean = re.sub(r'https?://\S+', '[リンクは原資料で確認]', clean)
                    found[heading] = (found.get(heading, '') + '\n' + clean[:500]).strip()[:1100]
                    used += len(clean)
    return found, truncated

class Desk:
    def __init__(self, home=Path.home(), data=ROOT/'data'):
        self.home = Path(home); self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True)
        self.machine=read_json(self.data/'node.json',{}).get('name','このMac')
        self.db = self.data/'desk.sqlite3'
        self.lock = threading.RLock(); self.cache = None; self.cache_at = 0
        self.title_cache = {}; self.token = secrets.token_urlsafe(32)
        access_file=self.data/'access.json'
        if not access_file.exists():
            fd=os.open(access_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:json.dump({'code':str(secrets.randbelow(9000000000)+1000000000),'session':secrets.token_urlsafe(40)},f)
        self.access=read_json(access_file,{})
        if not self.access.get('code') or not self.access.get('session'):raise ValueError('接続設定を読めません。')
        self.login_attempts=[]
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,company TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS bindings(source_id TEXT PRIMARY KEY,project_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,
              next_action TEXT NOT NULL DEFAULT '',blocker TEXT NOT NULL DEFAULT '',result TEXT NOT NULL DEFAULT '',
              session_id TEXT NOT NULL DEFAULT '',created TEXT NOT NULL,updated TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,project_id TEXT,at TEXT NOT NULL,kind TEXT NOT NULL,note TEXT NOT NULL);
            ''')
            existing={row[1] for row in c.execute('PRAGMA table_info(tasks)')}
            for name,definition in [('due_date',"TEXT NOT NULL DEFAULT ''"),('start_date',"TEXT NOT NULL DEFAULT ''"),('effort_days',"TEXT NOT NULL DEFAULT ''"),('depends_on',"TEXT NOT NULL DEFAULT ''"),('deadline_reason',"TEXT NOT NULL DEFAULT ''"),('completion_criteria',"TEXT NOT NULL DEFAULT ''")]:
                if name not in existing:c.execute('ALTER TABLE tasks ADD COLUMN '+name+' '+definition)
    def connect(self):
        c = sqlite3.connect(self.db, timeout=15); c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON'); return c
    def invalidate(self):
        self.cache_at = 0
    def collect(self, force=False):
        with self.lock:
            if self.cache is not None and not force and time.monotonic()-self.cache_at < 20:
                return self.cache
            errors = []; sources = []; sessions = []
            ml_gantt=read_json(self.data/'ml_gantt.json',{})
            canonical_ml=bool(ml_gantt.get('projects'))
            runtime = self.home/'.claude/runtime'; ledger_root = runtime/'ledger'
            if ledger_root.exists():
                for p in sorted(ledger_root.rglob('*.md')):
                    rel = p.relative_to(ledger_root)
                    if any(s.startswith(('.', '_')) for s in rel.parts[:-1]):
                        continue
                    try:
                        company, name = named(p.stem, rel.parts[0] if len(rel.parts)>1 else '未分類')
                        sections, partial = excerpts(p)
                        sources.append({'id':uid('macmini-ledger-' if self.machine=='Mac mini' else 'ledger-',str(rel)), 'type':'案件台帳', 'name':name,'company':company,
                            'updated':dt.datetime.fromtimestamp(p.stat().st_mtime,JST).isoformat(timespec='seconds'),
                            'path':str(p),'sections':sections,'partial':partial,'recorded_status':''})
                    except OSError:
                        errors.append('読めない案件台帳があります: '+p.name)
            else:
                errors.append('案件台帳フォルダが見つかりません。')
            board_path = runtime/'project_state.json'; board = read_json(board_path, None)
            if not isinstance(board,dict):
                errors.append('進捗ボードを読めませんでした。')
                board={}
            for company, rows in board.items():
                if company.startswith('_') or not isinstance(rows,dict): continue
                for key, entry in rows.items():
                    if not isinstance(entry,dict) or not entry.get('name'): continue
                    sources.append({'id':uid('macmini-board-' if self.machine=='Mac mini' else 'board-',company+'/'+key),'type':'進捗ボード', 'company':company,
                        'name':entry['name'],'updated':entry.get('last_touched') or board.get('_updated') or '',
                        'recorded_status':entry.get('status',''),'sections':{'次アクション':str(entry.get('next_action') or '')},
                        'path':str(board_path),'partial':False})
            # Session metadata only: do not surface conversation bodies or tool results.
            old_titles = read_json(runtime/'session_titles_cache.json',{})
            if not isinstance(old_titles,dict): old_titles={}
            session_root = self.home/'.claude/projects'
            paths = list(session_root.glob('*/*.jsonl')) if session_root.exists() else []
            for p in paths:
                try:
                    stat = p.stat(); sig = (stat.st_size,stat.st_mtime_ns)
                    cached = self.title_cache.get(str(p))
                    old = old_titles.get(str(p),{})
                    if not isinstance(old,dict): old={}
                    if cached and cached[0] == sig:
                        title = cached[1]
                    else:
                        title = str(old.get('title') or '')
                        with p.open('rb') as f:
                            f.seek(max(0,stat.st_size-24576))
                            tail=f.read(24576).decode('utf-8',errors='replace')
                        titles=re.findall(r'"customTitle"\s*:\s*("(?:[^"\\]|\\.)*")',tail)
                        if titles:
                            try:title=json.loads(titles[-1])
                            except ValueError:pass
                        self.title_cache[str(p)]=(sig,title)
                    if not title or old.get('internal'): continue
                    company,project = named(title)
                    sessions.append({'id':('macmini:claude:' if self.machine=='Mac mini' else 'claude:')+p.stem,'title':title,'company':company,'project_name':project,
                        'type':'Claude Code','updated':dt.datetime.fromtimestamp(stat.st_mtime,JST).isoformat(timespec='seconds'),
                        'observed_status':'会話記録あり・実行状態は未確認','snapshot_at':None})
                except OSError:
                    errors.append('一部の会話記録を読めませんでした。')
            codex = read_json(self.data/'codex_threads.json',{})
            for t in codex.get('threads',[]) if isinstance(codex,dict) else []:
                if not isinstance(t,dict) or t.get('kind')!='codex':continue
                company,project=named(str(t.get('title','名称なし')))
                sessions.append({'id':'codex:'+str(t['id']),'title':t.get('title','名称なし'),
                    'company':company,'project_name':project,'type':'Codex',
                    'updated':t.get('updated',''),'observed_status':'取得時点: '+str(t.get('status','不明')),
                    'snapshot_at':codex.get('captured_at')})
            for s in sources+sessions:
                s['machine']=self.machine
            remote=read_json(self.data/'peer_snapshot.json',None)
            if remote is None:remote=read_json(self.data/'mac_mini.json',{})
            remote_status=read_json(self.data/'peer_sync.json',None)
            if remote_status is None:remote_status=read_json(self.data/'mac_mini_sync.json',{})
            if isinstance(remote,dict):
                sources.extend(remote.get('sources',[]))
                sessions.extend(remote.get('sessions',[]))
                errors.extend(e for e in remote.get('errors',[]) if not (canonical_ml and 'タスクガント' in e))
            if remote_status and not remote_status.get('ok'):
                errors.append(str(remote_status.get('error','Mac miniの接続を確認してください。')))
            with self.connect() as c:
                manual=[dict(r) for r in c.execute('SELECT * FROM projects')]
                bindings={r['source_id']:r['project_id'] for r in c.execute('SELECT * FROM bindings')}
            projects={p['id']:{**p,'sources':[],'sessions':[]} for p in manual}
            exact={}
            for s in sources:
                key=normalized(s['company'])+'/'+normalized(s['name'])
                project_id=bindings.get(s['id']) or exact.get(key) or uid('project-',key)
                exact.setdefault(key,project_id)
                if project_id not in projects:
                    projects[project_id]={'id':project_id,'name':s['name'],'company':s['company'],'sources':[],'sessions':[]}
                projects[project_id]['sources'].append(s)
            # Register exact matches for manual projects too; ambiguous names are never fuzzy matched.
            for p in projects.values():
                exact.setdefault(normalized(p['company'])+'/'+normalized(p['name']),p['id'])
            unlinked=[]
            for s in sessions:
                key=normalized(s['company'])+'/'+normalized(s['project_name'])
                target=bindings.get(s['id']) or exact.get(key)
                if target in projects:
                    projects[target]['sessions'].append(s)
                else:unlinked.append(s)
            for p in projects.values():
                p['sessions'].sort(key=lambda s:s['updated'],reverse=True)
                p['sources'].sort(key=lambda s:str(s['updated']),reverse=True)
                p['updated']=max([str(s['updated']) for s in p['sources']+p['sessions']] + [str(p.get('created',''))])
                p['recorded_status']=next((s['recorded_status'] for s in p['sources'] if s['recorded_status']), '')
                p['current']=next((s['sections'].get('現在地') for s in p['sources'] if s['sections'].get('現在地')), '')
                p['next_action']=next((s['sections'].get('次アクション') for s in p['sources'] if s['sections'].get('次アクション')), '')
                p['blocker']=next((s['sections'].get('未解決') for s in p['sources'] if s['sections'].get('未解決')), '')
                p['machines']=sorted({s.get('machine','このMac') for s in p['sources']+p['sessions']})
            sheet_tasks=[]
            if canonical_ml:
                for p in projects.values():
                    if normalized(p['company'])==normalized('モノ・ループ'):p['reference_only']=True
                for sheet in ml_gantt['projects']:
                    display_name=sheet.get('tab_name') if not sheet.get('archived') and sheet.get('tab_name') else sheet['name']
                    key=normalized('モノ・ループ')+'/'+normalized(display_name)
                    pid=exact.get(key) or uid('project-',key)
                    project=projects.setdefault(pid,{'id':pid,'name':display_name,'company':'モノ・ループ','sources':[],'sessions':[],'machines':[]})
                    project.update(reference_only=bool(sheet.get('archived')),canonical_gantt=True,
                        updated=ml_gantt['captured_at'],current='MLガントチャートのステータスを表示',
                        next_action=next((t['title'] for t in sheet['tasks'] if t['status']!='完了'),'ガント記載のタスクはすべて完了'),
                        blocker='',recorded_status='',deadline=sheet['deadline'])
                    project['sources'].insert(0,{'id':'ml-sheet-'+str(sheet['id']),'type':'MLガント（正本）','name':sheet['name'],
                        'company':'モノ・ループ','machine':'Google Sheets','updated':ml_gantt['captured_at'],
                        'path':sheet['url'],'sections':{'現在地':'このタブのタスク・ステータス・完了予定日を読み取っています。'},
                        'partial':False,'recorded_status':''})
                    project['machines']=sorted(set(project.get('machines',[]))|{'Google Sheets'})
                    for entry in sheet['tasks']:
                        if sheet.get('archived'):continue
                        sheet_tasks.append({'id':'ml-'+str(sheet['id'])+'-'+entry['source_id']+'-'+str(entry['row']),
                            'project_id':pid,'title':entry['title'],'status':entry['status'] or '状態未設定',
                            'source_status':entry['status'],'next_action':entry['detail'] or entry['title'],
                            'blocker':'','result':'SSのステータス列に「完了」と記載（実動作の独立検証ではありません）。' if entry['status']=='完了' else '',
                            'session_id':'','created':ml_gantt['captured_at'],'updated':ml_gantt['captured_at'],
                            'version':None,'read_only':True,'source_url':sheet['url'],'source_row':entry['row'],
                            'deadline':entry['deadline'],'needs_check':False})
            imported=[]
            for kind,filename,array_key in [('タスクガント','gantt_cache.json','tasks'),('議事録タスク','meeting_ledger_cache.json','items')]:
                if canonical_ml and filename=='gantt_cache.json':continue
                document=read_json(runtime/filename,None)
                if not isinstance(document,dict) or not isinstance(document.get(array_key),list):
                    errors.append(kind+'の控えを読めませんでした。');continue
                if document.get('error'):errors.append(kind+'の元データ取得にエラーがあります。')
                for row in document[array_key]:
                    title=row.get('name' if array_key=='tasks' else 'title','')
                    if not isinstance(title,str) or not title.strip():continue
                    identity=str(row.get('id')) if array_key=='tasks' else str(row.get('extract_at',''))+'/'+str(row.get('meeting_title',''))+'/'+title
                    item_id=uid('macmini-import-' if self.machine=='Mac mini' else 'import-',filename+'/'+identity)
                    imported.append({'id':item_id,'title':title,'type':kind,'updated':document.get('updated',''),
                        'status':str(row.get('st' if array_key=='tasks' else 'status','')),
                        'deadline':str(row.get('end' if array_key=='tasks' else 'deadline','') or ''),
                        'category':str(row.get('cat' if array_key=='tasks' else 'related_project','') or ''),
                        'project_id':bindings.get(item_id),'path':str(runtime/filename),'machine':self.machine})
            for item in remote.get('imported_tasks',[]) if isinstance(remote,dict) else []:
                if canonical_ml and item.get('type')=='タスクガント':continue
                imported.append({**item,'project_id':bindings.get(item['id'])})
            overrides=read_json(self.data/'company_overrides.json',{})
            for p in projects.values():
                old=p.get('company','')
                if old in overrides:
                    p['company']=overrides[old]
                    p['activity']=old
                    if old not in p['name']:p['name']=old+' / '+p['name']
            for item in unlinked:
                if item.get('company') in overrides:item['company']=overrides[item['company']]
            self.cache={'projects':list(projects.values()),'unlinked':sorted(unlinked,key=lambda s:s['updated'],reverse=True),'imported_tasks':imported,'sheet_tasks':sheet_tasks,
                'sources':{'ledger_files':sum(s['type']=='案件台帳' for s in sources),'board_projects':sum(s['type']=='進捗ボード' for s in sources),
                           'claude_sessions':sum(s['type']=='Claude Code' for s in sessions),'codex_sessions':sum(s['type']=='Codex' for s in sessions),
                           'board_updated':board.get('_updated'), 'codex_captured_at':codex.get('captured_at') if isinstance(codex,dict) else None,
                           'host_machine':self.machine,'ml_gantt':{'captured_at':ml_gantt.get('captured_at'),'url':ml_gantt.get('url'),
                               'projects':sum(not p.get('archived') for p in ml_gantt.get('projects',[])),
                               'excluded_tabs':ml_gantt.get('excluded_tabs',[])},
                           'machines':[{'name':machine,'ledger_files':sum(s['type']=='案件台帳' and s.get('machine')==machine for s in sources),
                               'sync':{'ok':True} if machine==self.machine else remote_status,
                               'captured_at':now() if machine==self.machine else remote.get('captured_at') if isinstance(remote,dict) else None}
                               for machine in sorted({self.machine}|{s.get('machine',self.machine) for s in sources})]},
                'errors':list(dict.fromkeys(errors)),'indexed_at':now()}
            self.cache_at=time.monotonic();return self.cache
    def snapshot(self):
        base=self.collect()
        with self.connect() as c:
            tasks=[dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY updated DESC')]
            events=[dict(r) for r in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 120')]
        at=dt.datetime.now(JST)
        for t in tasks:
            t['needs_check']=(t['status']=='作業中' and (at-dt.datetime.fromisoformat(t['updated'])).total_seconds()>900)
            t['is_ai_request']=(self.data/'requests'/t['id']/'project_context.json').exists()
            t['receipt']=read_json(self.data/'requests'/t['id']/'receipt.json',None)
        local_health=read_json(self.data/'session_health.json',{})
        peer=read_json(self.data/'peer_snapshot.json',None)
        if peer is None:peer=read_json(self.data/'mac_mini.json',{})
        remote_health=read_json(self.data/'peer_health.json',peer.get('health',{}))
        health_sources=[h for h in [local_health,remote_health] if h.get('captured_at')]
        health_rows=[]
        exact={normalized(p['company'])+'/'+normalized(p['name']):p['id'] for p in base['projects']}
        session_projects={s['id']:p['id'] for p in base['projects'] for s in p['sessions']}
        for h in health_sources:
            for row in h.get('rows',[]):
                key=normalized(row['company'])+'/'+normalized(row['project_name'])
                health_rows.append({**row,'project_id':session_projects.get(row['session_id']) or exact.get(key)})
        health={'sources':[{k:v for k,v in h.items() if k!='rows'} for h in health_sources], 'rows':health_rows}
        from attachments import public_records
        from chat_schedule import overlay
        return {**base,'attachments':public_records(self),'tasks':overlay(self,tasks+base.get('sheet_tasks',[])),'events':events,'checked_at':now(),'app_path':str(ROOT/'app.py'),'health':health,
                'connections':read_json(self.data/'connections.json',[]),
                'engines':read_json(self.data/'engines.json',[]),
                'deadline_review':read_json(self.data/'deadline_review.json',{}),
                'access_url':read_json(self.data/'network.json',{}).get('origin')}
    def project_ids(self):
        return {p['id'] for p in self.collect()['projects']}
    def mutate(self,action,payload):
        if not isinstance(payload,dict):raise ValueError('入力内容が不正です。')
        stamp=now()
        with self.lock:
            if action=='project':
                name=required(payload,'name',160); company=required(payload,'company',100)
                if any(normalized(p['company'])==normalized(company) and normalized(p['name'])==normalized(name) for p in self.collect()['projects']):raise ValueError('同じ会社・活動に同名の案件があります。既存の案件を利用してください。')
                pid='manual-'+secrets.token_hex(8)
                with self.connect() as c:
                    c.execute('INSERT INTO projects VALUES(?,?,?,?)',(pid,name,company,stamp))
                    c.execute('INSERT INTO events(task_id,project_id,at,kind,note) VALUES(NULL,?,?,?,?)',(pid,stamp,'案件追加',name))
                self.invalidate();return {'id':pid}
            if action=='bind':
                sid=required(payload,'source_id',200);pid=required(payload,'project_id',100)
                known={s['id'] for p in self.collect()['projects'] for s in p['sources']+p['sessions']} | {s['id'] for s in self.collect()['unlinked']} | {s['id'] for s in self.collect()['imported_tasks']}
                if pid not in self.project_ids() or sid not in known:raise ValueError('案件または会話が見つかりません。更新してやり直してください。')
                with self.connect() as c:
                    c.execute('INSERT INTO bindings VALUES(?,?) ON CONFLICT(source_id) DO UPDATE SET project_id=excluded.project_id',(sid,pid))
                    c.execute('INSERT INTO events(task_id,project_id,at,kind,note) VALUES(NULL,?,?,?,?)',(pid,stamp,'関連付け',sid))
                self.invalidate();return {'ok':True}
            if action=='create':
                pid=required(payload,'project_id',100);title=required(payload,'title',240)
                if pid not in self.project_ids():raise ValueError('案件が見つかりません。')
                tid='task-'+secrets.token_hex(8)
                next_action=optional(payload,'next_action',2000)
                from scheduling import validate
                with self.connect() as c:
                    schedule=validate(c,payload,pid,tid)

                    c.execute('INSERT INTO tasks(id,project_id,title,status,next_action,created,updated) VALUES(?,?,?,?,?,?,?)',
                        (tid,pid,title,'未着手',next_action,stamp,stamp))
                    c.execute('UPDATE tasks SET due_date=?,start_date=?,effort_days=?,depends_on=?,deadline_reason=?,completion_criteria=? WHERE id=?',(*schedule.values(),tid))
                    c.execute('INSERT INTO events(task_id,project_id,at,kind,note) VALUES(?,?,?,?,?)',(tid,pid,stamp,'タスク追加',title))
                return {'id':tid,'status':'未着手','version':1}
            if action=='update':
                tid=required(payload,'id',100)
                status=required(payload,'status',20)
                if status not in STATES:raise ValueError('状態を選択してください。')
                try:version=int(payload.get('version',0))
                except (TypeError,ValueError):raise ValueError('版番号が不正です。')
                with self.connect() as c:
                    current=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
                    if current is None:raise ValueError('タスクが見つかりません。')
                    from scheduling import validate
                    schedule=validate(c,payload,current['project_id'],tid,current)
                    values={k:optional(payload,k,4000) if k in payload else current[k] for k in ['next_action','blocker','result','session_id']}
                    if status=='完了' and not values['result'].strip():raise ValueError('完了にするには成果物または確認結果を記録してください。')
                    if status in ('確認待ち','保留') and not values['blocker'].strip():raise ValueError('待っている理由を記録してください。')
                    if status=='作業中' and not values['next_action'].strip():raise ValueError('取り組む作業を記録してください。')
                    cursor=c.execute('UPDATE tasks SET status=?,next_action=?,blocker=?,result=?,session_id=?,updated=?,version=version+1 WHERE id=? AND version=?',
                        (status,values['next_action'],values['blocker'],values['result'],values['session_id'],stamp,tid,version))
                    if cursor.rowcount!=1:raise Conflict('別の画面で更新されています。最新を読み直してください。')
                    c.execute('UPDATE tasks SET due_date=?,start_date=?,effort_days=?,depends_on=?,deadline_reason=?,completion_criteria=? WHERE id=?',(*schedule.values(),tid))
                    c.execute('INSERT INTO events(task_id,project_id,at,kind,note) VALUES(?,?,?,?,?)',
                        (tid,current['project_id'],stamp,'状態更新',status+' / '+(values['result'] if status=='完了' else values['blocker'] if status in ('確認待ち','保留') else values['next_action'])))
                return {'id':tid,'version':version+1,'status':status}
        raise ValueError('未対応の操作です。')

class Conflict(ValueError):pass

def required(obj,key,limit):
    value=obj.get(key)
    if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError(key+'を入力してください（長さも確認してください）。')
    return value.strip()

def optional(obj,key,limit):
    value=obj.get(key,'')
    if not isinstance(value,str) or len(value)>limit:raise ValueError(key+'の入力が長すぎるか、形式が不正です。')
    return value.strip()

class Handler(BaseHTTPRequestHandler):
    server_version='ProjectDesk'
    def log_message(self,*args):pass
    def send_data(self,code,body,kind='application/json; charset=utf-8'):
        if isinstance(body,dict):body=json.dumps(body,ensure_ascii=False).encode()
        elif isinstance(body,str):body=body.encode()
        self.send_response(code)
        self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        self.end_headers();self.wfile.write(body)
    def valid_host(self):
        local='127.0.0.1:'+str(self.server.server_port)
        allowed={local}
        if getattr(self.server,'remote_access',False):
            network=read_json(self.server.desk.data/'network.json',{})
            for origin in [network.get('origin','')]+network.get('origins',[]):
                if origin:allowed.add(urlparse(origin).netloc)
        return self.headers.get('Host') in allowed
    def authorized(self):
        if not getattr(self.server,'remote_access',False):return True
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return False
        value=cookie.get('desk_session')
        return value is not None and secrets.compare_digest(value.value,self.server.desk.access['session'])
    def do_GET(self):
        if not self.valid_host():return self.send_data(403,{'error':'この端末からのみ利用できます。'})
        route=urlparse(self.path).path
        try:
            if route=='/api/access':
                if getattr(self.server,'remote_access',False):return self.send_data(403,{'error':'接続コードは元のMacから確認してください。'})
                return self.send_data(200,{'code':self.server.desk.access['code'],'url':read_json(self.server.desk.data/'network.json',{}).get('origin')})
            if route.startswith('/api/') and route!='/api/health' and not self.authorized():return self.send_data(401,{'error':'接続コードを入力してください。'})
            if route in ('/api/artifact','/api/artifact-preview'):
                query=parse_qs(urlparse(self.path).query);tid=query.get('task_id',[''])[0];name=query.get('file',[''])[0]
                if not re.fullmatch(r'task-[0-9a-f]+',tid):return self.send_data(404,{'error':'成果物が見つかりません。'})
                folder=(self.server.desk.data/'requests'/tid).resolve();path=(folder/name).resolve()
                from execution import PRIVATE
                if not path.is_relative_to(folder) or not path.is_file() or path.name in PRIVATE:return self.send_data(404,{'error':'成果物が見つかりません。'})
                if any(part.startswith('.') or part=='__pycache__' for part in path.relative_to(folder).parts):return self.send_data(404,{'error':'成果物が見つかりません。'})
                if route=='/api/artifact-preview':
                    from previews import describe,RAW,MAX_PREVIEW
                    raw_url='/api/artifact-preview?task_id='+quote(tid)+'&file='+quote(name)+'&raw=1'
                    if query.get('raw')==['1']:
                        if path.stat().st_size>MAX_PREVIEW or path.suffix.lower() not in RAW:return self.send_data(415,{'error':'画面内表示には対応していません。'})
                        raw_path=path;mime=RAW[path.suffix.lower()]
                        if query.get('page'):
                            from previews import pdf_pages
                            if path.suffix.lower()!='.pdf':return self.send_data(404,{'error':'ページが見つかりません。'})
                            page=int(query['page'][0]);cache,manifest=pdf_pages(path,ROOT)
                            if page<1 or page>len(manifest['pages']):return self.send_data(404,{'error':'ページが見つかりません。'})
                            raw_path=cache/manifest['pages'][page-1];mime='image/png'
                        body=raw_path.read_bytes();self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Disposition','inline');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'none'; img-src data:; style-src 'unsafe-inline'; frame-ancestors 'self'"+('; sandbox' if path.suffix.lower() in ('.html','.htm') else ''));self.end_headers();self.wfile.write(body);return
                    return self.send_data(200,describe(path,raw_url,ROOT))
                self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(path.name));self.send_header('Content-Length',str(path.stat().st_size));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
                with path.open('rb') as stream:
                    while True:
                        chunk=stream.read(65536)
                        if not chunk:break
                        self.wfile.write(chunk)
                return
            if route=='/api/state':return self.send_data(200,self.server.desk.snapshot())
            if route=='/api/health':return self.send_data(200,{'ok':True})
            if route=='/':
                filename='index.html' if self.authorized() else 'login.html'
                html=(ROOT/'static'/filename).read_text().replace('__CSRF_TOKEN__',self.server.desk.token)
                return self.send_data(200,html,'text/html; charset=utf-8')
            allowed={'/request_summary.js':'application/javascript; charset=utf-8','/deadlines.js':'application/javascript; charset=utf-8','/voice.js':'application/javascript; charset=utf-8','/app.js':'application/javascript; charset=utf-8','/login.js':'application/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}
            if route in allowed:return self.send_data(200,(ROOT/'static'/route[1:]).read_bytes(),allowed[route])
            self.send_data(404,{'error':'ページが見つかりません。'})
        except (OSError,sqlite3.Error,ValueError):self.send_data(500,{'error':'情報を読み込めませんでした。再読み込みしてください。'})
    def do_POST(self):
        origins={'http://127.0.0.1:'+str(self.server.server_port)}
        if getattr(self.server,'remote_access',False):
            network=read_json(self.server.desk.data/'network.json',{})
            origins.update([network.get('origin','')]+network.get('origins',[]))
        if not self.valid_host() or self.headers.get('Origin') not in origins or not secrets.compare_digest(self.headers.get('X-Desk-Token',''),self.server.desk.token):
            return self.send_data(403,{'error':'操作元を確認できません。画面を開き直してください。'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            route=urlparse(self.path).path
            if route=='/api/files/upload':
                if not self.authorized():return self.send_data(401,{'error':'接続コードを入力してください。'})
                from attachments import MAX_FILE,receive
                if length<=0 or length>MAX_FILE:return self.send_data(413,{'error':'ファイルは1件50MBまでです。'})
                pid=parse_qs(urlparse(self.path).query).get('project_id',[''])[0]
                if pid and pid not in self.server.desk.project_ids():return self.send_data(400,{'error':'保存先の案件を確認してください。'})
                body=self.rfile.read(length)
                if len(body)!=length:return self.send_data(400,{'error':'受信が途中で途切れました。ファイルを再選択してください。'})
                result=receive(self.server.desk,unquote(self.headers.get('X-File-Name','')),body,pid)
                return self.send_data(200,result)
            if length<=0 or length>MAX_BODY:return self.send_data(413,{'error':'入力内容が大きすぎます。'})
            payload=json.loads(self.rfile.read(length))
            if route=='/api/login':
                desk=self.server.desk
                with desk.lock:
                    desk.login_attempts=[t for t in desk.login_attempts if time.monotonic()-t<300]
                    if len(desk.login_attempts)>=15:return self.send_data(429,{'error':'入力回数が多いため、5分待ってから試してください。'})
                    desk.login_attempts.append(time.monotonic())
                    code=payload.get('code','') if isinstance(payload,dict) else ''
                    if not isinstance(code,str) or not secrets.compare_digest(code,desk.access['code']):return self.send_data(401,{'error':'接続コードを確認してください。'})
                    desk.login_attempts=[]
                self.send_response(200);self.send_header('Content-Type','application/json')
                secure='; Secure' if self.headers.get('Origin','').startswith('https:') else ''
                self.send_header('Set-Cookie','desk_session='+desk.access['session']+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=604800'+secure)
                self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b'{"ok":true}');return
            if not self.authorized():return self.send_data(401,{'error':'接続コードを入力してください。'})
            if route=='/api/files/retry':
                from attachments import record_path,POOL,store_drive
                if not record_path(self.server.desk,payload.get('id')).exists():return self.send_data(404,{'error':'添付が見つかりません。'})
                POOL.submit(store_drive,self.server.desk,payload['id']);return self.send_data(200,{'ok':True})
            if route=='/api/refresh':
                if read_json(self.server.desk.data/'node.json',{}).get('enable_user_requests'):
                    from auth_status import refresh
                    refresh(self.server.desk.data,self.server.desk.home)
                self.server.desk.collect(force=True);return self.send_data(200,{'ok':True})
            if route=='/api/run':
                if not read_json(self.server.desk.data/'node.json',{}).get('enable_user_requests'):
                    return self.send_data(503,{'error':'AI実行はMac miniへの移行後に有効になります。'})
                from execution import submit
                return self.send_data(200,submit(self.server.desk,payload))
            actions={'/api/projects':'project','/api/tasks':'create','/api/tasks/update':'update','/api/bind':'bind'}
            if route not in actions:return self.send_data(404,{'error':'操作が見つかりません。'})
            self.send_data(200,self.server.desk.mutate(actions[route],payload))
        except Conflict as exc:self.send_data(409,{'error':str(exc)})
        except (ValueError,TypeError) as exc:self.send_data(400,{'error':str(exc)})
        except sqlite3.Error:self.send_data(500,{'error':'保存できませんでした。内容を控えて再試行してください。'})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=18765)
    parser.add_argument('--remote-port',type=int,default=18767)
    parser.add_argument('--home',type=Path,default=Path.home())
    parser.add_argument('--data',type=Path,default=ROOT/'data')
    parser.add_argument('--action',choices=['project','create','update','bind','state'])
    args=parser.parse_args()
    if args.action and read_json(args.data/'authority.json',{}).get('server_url'):
        import sys
        from agent_client import call
        payload=None if args.action=='state' else json.load(sys.stdin)
        print(json.dumps(call(args.action,payload,args.data),ensure_ascii=False,indent=2));return
    desk=Desk(args.home,args.data)
    if args.action:
        import sys
        result=desk.snapshot() if args.action=='state' else desk.mutate(args.action,json.load(sys.stdin))
        print(json.dumps(result,ensure_ascii=False,indent=2));return
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);server.desk=desk
    private_server=None
    if read_json(desk.data/'network.json',{}).get('origin'):
        private_server=ThreadingHTTPServer(('127.0.0.1',args.remote_port),Handler)
        private_server.desk=desk;private_server.remote_access=True
        threading.Thread(target=private_server.serve_forever,daemon=True).start()
    stop_sync=threading.Event()
    if (desk.data/'mac_mini.json').exists():
        from sync_mac_mini import sync
        def refresh_remote():
            while not stop_sync.is_set():
                sync(desk.data);desk.invalidate()
                if stop_sync.wait(60):break
        threading.Thread(target=refresh_remote,daemon=True).start()
    from attachments import resume_pending
    resume_pending(desk)
    print('Project Desk: http://127.0.0.1:'+str(server.server_port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        stop_sync.set();server.server_close()
        if private_server:private_server.shutdown();private_server.server_close()
if __name__=='__main__':main()
