"""Gemini through Google's supported Antigravity CLI; supplied context only."""
import json
from pathlib import Path

def binary(root):return root/'vendor/bin/agy'

def command(root,folder):
    try:model=json.loads((root/'data/gemini_probe.json').read_text()).get('model','')
    except (OSError,ValueError):model=''
    if not isinstance(model,str) or not model.startswith('gemini-'):raise RuntimeError('Geminiの契約ログインと利用可能なモデルの確認が必要です。')
    return [str(binary(root)),'--input-format','stream-json','--output-format','stream-json','--mode','plan','--sandbox','--disable-slash-commands','--model',model,'--print-timeout','15m']

def response(text):
    decoder=json.JSONDecoder();answer=''
    for line in text.splitlines():
        try:a=json.loads(line)
        except ValueError:continue
        if isinstance(a,dict) and a.get('event')=='result' and isinstance(a.get('result'),dict):
            result=a['result']
            if result.get('status')=='SUCCESS':answer=result.get('response','')
            else:raise RuntimeError('Geminiの処理が完了していません。接続・利用枠・権限を確認してください。')
    if answer:return answer
    for i,c in enumerate(text):
        if c!='{':continue
        try:a,_=decoder.raw_decode(text[i:])
        except ValueError:continue
        if isinstance(a,dict) and isinstance(a.get('response'),str):return a['response']
    return ''
