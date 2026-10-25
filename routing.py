"""Deterministic, inspectable routing; no secondary paid classification call."""
import re
ENGINES=('Codex','Claude Code','Gemini')
def choose(prompt,engines,requested='おまかせ'):
    ready={e['engine'] for e in engines if e.get('available') and e.get('engine') in ENGINES}
    if requested!='おまかせ':
        if requested not in ENGINES:raise ValueError('使用するAIを確認してください。')
        if requested not in ready:raise ValueError(requested+'はログイン・接続確認が必要です。')
        return requested,'指定されたAIを使用'
    if re.search(r'実装|修正|不具合|エラー|コード|プログラム|アプリ|自動化|テスト|SQL|GAS|python|javascript',prompt,re.I):
        order=['Codex','Claude Code'];reason='実装・修正の依頼として振り分け'
    elif re.search(r'要約|比較|読み比べ|整理|分析|調査|集計',prompt) or len(prompt)>3000:
        order=['Gemini','Claude Code','Codex'];reason='要約・比較・分析の依頼として振り分け'
    elif re.search(r'文章|下書き|文案|マニュアル|企画|説明文|メール',prompt):
        order=['Claude Code','Codex','Gemini'];reason='文章・下書きの依頼として振り分け'
    else:order=['Codex','Claude Code','Gemini'];reason='一般の作業依頼として振り分け'
    for i,name in enumerate(order):
        if name in ready:return name,reason+('（優先候補が未接続のため利用可能なAIを選択）' if i else '')
    raise ValueError('この依頼を実行できるAIが未接続です。ログイン・接続状態を確認してください。')
