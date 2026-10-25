"""Read-only exporter run over an existing SSH connection. Writes nothing remotely."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

JST=dt.timezone(dt.timedelta(hours=9))
def uid(prefix,text):return prefix+hashlib.sha256(text.encode()).hexdigest()[:20]
def named(title,fallback='未分類'):
    m=re.match(r'^【([^：:】]+)[：:]([^】]+)】',title)
    return (m[1].replace('モノ_ループ','モノ・ループ'),m[2].strip()) if m else (fallback,title.strip())
def read_json(path,default):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return default
def excerpts(p):
    found={};heading=None;used=0
    with p.open(encoding='utf-8',errors='replace') as stream:
        for line in stream:
            if line.startswith('#'):
                heading=next((k for k in ['目的','現在地','次アクション','未解決','再開のしかた'] if re.match(r'^#{1,3}\s*'+k+r'(?:\s|[（(]|$)',line)),None);used=0
            elif heading and used<1100:
                clean=line.strip()
                if clean and not re.search(r'token|password|secret|api[_ -]?key|Bearer\s',clean,re.I):
                    clean=re.sub(r'https?://\S+','[リンクは原資料で確認]',clean)
                    found[heading]=(found.get(heading,'')+'\n'+clean[:500]).strip()[:1100];used+=len(clean)
    return found

def export():
    home=Path.home();runtime=home/'.claude/runtime';root=runtime/'ledger';sources=[];sessions=[];imports=[];errors=[]
    for p in sorted(root.rglob('*.md')) if root.exists() else []:
        rel=p.relative_to(root)
        if any(x.startswith(('.','_')) for x in rel.parts[:-1]):continue
        try:
            company,name=named(p.stem,rel.parts[0] if len(rel.parts)>1 else '未分類')
            sources.append({'id':uid('macmini-ledger-',str(rel)),'type':'案件台帳','machine':'Mac mini','name':name,'company':company,
                'updated':dt.datetime.fromtimestamp(p.stat().st_mtime,JST).isoformat(timespec='seconds'),'path':str(p),
                'sections':excerpts(p),'partial':p.stat().st_size>50000,'recorded_status':''})
        except OSError:errors.append('Mac miniの台帳を一部読めません。')
    board=read_json(runtime/'project_state.json',{})
    if not isinstance(board,dict):board={}
    for company,rows in board.items():
        if company.startswith('_') or not isinstance(rows,dict):continue
        for key,entry in rows.items():
            if not isinstance(entry,dict) or not entry.get('name'):continue
            sources.append({'id':uid('macmini-board-',company+'/'+key),'type':'進捗ボード','machine':'Mac mini','name':entry['name'],'company':company,
                'updated':entry.get('last_touched') or board.get('_updated') or '', 'recorded_status':entry.get('status',''),
                'sections':{'次アクション':str(entry.get('next_action') or '')},'path':str(runtime/'project_state.json'),'partial':False})
    titles=read_json(runtime/'session_titles_cache.json',{})
    if not isinstance(titles,dict):titles={}
    for p in sorted((home/'.claude/projects').glob('*/*.jsonl')):
        try:
            old=titles.get(str(p),{});title=str(old.get('title') or '') if isinstance(old,dict) else ''
            if isinstance(old,dict) and old.get('internal'):continue
            stat=p.stat()
            with p.open('rb') as f:f.seek(max(0,stat.st_size-24576));tail=f.read(24576).decode('utf-8',errors='replace')
            matches=re.findall(r'"customTitle"\s*:\s*("(?:[^"\\]|\\.)*")',tail)
            if matches:
                try:title=json.loads(matches[-1])
                except ValueError:pass
            if not title:continue
            company,name=named(title)
            sessions.append({'id':'macmini:claude:'+p.stem,'type':'Claude Code','machine':'Mac mini','title':title,'company':company,'project_name':name,
                'updated':dt.datetime.fromtimestamp(stat.st_mtime,JST).isoformat(timespec='seconds'),
                'observed_status':'会話記録あり・実行状態は未確認','snapshot_at':None})
        except OSError:errors.append('Mac miniの会話記録を一部読めません。')
    for kind,filename,key in [('タスクガント','gantt_cache.json','tasks'),('議事録タスク','meeting_ledger_cache.json','items')]:
        doc=read_json(runtime/filename,{})
        if not isinstance(doc,dict) or not isinstance(doc.get(key),list):continue
        if doc.get('error'):errors.append('Mac miniの'+kind+'の取得にエラーがあります。')
        for row in doc[key]:
            title=row.get('name' if key=='tasks' else 'title','')
            if not title:continue
            identity=str(row.get('id')) if key=='tasks' else str(row.get('extract_at',''))+'/'+str(row.get('meeting_title',''))+'/'+title
            imports.append({'id':uid('macmini-import-',filename+'/'+identity),'type':kind,'machine':'Mac mini','title':title,
                'updated':doc.get('updated',''),'status':str(row.get('st' if key=='tasks' else 'status','')),
                'deadline':str(row.get('end' if key=='tasks' else 'deadline','') or ''),
                'category':str(row.get('cat' if key=='tasks' else 'related_project','') or ''),'project_id':None,'path':str(runtime/filename)})
    return {'captured_at':dt.datetime.now(JST).isoformat(timespec='seconds'),'sources':sources,'sessions':sessions,'imported_tasks':imports,
        'errors':list(dict.fromkeys(errors)),'machine':'Mac mini','board_updated':board.get('_updated')}
print(json.dumps(export(),ensure_ascii=False))
