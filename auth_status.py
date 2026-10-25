"""Check CLI login without retaining identity or credential values."""
import json
import subprocess
import time
from pathlib import Path
from execution import environment

def refresh(data,home):
    env=environment(home);items=[]
    for name,command in [('Codex',['/opt/homebrew/bin/codex','login','status']),('Claude Code',[str(home/'.local/bin/claude'),'auth','status','--json'])]:
        available=False
        try:
            r=subprocess.run(command,env=env,capture_output=True,text=True,timeout=15)
            if name=='Codex':available=r.returncode==0 and 'ChatGPT' in r.stdout+r.stderr
            else:
                a=json.loads(r.stdout);available=r.returncode==0 and a.get('loggedIn',False) and a.get('authMethod') in ('claude.ai','claudeai','oauth')
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
        items.append({'engine':name,'available':bool(available),'detail':'契約ログイン確認済み' if available else 'ログインまたはキーチェーンの解除を確認してください'})
    try:
        probe=json.loads((data/'gemini_probe.json').read_text())
        from gemini_adapter import binary
        available=bool(binary(data.parent).exists() and probe.get('ok') and 0<=time.time()-probe.get('checked_at',0)<86400)
    except (OSError,ValueError,TypeError):available=False
    items.append({'engine':'Gemini','available':available,'detail':'Googleログインで応答確認済み' if available else 'Google側で旧方式が非対応。後継Antigravityで一度ログインしてください'})
    (data/'engines.json').write_text(json.dumps(items,ensure_ascii=False))
    return items
