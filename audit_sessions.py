"""Read only bounded tails; flag failure evidence, never assert a live defect."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re

JST=dt.timezone(dt.timedelta(hours=9))
REMEDIES={
 '認証・操作権限':('同じ認証・端末で読取専用の確認を1回実行する。','期限切れなら再認証、未許可なら対象アプリの必要な権限だけを付与し、同じ確認を再実行する。'),
 '接続・時間切れ':('接続先の稼働・ネットワーク・処理時間を個別に確認する。','接続を復旧し、読み取り範囲や処理量を分割する。無条件の再実行や本番反映はしない。'),
 '利用枠・制限':('現在の利用枠と解除時刻を、サービス側で確認する。','処理を小さくするか枠の回復後に再開する。課金や契約変更は自動で行わない。'),
 'コード・実行環境':('元の失敗した操作を開発環境で再現し、エラー位置と依存関係を確認する。','原因を限定して修正し、変更前後の同じテストを実行する。運用中の原本は直接変更しない。'),
 'ファイル・参照先':('パス・端末・対象IDが現在も存在するか確認する。','正しい端末の参照先に修正する。見つからない資料やデータを推測で作らない。'),
 'ツール実行の失敗':('元の会話にある失敗操作と、その後の検証結果を確認する。','仮説と判別テストを用意し、失敗が今も再現する場合だけ対処する。')}

def category(text):
    text=text.lower()
    checks=[('利用枠・制限',r'429|rate.?limit|quota|usage.limit|limit.reached'),('認証・操作権限',r'401|403|permission|not permitted|denied|unauthori|authentic|認証|権限'),('接続・時間切れ',r'timeout|timed out|econn|connection refused|network|dns'),('コード・実行環境',r'syntaxerror|typeerror|referenceerror|compile|build failed|modulenotfound|importerror'),('ファイル・参照先',r'no such file|not found|enoent')]
    return next((label for label,pattern in checks if re.search(pattern,text)),'ツール実行の失敗')

def scan_sessions(home,machine='このMac'):
    home=Path(home);titles={}
    try:titles=json.loads((home/'.claude/runtime/session_titles_cache.json').read_text())
    except (OSError,ValueError):pass
    if not isinstance(titles,dict):titles={}
    paths=[('Claude Code',p) for p in (home/'.claude/projects').glob('*/*.jsonl')]
    paths += [('Codex',p) for folder in ['sessions','archived_sessions'] for p in (home/'.codex'/folder).rglob('*.jsonl')]
    rows=[];unreadable=0;empty_windows=0;malformed=0
    for provider,p in paths:
        try:
            stat=p.stat()
            with p.open('rb') as stream:
                offset=max(0,stat.st_size-32768);stream.seek(offset);blob=stream.read(32768).decode('utf-8',errors='replace')
            lines=blob.splitlines()
            if offset and lines:lines=lines[1:]
            old=titles.get(str(p),{});title=old.get('title','') if isinstance(old,dict) else ''
            errors=[];successes=[];records=0
            for index,line in enumerate(lines):
                try:record=json.loads(line)
                except ValueError:malformed+=1;continue
                if not isinstance(record,dict):continue
                records+=1
                if record.get('customTitle'):title=record['customTitle']
                message=record.get('message',{})
                content=message.get('content',[]) if isinstance(message,dict) else []
                for block in content if isinstance(content,list) else []:
                    if not isinstance(block,dict) or block.get('type')!='tool_result':continue
                    if block.get('is_error') is True:
                        errors.append((index,record.get('timestamp'),category(str(block.get('content','')))))
                    else:successes.append(index)
                payload=record.get('payload',{})
                if isinstance(payload,dict) and payload.get('type')=='function_call_output':
                    output=str(payload.get('output',''))
                    if re.search(r'(?:Process exited with code|exit_code["\s]*:|Exit code:)\s*[1-9]\d*|"isError"\s*:\s*true',output,re.I):
                        errors.append((index,record.get('timestamp'),category(output)))
                    elif re.search(r'(?:Process exited with code|exit_code["\s]*:|Exit code:)\s*0\b',output,re.I):successes.append(index)
                if record.get('type') in ('error','api_error'):
                    errors.append((index,record.get('timestamp'),category(str(record.get('error','')))))
            if not records:empty_windows+=1
            match=re.match(r'^【([^：:】]+)[：:]([^】]+)】',str(title))
            company=match[1].replace('モノ_ループ','モノ・ループ') if match else '未分類';project=match[2] if match else ''
            ids=re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',p.stem,re.I)
            sid=('claude:' if provider=='Claude Code' else 'codex:')+(ids[-1] if ids else p.stem)
            if machine=='Mac mini':sid='macmini:'+sid
            last=errors[-1] if errors else None
            after=bool(last and any(i>last[0] for i in successes))
            label=last[2] if last else None
            test,solution=REMEDIES[label] if label else ('','')
            rows.append({'session_id':sid,'provider':provider,'machine':machine,'title':title or '名称未設定の会話 '+p.stem[-8:],
                'company':company,'project_name':project,'updated':dt.datetime.fromtimestamp(stat.st_mtime,JST).isoformat(timespec='seconds'),
                'path':str(p),'tail_bytes':min(stat.st_size,32768),'complete_records':records,'error_count':len(errors),
                'last_error_at':last[1] if last else None,'category':label,'later_success_response':after,
                'assessment':'失敗履歴あり・現在の再現は未検証' if last else '確認した末尾に失敗応答なし' if records else '末尾に完全な記録がなく判定できない',
                'test':test,'solution':solution,'internal':bool(old.get('internal')) if isinstance(old,dict) else False})
        except OSError:unreadable+=1
    return {'captured_at':dt.datetime.now(JST).isoformat(timespec='seconds'),'machine':machine,'sessions_found':len(paths),
        'sessions_read':len(rows),'unreadable':unreadable,'empty_windows':empty_windows,'malformed_records':malformed,
        'sessions_with_failure_history':sum(bool(r['error_count']) for r in rows),'rows':rows,
        'scope':'主会話のJSONL（Claude CodeとCodex、Codexの保管済みを含む）の末尾32KBのみ。子エージェント記録・クラウド専用会話・稼働中アプリの動作試験は対象外。エラー履歴は現在の不具合の証明ではない。'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);parser.add_argument('--home',type=Path,default=Path.home());args=parser.parse_args()
    result=scan_sessions(args.home)
    if args.output:args.output.write_text(json.dumps(result,ensure_ascii=False))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
