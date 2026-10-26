"""Route against the tools actually exposed by each adapter, not brand names alone."""
import re
from pathlib import Path
ENGINES=('Codex','Claude Code','Gemini')
# The Gemini adapter accepts text only. Restricted Claude tools can read images,
# but expose neither image generation nor a command runner for testing code.
CAPABILITIES={
 'Codex':{'text','files','vision','image_generation','code','tests'},
 'Claude Code':{'text','files','vision','code'},
 'Gemini':{'text'},
}
IMAGE_SUFFIXES={'.png','.jpg','.jpeg','.webp','.heic','.tiff','.bmp','.gif'}
def profile(prompt,attachments=()):
 images=any(Path(a.get('name','')).suffix.lower() in IMAGE_SUFFIXES for a in attachments)
 visual=bool(re.search(r'画像|写真|バナー|チラシ|イラスト|ロゴ|ポスター|クーポン',prompt))
 generate=visual and bool(re.search(r'生成|作成|作って|作る|描|デザイン|修正|直して|変更',prompt))
 if re.search(r'プロンプト|仕様書|文章だけ|文案だけ|画像を作らず',prompt):generate=False
 code=bool(re.search(r'実装|不具合|エラー|コード|プログラム|アプリ|自動化|テスト|SQL|GAS|python|javascript',prompt,re.I))
 if generate:return {'kind':'image_generation','requires':{'image_generation','vision'},'review_required':True}
 if images or (visual and re.search(r'確認|見直|検品|比較|レビュー|見て|読み取|分析',prompt)):
  return {'kind':'image_review','requires':{'vision'},'review_required':True}
 if code:return {'kind':'implementation','requires':{'code','tests'},'review_required':True}
 if re.search(r'修正',prompt):return {'kind':'editing','requires':{'files'},'review_required':False}
 if re.search(r'要約|比較|読み比べ|整理|分析|調査|集計',prompt) or len(prompt)>3000:
  return {'kind':'analysis','requires':{'text'},'review_required':False}
 if re.search(r'文章|下書き|文案|マニュアル|企画|説明文|メール',prompt):
  return {'kind':'writing','requires':{'text'},'review_required':False}
 return {'kind':'general','requires':{'text'},'review_required':False}
def choose(prompt,engines,requested='おまかせ',attachments=()):
 job=profile(prompt,attachments)
 ready={e['engine'] for e in engines if e.get('available') and e.get('engine') in ENGINES}
 eligible={n for n in ready if job['requires'] <= CAPABILITIES[n]}
 if requested!='おまかせ':
  if requested not in ENGINES:raise ValueError('使用するAIを確認してください。')
  if requested not in ready:raise ValueError(requested+'はログイン・接続確認が必要です。')
  if requested not in eligible:raise ValueError(requested+'の現在の接続方式では、この依頼に必要な画像操作・ファイル操作・検証を実行できません。おまかせで選択してください。')
  return requested,'指定されたAIを使用（必要な操作に対応）'
 orders={
  'image_generation':(['Codex'],'画像生成と実画像の確認が必要な依頼'),
  'image_review':(['Codex','Claude Code'],'画像の実物を読み取る必要がある依頼'),
  'implementation':(['Codex','Claude Code'],'実装と実行による検証が必要な依頼'),
  'editing':(['Codex','Claude Code'],'ファイルを編集する依頼'),
  'analysis':(['Gemini','Claude Code','Codex'],'要約・比較・分析の依頼'),
  'writing':(['Claude Code','Codex','Gemini'],'文章・下書きの依頼'),
  'general':(['Codex','Claude Code','Gemini'],'一般の作業依頼'),
 }
 order,reason=orders[job['kind']]
 for i,name in enumerate(order):
  if name in eligible:return name,reason+'として振り分け'+('（優先候補が未接続または必要な操作に未対応）' if i else '')
 raise ValueError('この依頼に必要な操作へ対応したAIが未接続です。ログイン・接続状態を確認してください。')
