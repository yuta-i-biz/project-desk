"""Read-only launchd inventory. Exit zero is not evidence of business success."""
import datetime as dt,os,plistlib,re,subprocess,threading,time
from pathlib import Path
PREFIXES=('com.imagawa.','com.jibun.','com.claude.','com.ml-','local.projectdesk.')
_CACHE={};LOCK=threading.Lock()
NAMES={'com.imagawa.plaud-daily':'Plaud取得・タスク仕分け・夜間実行','local.projectdesk.claude-gui':'Claudeの画面側接続','com.imagawa.morning-regression':'朝の動作検証','com.imagawa.note-daily':'noteの定期処理','com.imagawa.morning-briefing':'朝の業務確認'}
def parse_state(raw):
 state=re.search(r'^\s*state = (.+)$',raw,re.M);code=re.search(r'^\s*last exit code = (-?\d+)',raw,re.M);runs=re.search(r'^\s*runs = (\d+)',raw,re.M)
 return {'process_state':state.group(1) if state else 'unknown','last_exit':int(code.group(1)) if code else None,'runs':int(runs.group(1)) if runs else None}
def collect(home,runner=subprocess.run):
 home=Path(home);rows=[]
 for p in sorted((home/'Library/LaunchAgents').glob('*.plist')):
  if not p.name.startswith(PREFIXES):continue
  try:
   if p.is_symlink() or p.stat().st_size>128000:raise ValueError()
   cfg=plistlib.loads(p.read_bytes());label=cfg.get('Label','')
   if not isinstance(label,str) or not label.startswith(PREFIXES) or not re.fullmatch(r'[A-Za-z0-9_.-]+',label):continue
   r=runner(['launchctl','print','gui/'+str(os.getuid())+'/'+label],capture_output=True,text=True,timeout=3)
   info=parse_state(r.stdout) if r.returncode==0 else {'process_state':'unavailable','last_exit':None,'runs':None}
   status='running' if info['process_state']=='running' else 'failed' if info['last_exit'] not in (None,0) else 'idle' if r.returncode==0 else 'unknown'
   evidence=[]
   for k in ['StandardOutPath','StandardErrorPath']:
    path=Path(str(cfg.get(k,'')))
    # File timestamps only; never read log contents or environment/arguments.
    if path.is_absolute() and path.is_file() and not path.is_symlink():evidence.append(dt.datetime.fromtimestamp(path.stat().st_mtime,dt.timezone.utc).isoformat())
   missing=[]
   for arg in cfg.get('ProgramArguments',[]):
    if isinstance(arg,str) and arg.startswith('/') and arg.endswith(('.py','.sh')) and not Path(arg).is_file():missing.append(Path(arg).name)
   schedule={k:cfg[k] for k in ['StartCalendarInterval','StartInterval','RunAtLoad','KeepAlive'] if k in cfg}
   rows.append({'id':label,'name':NAMES.get(label,label),'status':status,**info,'schedule':schedule,'missing_files':missing,'next_action':'起動先のファイルと現在の保存場所を照合し、変更案を準備する。' if missing else '前回失敗が現在も再現するか確認する。' if status=='failed' else '', 'last_log_update':max(evidence) if evidence else None,'note':'終了番号は処理内容の正しさを保証しません。待機中は停止障害とは限りません。'})
  except (OSError,ValueError,subprocess.SubprocessError,plistlib.InvalidFileException):rows.append({'id':p.stem,'name':p.stem,'status':'unknown','note':'設定または起動状態を読み取れません。'})
 return {'captured_at':dt.datetime.now(dt.timezone.utc).isoformat(),'machine':'この端末','rows':rows,'scope':'ユーザーの業務用LaunchAgentsのみ。Cloud Run・GAS等の定期処理は対象外。'}
def snapshot(home):
 key=str(home)
 with LOCK:
  old=_CACHE.get(key)
  if old and time.monotonic()-old[0]<60:return old[1]
  result=collect(home);_CACHE[key]=(time.monotonic(),result);return result
