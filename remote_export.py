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
    found={};heading=None;used=0;private=False
    with p.open(encoding='utf-8',errors='replace') as stream:
        for line in stream:
            if re.search(r'-----BEGIN .*PRIVATE KEY-----',line):private=True;continue
            if private:
                if re.search(r'-----END .*PRIVATE KEY-----',line):private=False
                continue
            if line.startswith('#'):
                heading=next((k for k in ['目的','現在地','次アクション','未解決','再開のしかた'] if re.match(r'^#{1,3}\s*'+k+r'(?:\s|[（(]|$)',line)),None);used=0
            elif heading and used<1100:
                clean=line.strip()
                if clean and not re.search(r'token|password|secret|api[_ -]?key|Bearer\s',clean,re.I):
                    clean=re.sub(r'https?://\S+','[リンクは原資料で確認]',clean)
                    found[heading]=(found.get(heading,'')+'\n'+clean[:500]).strip()[:1100];used+=len(clean)
    return found

def scrub(text):
    text=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----','[秘密鍵省略]',text,flags=re.S)
    text=re.sub(r'(?im)^([^\n]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret|認証トークン)\s*[:=]\s*).+$',r'\1[秘密情報省略]',text)
    return re.sub(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_-]{25,})\b','[秘密情報省略]',text)

def scan_sessions(home,machine,cache=None):
    root=Path(home)/'.claude/projects';titles=read_json(Path(home)/'.claude/runtime/session_titles_cache.json',{})
    if not isinstance(titles,dict):titles={}
    sessions=[];errors=[];coverage={'total':0,'internal_excluded':0,'untitled_included':0}
    for p in sorted(root.glob('*/*.jsonl')):
        coverage['total']+=1
        old=titles.get(str(p),{})
        if not isinstance(old,dict):old={}
        if old.get('internal'):coverage['internal_excluded']+=1;continue
        try:
            if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):raise OSError('linked session')
            stat=p.stat();signature=[stat.st_size,stat.st_mtime_ns,hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()]
            cached=cache.get(str(p),{}) if isinstance(cache,dict) else {}
            if isinstance(cached,dict) and isinstance(cached.get('session'),dict) and cached.get('signature')==signature and cached.get('session',{}).get('machine')==machine:
                record=dict(cached['session']);sessions.append(record);coverage['untitled_included']+=int(record.get('untitled',False));continue
            with p.open('rb') as stream:
                head=stream.read(65536).decode('utf-8',errors='replace');stream.seek(max(0,stat.st_size-24576));tail=stream.read(24576).decode('utf-8',errors='replace')
            title=str(old.get('title') or '');matches=re.findall(r'"customTitle"\s*:\s*("(?:[^"\\]|\\.)*")',tail)
            if matches:title=json.loads(matches[-1])
            cwd=''
            for line in head.splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                if isinstance(event,dict) and isinstance(event.get('cwd'),str):cwd=event['cwd'];break
            untitled=not title
            if untitled:
                coverage['untitled_included']+=1;title='所属未確認｜'+(Path(cwd).name if cwd else '作業フォルダ未確認')+'｜'+p.stem[:8]
            company,name=named(title)
            sessions.append({'id':('macmini:claude:' if machine=='Mac mini' else 'claude:')+p.stem,'type':'Claude Code','machine':machine,'title':scrub(title),'company':company,'project_name':name,'cwd':cwd,'untitled':untitled,'metadata_only':True,'updated':dt.datetime.fromtimestamp(stat.st_mtime,JST).isoformat(timespec='seconds'),'observed_status':'会話記録あり・実行状態は未確認','snapshot_at':None})
            if isinstance(cache,dict):cache[str(p)]={'signature':signature,'session':sessions[-1]}
        except (OSError,ValueError):errors.append(machine+'の会話記録を一部読めません。')
    return sessions,coverage,errors

def export(home=None,machine='Mac mini',include_documents=False,session_cache=None):
    home=Path(home or Path.home());runtime=home/'.claude/runtime';root=runtime/'ledger';sources=[];sessions=[];imports=[];errors=[];warnings=[];documents=[]
    prefix='macmini-' if machine=='Mac mini' else ''
    if not root.is_dir():errors.append('案件台帳フォルダを確認できません。')
    for p in sorted(root.rglob('*.md')) if root.exists() else []:
        rel=p.relative_to(root)
        if any(x.startswith(('.','_')) for x in rel.parts[:-1]):continue
        try:
            if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):raise OSError('linked ledger')
            company,name=named(p.stem,rel.parts[0] if len(rel.parts)>1 else '未分類')
            sources.append({'id':uid(prefix+'ledger-',str(rel)),'type':'案件台帳','machine':machine,'name':name,'company':company,
                'updated':dt.datetime.fromtimestamp(p.stat().st_mtime,JST).isoformat(timespec='seconds'),'path':str(p),
                'sections':excerpts(p),'partial':p.stat().st_size>50000,'recorded_status':''})
            if include_documents:
                text=scrub(p.read_text(errors='replace'));digest=hashlib.sha256(text.encode()).hexdigest()
                documents.append({'source_id':sources[-1]['id'],'sha256':digest,'text':text})
        except OSError:errors.append(machine+'の台帳を一部読めません。')
    board=read_json(runtime/'project_state.json',{})
    if not isinstance(board,dict):board={}
    for company,rows in board.items():
        if company.startswith('_') or not isinstance(rows,dict):continue
        for key,entry in rows.items():
            if not isinstance(entry,dict) or not entry.get('name'):continue
            sources.append({'id':uid(prefix+'board-',company+'/'+key),'type':'進捗ボード','machine':machine,'name':entry['name'],'company':company,
                'updated':entry.get('last_touched') or board.get('_updated') or '', 'recorded_status':entry.get('status',''),
                'sections':{'次アクション':str(entry.get('next_action') or '')},'path':str(runtime/'project_state.json'),'partial':False})
    sessions,coverage,session_errors=scan_sessions(home,machine,session_cache)
    errors.extend(session_errors)
    for kind,filename,key in [('タスクガント','gantt_cache.json','tasks'),('議事録タスク','meeting_ledger_cache.json','items')]:
        doc=read_json(runtime/filename,{})
        if not isinstance(doc,dict) or not isinstance(doc.get(key),list):continue
        if doc.get('error'):warnings.append(machine+'の'+kind+'の取得にエラーがあります（元キャッシュの状態）。')
        for row in doc[key]:
            title=row.get('name' if key=='tasks' else 'title','')
            if not title:continue
            identity=str(row.get('id')) if key=='tasks' else str(row.get('extract_at',''))+'/'+str(row.get('meeting_title',''))+'/'+title
            imports.append({'id':uid(prefix+'import-',filename+'/'+identity),'type':kind,'machine':machine,'title':title,
                'updated':doc.get('updated',''),'status':str(row.get('st' if key=='tasks' else 'status','')),
                'deadline':str(row.get('end' if key=='tasks' else 'deadline','') or ''),
                'category':str(row.get('cat' if key=='tasks' else 'related_project','') or ''),'project_id':None,'path':str(runtime/filename)})
    return {'captured_at':dt.datetime.now(JST).isoformat(timespec='seconds'),'sources':sources,'sessions':sessions,'imported_tasks':imports,
        'errors':list(dict.fromkeys(errors)),'machine':machine,'board_updated':board.get('_updated'),'documents':documents,'coverage':coverage,'warnings':warnings,'scope':'Claude Codeの案件台帳とセッション一覧。会話本文・認証設定は含まない。'}
if __name__=='__main__':print(json.dumps(export(),ensure_ascii=False))
