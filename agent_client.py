"""Agent-neutral client; uses the same project/task API as the browser."""
import http.cookiejar
import json
from pathlib import Path
import re
import urllib.request

def call(action,payload=None,data=None):
    data=Path(data) if data else Path(__file__).resolve().parent/'data'
    config=json.loads((data/'authority.json').read_text())
    origin=config['server_url'].rstrip('/')
    code=json.loads((data/'access.json').read_text())['code']
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(origin+'/',timeout=30) as response:html=response.read().decode()
    match=re.search(r'name="desk-token" content="([^"]+)"',html)
    if not match:raise RuntimeError('管理画面の接続情報を読み取れません。')
    headers={'Content-Type':'application/json','Origin':origin,'X-Desk-Token':match.group(1)}
    req=urllib.request.Request(origin+'/api/login',data=json.dumps({'code':code}).encode(),headers=headers)
    with opener.open(req,timeout=30) as response:json.load(response)
    if action=='state':
        with opener.open(origin+'/api/state',timeout=30) as response:return json.load(response)
    paths={'project':'/api/projects','create':'/api/tasks','update':'/api/tasks/update','bind':'/api/bind'}
    req=urllib.request.Request(origin+paths[action],data=json.dumps(payload,ensure_ascii=False).encode(),headers=headers)
    with opener.open(req,timeout=30) as response:return json.load(response)
