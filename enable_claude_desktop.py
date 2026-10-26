"""Install the desktop worker in standard Application Support storage."""
import argparse,os,pathlib,plistlib,shutil,subprocess,sys
LABEL='local.projectdesk.claude-gui'
FILES=('claude_bridge.py','auth_status.py','execution.py','scheduler.py')
def definition(root):
 root=pathlib.Path(root).resolve()
 return {'Label':LABEL,'ProgramArguments':[sys.executable,str(root/'claude_bridge.py'),'--worker','--root',str(root)],'RunAtLoad':True,'KeepAlive':{'SuccessfulExit':False},'ThrottleInterval':60,'StandardOutPath':str(root/'data/claude-desktop.log'),'StandardErrorPath':str(root/'data/claude-desktop.log')}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parent);p.add_argument('--activate',action='store_true');a=p.parse_args();root=a.root.resolve();service=pathlib.Path.home()/'Library/Application Support/Project Desk Claude';value=definition(service)
 if not a.activate:print(plistlib.dumps(value).decode());return
 if not all((root/f).is_file() for f in FILES) or not (root/'data/desk.sqlite3').is_file():raise SystemExit('Mac miniの反映済みアプリを指定してください。')
 folder=pathlib.Path.home()/'Library/LaunchAgents';folder.mkdir(exist_ok=True);path=folder/(LABEL+'.plist')
 old=path.read_bytes() if path.exists() else None
 if old:
  previous=plistlib.loads(old);args=previous.get('ProgramArguments',[])
  if previous.get('Label')!=LABEL or len(args)<2 or pathlib.Path(args[1]) not in (root/'claude_bridge.py',service/'claude_bridge.py'):raise SystemExit('既存の別設定は変更しません。')
  r=subprocess.run(['launchctl','bootout','gui/'+str(os.getuid())+'/'+LABEL],capture_output=True)
 service.mkdir(parents=True,exist_ok=True,mode=0o700);(service/'data').mkdir(mode=0o700,exist_ok=True)
 for name in FILES:shutil.copy2(root/name,service/name)
 from claude_bridge import atomic
 atomic(root/'data/claude_desktop.json',{'data':str(service/'data')})
 temp=path.with_suffix('.tmp');temp.write_bytes(plistlib.dumps(value));os.chmod(temp,0o600);os.replace(temp,path)
 r=subprocess.run(['launchctl','bootstrap','gui/'+str(os.getuid()),str(path)],capture_output=True)
 if r.returncode:
  if old:path.write_bytes(old)
  else:path.unlink()
  raise SystemExit('画面側で起動できませんでした。設定を確認してください。')
 print('Claudeの専用プロセスを起動しました。実応答はアプリから確認します。')
if __name__=='__main__':main()
