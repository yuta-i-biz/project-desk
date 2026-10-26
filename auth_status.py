"""Check CLI login without retaining identity or credential values."""
import json
import subprocess
import time
from pathlib import Path
from execution import environment

def claude_probe(home,env=None):
    env=environment(home) if env is None else env
    result={'engine':'Claude Code','available':False,'state':'not_verified','detail':'Claudeのログイン状態をアプリから確認できません。Mac mini側の認証アクセスを確認してください。'}
    try:
        r=subprocess.run([str(home/'.local/bin/claude'),'auth','status','--json'],env=env,capture_output=True,text=True,timeout=15)
        auth=json.loads(r.stdout)
        if not isinstance(auth,dict):return result
        if r.returncode==0 and auth.get('loggedIn') and auth.get('authMethod') in ('claude.ai','claudeai','oauth'):
            return {'engine':'Claude Code','available':True,'state':'connected','detail':'Claude契約のログインを確認済み'}
    except subprocess.TimeoutExpired:
        result.update(state='auth_timeout',detail='Claudeの認証確認が時間切れです。ログアウトと決めつけず、Mac miniの画面側でアクセス確認が出ていないか確認してください。')
    except (OSError,ValueError):return result
    keychain=home/'Library/Keychains/login.keychain-db'
    if keychain.exists():
        try:
            check=subprocess.run(['/usr/bin/security','show-keychain-info',str(keychain)],capture_output=True,text=True,timeout=5)
            if check.returncode and 'User interaction is not allowed' in check.stdout+check.stderr:
                result.update(state='credential_unavailable',detail='アプリの起動経路からキーチェーンを確認できず、ログイン状態は未確認です。再ログインの前にMac mini側の認証アクセスを確認してください。')
        except (OSError,subprocess.TimeoutExpired):pass
    return result

def refresh(data,home):
    env=environment(home);items=[]
    for name,command in [('Codex',['/opt/homebrew/bin/codex','login','status'])]:
        available=False
        try:
            r=subprocess.run(command,env=env,capture_output=True,text=True,timeout=15)
            available=r.returncode==0 and 'ChatGPT' in r.stdout+r.stderr
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
        items.append({'engine':name,'available':bool(available),'detail':'契約ログイン確認済み' if available else 'ログインまたはキーチェーンの解除を確認してください'})
    from claude_bridge import status as bridge_status
    items.append(bridge_status(data) or claude_probe(home,env))
    try:
        probe=json.loads((data/'gemini_probe.json').read_text())
        from gemini_adapter import binary
        available=bool(binary(data.parent).exists() and probe.get('ok') and 0<=time.time()-probe.get('checked_at',0)<86400)
    except (OSError,ValueError,TypeError):available=False
    items.append({'engine':'Gemini','available':available,'detail':'Googleログインで応答確認済み' if available else 'Google側で旧方式が非対応。後継Antigravityで一度ログインしてください'})
    (data/'engines.json').write_text(json.dumps(items,ensure_ascii=False))
    return items
