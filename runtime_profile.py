"""Describe inherited resources and effective restrictions without exporting secrets."""
def describe(home,engine):
 import json
 from routing import CAPABILITIES
 base=home/'.claude'
 resources={}
 for name,path in [('rules',base/'CLAUDE.md'),('criteria',base/'runtime/auto_run_criteria.md'),('memory',base/'projects'/('-'+str(home).strip('/').replace('/','-'))/'memory/MEMORY.md')]:
  if path.is_file():resources[name]=str(path)
 def config(path):
  try:
   if path.stat().st_size>2*1024*1024:return {}
   data=json.loads(path.read_text());return data if isinstance(data,dict) else {}
  except (OSError,ValueError):return {}
 settings=config(base/'settings.json');user=config(home/'.claude.json')
 inherited={'status':'設定名の確認のみ。実接続・実行は未検証。',
  'mcp_servers':sorted((user.get('mcpServers') or {}).keys()),
  'hooks':sorted((settings.get('hooks') or {}).keys()),
  'plugins':sorted(k for k,v in (settings.get('enabledPlugins') or {}).items() if v)}
 return {'engine':engine,'scope':'専用フォルダ内で成果物を作成。既存の業務ファイルは読取りのみ。',
  'capabilities':sorted(CAPABILITIES[engine]),'resources':resources,'configured_claude_environment':inherited,
  'agents':sorted(p.stem for p in (base/'agents').glob('*.md')),
  'skills':sorted(p.parent.name for p in (base/'skills').glob('*/SKILL.md')),
  'parity':'limited','limitations':['既存作業フォルダでの実装・MCP連携の同等性は未検証','Claude Codeのシェルによる検証は現在の接続方式では利用不可','既存hooksは全AIの操作を強制制御するものではない']}
