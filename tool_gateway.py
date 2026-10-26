"""A scoped read-only MCP bridge; secrets remain in the existing local config."""
import argparse,json,os,re,selectors,signal,subprocess,sys,time
from pathlib import Path
READ_TOOLS={'get_file_metadata':'file_id','read_file_content':'file_id','sheets_read':'spreadsheet_id','docs_get':'document_id','slides_get':'presentation_id'}

def file_ids(text):
 return sorted(set(re.findall(r'https://(?:docs\.google\.com/(?:document|spreadsheets|presentation)/d/|drive\.google\.com/file/d/)([A-Za-z0-9_-]{10,})',text or '')))

class Client:
 def __init__(self,config,env=None):
  if config.get('type','stdio')!='stdio' or not isinstance(config.get('command'),str):raise ValueError('stdio configuration required')
  self.p=subprocess.Popen([config['command'],*config.get('args',[])],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env={**(env or os.environ),**config.get('env',{})},bufsize=0,start_new_session=True)
  self.selector=selectors.DefaultSelector();self.selector.register(self.p.stdout,selectors.EVENT_READ);self.buf=b'';self.counter=0
  self.call('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'ProjectDeskReadOnly','version':'1'}})
  self.send({'jsonrpc':'2.0','method':'notifications/initialized'})
 def send(self,obj):self.p.stdin.write((json.dumps(obj)+'\n').encode());self.p.stdin.flush()
 def call(self,method,params=None,timeout=30):
  self.counter+=1;ident=self.counter;self.send({'jsonrpc':'2.0','id':ident,'method':method,'params':params or {}});until=time.monotonic()+timeout
  while time.monotonic()<until:
   while b'\n' in self.buf:
    line,self.buf=self.buf.split(b'\n',1)
    try:a=json.loads(line)
    except ValueError:continue
    if isinstance(a,dict) and a.get('id')==ident:
     if 'error' in a:raise RuntimeError('MCP server returned an error')
     return a.get('result',{})
   if self.p.poll() is not None:raise RuntimeError('MCP server stopped')
   if self.selector.select(.25):self.buf+=os.read(self.p.stdout.fileno(),65536)
   if len(self.buf)>2*1024*1024:raise ValueError('MCP response too large')
  raise TimeoutError('MCP server timeout')
 def close(self):
  self.selector.close()
  if self.p.poll() is None:
   os.killpg(self.p.pid,signal.SIGTERM)
   try:self.p.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(self.p.pid,signal.SIGKILL);self.p.wait()
  self.p.stdin.close();self.p.stdout.close()

class Gateway:
 def __init__(self,upstream,allowed):self.upstream=upstream;self.allowed=set(allowed)
 def handle(self,method,params):
  if method=='initialize':return {'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'ProjectDeskScopedReadOnly','version':'1'}}
  if method=='ping':return {}
  if method=='tools/list':
   tools=self.upstream.call('tools/list').get('tools',[])
   return {'tools':[{**t,'annotations':{'readOnlyHint':True,'destructiveHint':False}} for t in tools if t.get('name') in READ_TOOLS and self.allowed]}
  if method=='tools/call':
   name=params.get('name');args=params.get('arguments')
   if name not in READ_TOOLS or not isinstance(args,dict) or args.get(READ_TOOLS[name]) not in self.allowed:raise ValueError('この案件の明示された資料の読取りだけ利用できます。')
   args=dict(args)
   if name=='get_file_metadata':args['fields']='id,name,mimeType,modifiedTime,size,webViewLink'
   return self.upstream.call('tools/call',{'name':name,'arguments':args})
  raise ValueError('Unsupported MCP operation')

def codex_config(home,folder,prompt):
 ids=file_ids(prompt)
 if not ids:return []
 source=home/'.claude.json'
 try:config=json.loads(source.read_text()).get('mcpServers',{}).get('google-services')
 except (OSError,ValueError):return []
 if not config:return []
 scope=folder/'tool_scope.json';scope.write_text(json.dumps({'file_ids':ids}));os.chmod(scope,0o600)
 args=[str(Path(__file__).resolve()),'--home',str(home),'--scope',str(scope)]
 return ['-c','mcp_servers.project_desk_readonly.command='+json.dumps(sys.executable),'-c','mcp_servers.project_desk_readonly.args='+json.dumps(args)]

def main():
 p=argparse.ArgumentParser();p.add_argument('--home',type=Path,required=True);p.add_argument('--scope',type=Path,required=True);a=p.parse_args()
 records=json.loads((a.home/'.claude.json').read_text());scope=json.loads(a.scope.read_text());ids=scope.get('file_ids',[])
 if not isinstance(ids,list) or not all(isinstance(i,str) and re.fullmatch('[A-Za-z0-9_-]{10,}',i) for i in ids):raise ValueError('invalid scope')
 from execution import environment
 client=Client(records['mcpServers']['google-services'],environment(a.home));gateway=Gateway(client,ids)
 try:
  for line in sys.stdin:
   try:
    if len(line)>1024*1024:raise ValueError('request too large')
    request=json.loads(line)
    if 'id' not in request:continue
    try:answer={'jsonrpc':'2.0','id':request['id'],'result':gateway.handle(request.get('method'),request.get('params',{}))}
    except Exception:answer={'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':'許可された資料の読取りを完了できませんでした。操作・接続・範囲を確認してください。'}}
    print(json.dumps(answer,ensure_ascii=False),flush=True)
   except ValueError:continue
 finally:client.close()
if __name__=='__main__':main()

def disabled_mcp_config(binary,env):
 r=subprocess.run([binary,'mcp','list','--json'],env=env,capture_output=True,text=True,timeout=20)
 if r.returncode:raise RuntimeError('自動工程のツール制限を確認できないため停止しました。')
 try:records=json.loads(r.stdout)
 except ValueError:raise RuntimeError('自動工程のツール設定を読み取れません。')
 if not isinstance(records,list):raise RuntimeError('自動工程のツール設定が不正です。')
 flags=[]
 for item in records:
  name=item.get('name') if isinstance(item,dict) else None
  if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',name):raise RuntimeError('自動工程のツール名を確認できません。')
  flags+=['-c','mcp_servers.'+name+'.command="/usr/bin/false"','-c','mcp_servers.'+name+'.args=[]','-c','mcp_servers.'+name+'.enabled=false']
 check=subprocess.run([binary,*flags,'mcp','list','--json'],env=env,capture_output=True,text=True,timeout=20)
 try:effective=json.loads(check.stdout)
 except ValueError:raise RuntimeError('自動工程の実効ツール制限を確認できません。')
 if check.returncode or not isinstance(effective,list) or any(not isinstance(i,dict) or i.get('enabled') is not False for i in effective):raise RuntimeError('自動工程のツールが無効になっていないため停止しました。')
 return flags
