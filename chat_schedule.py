"""Apply explicit user-backed scheduling changes only to the app's own database."""
import json,re,datetime
from scheduling import FIELDS

def iso(v):
    m=re.fullmatch(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[（(][月火水木金土日][)）])?',str(v).strip())
    if not m:return ''
    try:return datetime.date(*map(int,m.groups())).isoformat()
    except ValueError:return ''

def overlay(desk,tasks):
    with desk.connect() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schedule_overrides'").fetchone():return tasks
        rows={r['source_id']:dict(r) for r in c.execute('SELECT * FROM schedule_overrides')}
    return [{**t,**json.loads(rows[t['id']]['payload']),'app_schedule_override':True,'schedule_updated':rows[t['id']]['updated']} if t['id'] in rows else t for t in tasks]

def apply(desk,pid,request,changes,snapshot,all_projects=False):
    if not isinstance(changes,list) or len(changes)>20:raise ValueError('日程更新案は20件以内の配列が必要です。')
    results=[];known={t['id']:t for t in snapshot}
    current={t['id']:t for t in overlay(desk,desk.snapshot()['tasks'])}
    for change in changes:
        try:
            if not isinstance(change,dict):raise ValueError('更新案の形式が不正です。')
            tid=change.get('task_id');t=known.get(tid);live=current.get(tid)
            if not t or not live or (not all_projects and t['project_id']!=pid):raise ValueError('対象案件の既存タスクではありません。')
            quote=change.get('source_quote','')
            if not quote or quote not in request or not (t['title'] in quote or tid in quote):raise ValueError('依頼文にタスクを特定する明示的な変更指示がありません。')
            if re.search(r'変更しない|変更不要|変えない|更新しない|そのまま|キャンセル|取り消',quote):raise ValueError('変更を否定する指示があるため更新しません。')
            patch={k:change[k] for k in ('due_date','start_date','status','next_action') if k in change}
            if not patch:raise ValueError('更新項目がありません。')
            if live.get('version')!=t.get('version') or live.get('schedule_updated')!=t.get('schedule_updated') or any(live.get(k)!=t.get(k) for k in ('status','deadline','due_date','start_date')):raise ValueError('依頼後に更新されています。最新状態を確認してください。')
            for field in ('due_date','start_date'):
                if field in patch:
                    value=iso(patch[field]);dates=[iso(x) for x in re.findall(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',quote)]
                    if not value or value not in dates:raise ValueError('期日は依頼文の西暦付き日付で明示してください。')
                    patch[field]=value
            if 'status' in patch and (patch['status'] not in ('未着手','作業中','確認待ち','保留','完了') or patch['status'] not in quote):raise ValueError('状態は依頼文で明示してください。')
            if patch.get('status')=='完了' and re.search(r'未完了|完了していない|完了しない|完了ではない',quote):raise ValueError('未完了の記載があるため完了にしません。')
            if 'next_action' in patch and (not isinstance(patch['next_action'],str) or patch['next_action'] not in quote):raise ValueError('次の作業は依頼文の記載に限ります。')
            start=patch.get('start_date',t.get('start_date',''));due=patch.get('due_date',t.get('due_date') or iso(t.get('deadline','')))
            if start and due and start>due:raise ValueError('開始日が期日より後です。')
            if t.get('read_only'):
                with desk.lock,desk.connect() as c:
                    c.execute('CREATE TABLE IF NOT EXISTS schedule_overrides(source_id TEXT PRIMARY KEY,project_id TEXT,payload TEXT,updated TEXT)')
                    old=c.execute('SELECT payload,updated FROM schedule_overrides WHERE source_id=?',(tid,)).fetchone()
                    if old and old['updated']!=t.get('schedule_updated'):raise ValueError('日程が既に更新されています。')
                    value={**(json.loads(old['payload']) if old else {}),**patch};stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                    c.execute('INSERT OR REPLACE INTO schedule_overrides VALUES(?,?,?,?)',(tid,t['project_id'],json.dumps(value,ensure_ascii=False),stamp))
                    c.execute('INSERT INTO events(task_id,project_id,at,kind,note) VALUES(NULL,?,?,?,?)',(t['project_id'],stamp,'アプリ内ガント更新',tid+' / '+json.dumps(patch,ensure_ascii=False)))
            else:
                payload={'id':tid,'version':t['version'],'status':patch.get('status',t['status']),'next_action':patch.get('next_action',t.get('next_action','')),'blocker':t.get('blocker',''),'result':t.get('result',''),**{k:patch[k] for k in FIELDS if k in patch}}
                if payload['status']=='完了':payload['result']='ユーザーの明示報告：'+quote
                if payload['status'] in ('保留','確認待ち') and not payload['blocker']:payload['blocker']=quote
                desk.mutate('update',payload)
            results.append({'task_id':tid,'applied':True,'changes':patch,'note':'アプリ内の更新。Google原本は未変更。'})
        except (ValueError,KeyError,TypeError) as e:results.append({'task_id':change.get('task_id') if isinstance(change,dict) else None,'applied':False,'reason':str(e)})
    return results
