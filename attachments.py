"""Bounded file intake, readable previews and project-local storage. Never execute uploads."""
import hashlib,json,mimetypes,os,re,secrets,subprocess,zipfile,threading,sys,codecs
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree
MAX_FILE=50*1024*1024
POOL=ThreadPoolExecutor(max_workers=1)
NATIVE_LOCK=threading.Lock()

def record_path(desk,uid):
    if not re.fullmatch(r'[0-9a-f]{32}',str(uid)):raise ValueError('添付IDが不正です。')
    return desk.data/'uploads'/uid/'record.json'
def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));os.replace(tmp,path)
def records(desk):
    out=[]
    for p in (desk.data/'uploads').glob('*/record.json'):
        try:out.append(json.loads(p.read_text()))
        except (OSError,ValueError):continue
    return sorted(out,key=lambda r:r.get('created',''),reverse=True)
def public_records(desk):
    return [{k:r.get(k) for k in ('id','name','size','project_id','project_name','company','read_status','drive_status','drive_url','folder_url','error','created')} for r in records(desk)]
def text_of(path,root=None):
    ext=path.suffix.lower();partial=False
    if ext=='.xlsx':
        chunks=[]
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist())>40*1024*1024:raise ValueError('展開後の表が大きすぎます。')
            strings=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                strings=[''.join(t.text or '' for t in item.iter() if t.tag.endswith('}t')) for item in ElementTree.fromstring(z.read('xl/sharedStrings.xml'))]
            for name in sorted(n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+.xml',n))[:50]:
                chunks.append(name)
                for row in ElementTree.fromstring(z.read(name)).iter():
                    if row.tag.rsplit('}',1)[-1]!='row':continue
                    values=[]
                    for cell in row:
                        value=''.join(t.text or '' for t in cell.iter() if t.tag.rsplit('}',1)[-1] in ('v','t'))
                        if cell.get('t')=='s':
                            try:value=strings[int(value)]
                            except (ValueError,IndexError):value='読取要確認'
                        values.append(cell.get('r','')+'='+value)
                    chunks.append(' | '.join(values))
                    if len(chunks)>3000:partial=True;break
                if partial:break
        text='\n'.join(chunks)
        return text[:100000],'一部読取' if partial or len(text)>100000 else '読取済み'
    if ext in ('.docx','.xlsx','.pptx','.odt','.ods','.odp'):
        chunks=[]
        with zipfile.ZipFile(path) as z:
            infos=[i for i in z.infolist() if i.filename.endswith('.xml') and re.match(r'word/(document|header|footer)|xl/(sharedStrings|worksheets/sheet)|ppt/slides/slide|content.xml',i.filename)]
            if sum(i.file_size for i in infos)>40*1024*1024:raise ValueError('展開後の文書が大きすぎます。原本を保管しました。')
            for info in infos[:80]:
                tree=ElementTree.fromstring(z.read(info));chunks.append(info.filename+'\n'+' '.join(x.text for x in tree.iter() if x.text and x.tag.rsplit('}',1)[-1] in ('t','v','p')))
                if sum(map(len,chunks))>100000:partial=True;break
        return '\n'.join(chunks)[:100000], '一部読取' if partial else '読取済み'
    if ext in ('.pdf','.png','.jpg','.jpeg','.webp','.heic','.tiff','.bmp'):
        reader=(root or Path(__file__).parent)/'vendor/file_reader'
        source=reader.parent.parent/'native/file_reader.swift'
        if not reader.exists() and source.exists() and sys.platform=='darwin':
            with NATIVE_LOCK:
                if not reader.exists():
                    reader.parent.mkdir(parents=True,exist_ok=True)
                    subprocess.run(['/usr/bin/swiftc',str(source),'-o',str(reader)],capture_output=True,timeout=90,check=True)
        if reader.exists():
            p=subprocess.run([str(reader),str(path)],capture_output=True,text=True,timeout=120)
            if p.returncode:raise ValueError('PDF・画像の読取りに失敗しました。暗号化や形式を確認してください。')
            value=json.loads(p.stdout);return value['text'][:100000],value['status']
        return '', '読取機能の準備待ち'
    if ext in ('.doc','.rtf'):
        p=subprocess.run(['/usr/bin/textutil','-convert','txt','-stdout',str(path)],capture_output=True,timeout=30)
        if p.returncode:raise ValueError('文書の読取りに失敗しました。')
        return p.stdout.decode('utf-8',errors='replace')[:100000],'一部読取' if len(p.stdout)>100000 else '読取済み'
    if ext=='.zip':
        with zipfile.ZipFile(path) as z:return '\n'.join(i.filename for i in z.infolist()[:500]),'ZIP内の一覧のみ（展開・実行なし）'
    raw=path.read_bytes()[:100001]
    if b'\0' not in raw:
        for encoding in ('utf-8-sig','cp932'):
            try:return codecs.getincrementaldecoder(encoding)(errors='strict').decode(raw[:100000],final=path.stat().st_size<=100000), '一部読取' if path.stat().st_size>100000 else '読取済み'
            except UnicodeDecodeError:pass
    return '', '保管済み・内容読取は未対応'

def classify(projects,name,text,pid=''):
    if pid:
        p=next((p for p in projects if p['id']==pid and not p.get('reference_only')),None)
        if not p:raise ValueError('保存先の案件が見つかりません。')
        return p
    hay=(name+' '+text[:12000]).casefold();scores=[]
    for p in projects:
        if p.get('reference_only') or p.get('company')=='全体':continue
        title=p['name'].casefold();tokens=[t for t in re.split(r'[\s_｜：:（）()・/]+',title) if len(t)>=3]
        score=(100 if len(title)>=3 and title in hay else 0)+sum(len(t) for t in tokens if t in hay)
        if score:scores.append((score,p))
    scores.sort(key=lambda x:-x[0])
    if scores and (len(scores)==1 or scores[0][0]>=scores[1][0]+5):return scores[0][1]
    return None

def receive(desk,name,body,pid=''):
    if not body or len(body)>MAX_FILE:raise ValueError('ファイルは1件50MBまでです。')
    name=Path(str(name).replace('\\','/')).name.replace('\0','')[:180]
    suffix=Path(name).suffix[:20]
    if len(name.encode('utf-8'))>240:
        stem=name[:-len(suffix)] if suffix else name
        while len((stem+suffix).encode('utf-8'))>240:stem=stem[:-1]
        name=stem+suffix
    if not name or name in ('.','..'):raise ValueError('ファイル名が不正です。')
    if pid:classify(desk.collect()['projects'],name,'',pid)
    uid=secrets.token_hex(16);folder=desk.data/'uploads'/uid;folder.mkdir(parents=True,mode=0o700);(folder/'original').mkdir(mode=0o700);path=folder/'original'/name;path.write_bytes(body);os.chmod(path,0o600)
    text='';status='読取待ち';error=''
    try:text,status=text_of(path,desk.data.parent)
    except Exception as e:status='保管済み・読取要確認';error=str(e)[:200]
    project=classify(desk.collect()['projects'],name,text,pid)
    import datetime
    r={'id':uid,'name':name,'size':len(body),'sha256':hashlib.sha256(body).hexdigest(),'project_id':project['id'] if project else '', 'project_name':project['name'] if project else '要分類','company':project['company'] if project else '未分類','read_status':status,'drive_status':'保存待ち','error':error,'created':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (folder/'preview.txt').write_text(text);save(folder/'record.json',r);POOL.submit(store_drive,desk,uid)
    return {k:v for k,v in r.items() if k!='sha256'}

def store_drive(desk,uid):
    path=record_path(desk,uid);r=json.loads(path.read_text())
    try:
        from drive_store import store
        result=store(desk,r,path.parent/'original'/r['name'],lambda:save(path,r));r.update(result);r['drive_status']='Drive格納済み';r['error']=''
    except (Exception,SystemExit):r['drive_status']='Drive保存待ち・要確認';r['error']='Googleドライブへの保存を確認できません。再試行してください。ローカルの原本は保持しています。'
    save(path,r)

def context(desk,ids,pid,global_scope=False):
    if not isinstance(ids,list) or len(ids)>10:raise ValueError('添付は10件以内にしてください。')
    available={r['id']:r for r in records(desk)};result=[]
    for uid in ids:
        r=available.get(uid)
        if not r or (not global_scope and r['project_id']!=pid):raise ValueError('別案件の添付はこの依頼に渡せません。')
        path=record_path(desk,uid).parent
        result.append({'id':uid,'name':r['name'],'read_status':r['read_status'],'drive_url':r.get('drive_url'),'text':(path/'preview.txt').read_text()[:16000],'preview_only':True,'original_in_request_folder':True})
    return result

def resume_pending(desk):
    for r in records(desk):
        if r.get('drive_status')=='保存待ち':POOL.submit(store_drive,desk,r['id'])
