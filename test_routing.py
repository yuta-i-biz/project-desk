import unittest
from routing import choose
from gemini_adapter import response
class RoutingTests(unittest.TestCase):
 def ready(self,*names):return [{'engine':n,'available':True} for n in names]
 def test_implementation_does_not_fall_to_text_only_gemini(self):
  self.assertEqual(choose('アプリのエラーを修正',self.ready('Codex','Gemini'))[0],'Codex')
  with self.assertRaises(ValueError):choose('コードを修正',self.ready('Gemini'))
 def test_analysis_and_writing_preferences(self):
  all=self.ready('Codex','Claude Code','Gemini')
  self.assertEqual(choose('資料を比較して要約',all)[0],'Gemini')
  self.assertEqual(choose('案内文の下書き',all)[0],'Claude Code')
 def test_unavailable_preference_uses_ready_provider(self):
  name,why=choose('文案の下書き',self.ready('Codex'))
  self.assertEqual(name,'Codex');self.assertIn('未接続',why)
 def test_invalid_and_unavailable_explicit_choice(self):
  with self.assertRaises(ValueError):choose('要約',self.ready('Codex'),'Gemini')
  with self.assertRaises(ValueError):choose('要約',self.ready('Codex'),'不明')
 def test_json_with_startup_notice(self):
  self.assertEqual(response('Loaded cached credentials.\n{"response":"done","stats":{}}'),'done')

class CapabilityRoutingTests(unittest.TestCase):
 def test_image_generation_cannot_fall_to_text_adapter(self):
  ready=[{'engine':n,'available':True} for n in ['Codex','Claude Code','Gemini']]
  self.assertEqual(choose('新しい画像を2案作成して',ready)[0],'Codex')
  with self.assertRaises(ValueError):choose('クーポン画像を修正',ready,'Gemini')
  with self.assertRaises(ValueError):choose('クーポン画像を修正',ready[1:])
 def test_image_attachment_changes_analysis_route(self):
  ready=[{'engine':n,'available':True} for n in ['Claude Code','Gemini']]
  self.assertEqual(choose('比較して',ready,attachments=[{'name':'scan.PNG'}])[0],'Claude Code')
 def test_restricted_claude_cannot_claim_runtime_testing(self):
  with self.assertRaises(ValueError):choose('コードの実装とテスト',[{'engine':'Claude Code','available':True}])
 def test_image_prompt_writing_is_text_work(self):
  from routing import profile
  self.assertFalse(profile('画像生成のプロンプトを作成')['review_required'])

if __name__=='__main__':unittest.main()
