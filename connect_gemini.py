"""One-shot subscription sign-in validation. Never reads credential contents."""
import json,re,subprocess,time
from pathlib import Path
from execution import environment
from gemini_adapter import binary,response
from auth_status import refresh
ROOT=Path(__file__).resolve().parent

def main():
    home=Path.home();env=environment(home);folder=ROOT/'data/gemini-auth-probe';folder.mkdir(mode=0o700,exist_ok=True)
    result=subprocess.run([str(binary(ROOT)),'models'],capture_output=True,text=True,env=env,timeout=30)
    models=re.findall(r'(?m)^\s*(gemini-[\w.-]+)\b',re.sub(r'\x1b\[[0-9;]*m','',result.stdout))
    if result.returncode or not models:
        (ROOT/'data/gemini_probe.json').write_text(json.dumps({'ok':False,'checked_at':time.time()}));refresh(ROOT/'data',home)
        print('Geminiのログインが未確認です。接続設定でGoogleへのログインを完了してください。');return 1
    model=models[0]
    command=[str(binary(ROOT)),'-p','接続確認です。GEMINI_DESK_OK の1行だけ返してください。外部ツールは使わない。','--model',model,'--output-format','json','--mode','plan','--sandbox','--disable-slash-commands','--print-timeout','1m']
    result=subprocess.run(command,cwd=folder,capture_output=True,text=True,env=env,timeout=90)
    ok=result.returncode==0 and response(result.stdout).strip()=='GEMINI_DESK_OK'
    (ROOT/'data/gemini_probe.json').write_text(json.dumps({'ok':ok,'checked_at':time.time(),'model':model,'exit_code':result.returncode}))
    refresh(ROOT/'data',home)
    print('Gemini接続を確認しました。画面の更新後、おまかせの候補になります。' if ok else '応答確認が完了しませんでした。案件資料は渡していません。')
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
