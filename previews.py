"""Screen previews for authenticated artifacts; active HTML stays sandboxed."""
import csv,io,mimetypes
from attachments import text_of
MAX_PREVIEW=20*1024*1024
RAW={'.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp','.pdf':'application/pdf','.mp3':'audio/mpeg','.m4a':'audio/mp4','.wav':'audio/wav','.mp4':'video/mp4','.webm':'video/webm','.html':'text/html; charset=utf-8','.htm':'text/html; charset=utf-8'}
def describe(path,raw_url,root):
    if path.stat().st_size>MAX_PREVIEW:return {'kind':'unsupported','name':path.name,'message':'20MBを超える成果物はダウンロードして確認してください。'}
    ext=path.suffix.lower()
    if ext in RAW:
        kind='html' if ext in ('.html','.htm') else RAW[ext].split('/')[0]
        if ext=='.pdf':kind='pdf'
        return {'kind':kind,'name':path.name,'url':raw_url}
    text,status=text_of(path,root)
    if ext in ('.csv','.tsv'):
        rows=list(__import__('itertools').islice(csv.reader(io.StringIO(text),delimiter='\t' if ext=='.tsv' else ','),201))
        return {'kind':'table','name':path.name,'rows':[r[:30] for r in rows[:200]],'message':'先頭200行・30列までの表示です。'}
    return {'kind':'text' if text else 'unsupported','name':path.name,'text':text[:100000],'message':status+'。本文の表示です。元のレイアウトはダウンロードして確認できます。'}
