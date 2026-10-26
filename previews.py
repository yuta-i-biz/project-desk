"""Screen previews for authenticated artifacts; active HTML stays sandboxed."""
import csv,io,mimetypes,hashlib,json,subprocess,threading
from attachments import text_of
MAX_PREVIEW=20*1024*1024
PDF_LOCK=threading.Lock()
RAW={'.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp','.pdf':'application/pdf','.mp3':'audio/mpeg','.m4a':'audio/mp4','.wav':'audio/wav','.mp4':'video/mp4','.webm':'video/webm','.html':'text/html; charset=utf-8','.htm':'text/html; charset=utf-8'}
def pdf_pages(path,root):
    key=hashlib.sha256((str(path.resolve())+str(path.stat().st_mtime_ns)+str(path.stat().st_size)).encode()).hexdigest()
    folder=root/'data/preview_cache'/key;manifest=folder/'manifest.json';reader=root/'vendor/file_reader'
    with PDF_LOCK:
        if not manifest.exists():
            folder.mkdir(parents=True,exist_ok=True,mode=0o700)
            result=subprocess.run([str(reader),str(path),'--render',str(folder)],capture_output=True,text=True,timeout=120,check=True)
            value=json.loads(result.stdout)
            if not value.get('pages'):raise ValueError('PDFページを取得できませんでした。')
            manifest.write_text(json.dumps(value))
    return folder,json.loads(manifest.read_text())

def describe(path,raw_url,root):
    if path.stat().st_size>MAX_PREVIEW:return {'kind':'unsupported','name':path.name,'message':'20MBを超える成果物はダウンロードして確認してください。'}
    ext=path.suffix.lower()
    if ext in RAW:
        kind='html' if ext in ('.html','.htm') else RAW[ext].split('/')[0]
        if ext=='.pdf':
            try:
                folder,data=pdf_pages(path,root)
                return {'kind':'pdf','name':path.name,'pages':[raw_url+'&page='+str(i+1) for i in range(len(data['pages']))],'message':str(data['total'])+'ページのPDF。画面内では先頭'+str(len(data['pages']))+'ページを表示します。'}
            except Exception:return {'kind':'unsupported','name':path.name,'message':'PDFの画面内表示を準備できませんでした。元のファイルをダウンロードして確認してください。'}
        return {'kind':kind,'name':path.name,'url':raw_url}
    text,status=text_of(path,root)
    if ext in ('.csv','.tsv'):
        rows=list(__import__('itertools').islice(csv.reader(io.StringIO(text),delimiter='\t' if ext=='.tsv' else ','),201))
        return {'kind':'table','name':path.name,'rows':[r[:30] for r in rows[:200]],'message':'先頭200行・30列までの表示です。'}
    return {'kind':'text' if text else 'unsupported','name':path.name,'text':text[:100000],'message':status+'。本文の表示です。元のレイアウトはダウンロードして確認できます。'}
