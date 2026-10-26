"""Drive storage using the existing Mac mini OAuth connection; no AI API keys."""
import hashlib,json,mimetypes,sys
from pathlib import Path

def service():
    sys.path.insert(0,str(Path.home()/'.claude/tools'))
    from google_auth import get_credentials
    from googleapiclient.discovery import build
    return build('drive','v3',credentials=get_credentials(['https://www.googleapis.com/auth/drive']),cache_discovery=False)
def escape(value):return str(value).replace('\\','\\\\').replace("'","\\'")
def folder(drive,name,parent='root'):
    q="trashed = false and mimeType = 'application/vnd.google-apps.folder' and name = '"+escape(name)+"' and '"+escape(parent)+"' in parents and 'me' in owners"
    files=drive.files().list(q=q,pageSize=100,fields='files(id,name,shared,webViewLink)',supportsAllDrives=True).execute().get('files',[])
    private=[f for f in files if not f.get('shared')]
    if private:return sorted(private,key=lambda f:f['id'])[0]
    created=drive.files().create(body={'name':name,'mimeType':'application/vnd.google-apps.folder','parents':[parent]},fields='id,name,webViewLink').execute()
    return drive.files().get(fileId=created['id'],fields='id,name,shared,webViewLink').execute()
def store(desk,record,path,persist):
    from googleapiclient.http import MediaFileUpload
    drive=service();root=folder(drive,'Project Desk');company=folder(drive,record['company'],root['id']);project=folder(drive,record['project_name'],company['id'])
    # Persist generated ID before upload, so an ambiguous network failure cannot create duplicates.
    if not record.get('drive_id'):
        record['drive_id']=drive.files().generateIds(count=1,space='drive',type='files').execute()['ids'][0];persist()
    fid=record['drive_id']
    try:meta=drive.files().get(fileId=fid,fields='id,size,md5Checksum,webViewLink,parents').execute()
    except Exception as e:
        if getattr(e,'resp',None) is None or e.resp.status!=404:raise
        media=MediaFileUpload(str(path),mimetype=mimetypes.guess_type(record['name'])[0] or 'application/octet-stream',resumable=True)
        drive.files().create(body={'id':fid,'name':record['name'],'parents':[project['id']],'appProperties':{'projectDeskUpload':record['id']}},media_body=media,fields='id').execute()
        meta=drive.files().get(fileId=fid,fields='id,size,md5Checksum,webViewLink,parents').execute()
    if int(meta.get('size',-1))!=path.stat().st_size or meta.get('md5Checksum')!=hashlib.md5(path.read_bytes()).hexdigest():raise ValueError('Driveの内容照合に失敗しました。')
    return {'drive_url':meta['webViewLink'],'folder_url':project['webViewLink']}
