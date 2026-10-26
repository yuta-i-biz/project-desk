"""Prepare or activate a desktop-session worker. No login tokens are read/copied."""
import argparse,os,pathlib,plistlib,subprocess,sys
LABEL='local.projectdesk.claude-gui'
def definition(root):
 root=pathlib.Path(root).resolve()
 return {'Label':LABEL,'ProgramArguments':[sys.executable,str(root/'claude_bridge.py'),'--worker','--root',str(root)],'RunAtLoad':True,'KeepAlive':{'SuccessfulExit':False},'ThrottleInterval':60,'StandardOutPath':str(root/'data/claude-desktop.log'),'StandardErrorPath':str(root/'data/claude-desktop.log')}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parent);p.add_argument('--activate',action='store_true');a=p.parse_args();root=a.root.resolve();value=definition(root)
 if not a.activate:
  print(plistlib.dumps(value).decode());return
 if not (root/'claude_bridge.py').is_file() or not (root/'data/desk.sqlite3').is_file():raise SystemExit('Mac miniの反映済みアプリを指定してください。')
 folder=pathlib.Path.home()/'Library/LaunchAgents';folder.mkdir(exist_ok=True);path=folder/(LABEL+'.plist')
 if path.exists():raise SystemExit('設定は既に存在します。重複起動せず既存プロセスを確認してください。')
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(plistlib.dumps(value))
 r=subprocess.run(['launchctl','bootstrap','gui/'+str(os.getuid()),str(path)],capture_output=True)
 if r.returncode:path.unlink();raise SystemExit('画面側で起動できませんでした。設定は元に戻しました。')
 print('Claudeの画面側実行プロセスを起動しました。接続成功はアプリで別途確認します。')
if __name__=='__main__':main()
