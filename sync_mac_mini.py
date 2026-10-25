"""Fetch read-only records over the existing mac-mini SSH alias."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parent
JST=dt.timezone(dt.timedelta(hours=9))
def sync(data=ROOT/'data'):
    data=Path(data);data.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now(JST).isoformat(timespec='seconds')
    try:
        result=subprocess.run(['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','mac-mini','python3','-'],
            input=(ROOT/'remote_export.py').read_text(),text=True,capture_output=True,timeout=40)
        if result.returncode:raise RuntimeError('SSH接続を確認してください。')
        payload=json.loads(result.stdout)
        if not isinstance(payload,dict) or not isinstance(payload.get('sources'),list):raise ValueError('Unexpected export')
        temp=data/'mac_mini.tmp';temp.write_text(json.dumps(payload,ensure_ascii=False));os.replace(temp,data/'mac_mini.json')
        status={'ok':True,'attempted_at':stamp,'last_success':payload['captured_at']}
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):
        previous={}
        try:previous=json.loads((data/'mac_mini_sync.json').read_text())
        except (OSError,ValueError):pass
        status={'ok':False,'attempted_at':stamp,'last_success':previous.get('last_success'),'error':'Mac miniに接続できません。最後に取得した記録を表示しています。'}
    temp=data/'mac_mini_sync.tmp';temp.write_text(json.dumps(status,ensure_ascii=False));os.replace(temp,data/'mac_mini_sync.json')
    return status
if __name__=='__main__':
    status=sync();print(json.dumps(status,ensure_ascii=False));sys.exit(0 if status['ok'] else 1)
