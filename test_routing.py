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
if __name__=='__main__':unittest.main()
