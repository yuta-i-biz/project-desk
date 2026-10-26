import unittest,tempfile,json
from pathlib import Path
from app import Desk
class MLManualProjectTests(unittest.TestCase):
 def test_new_ml_project_visible_with_canonical_gantt(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);d=Desk(root/'home',root/'data');pid=d.mutate('project',{'company':'モノ・ループ','name':'新規の専用案件'})['id']
   (d.data/'ml_gantt.json').write_text(json.dumps({'captured_at':'2026-10-26T00:00:00+09:00','projects':[{'id':1,'name':'正本の案件','tab_name':'正本の案件','tasks':[],'deadline':'','url':'https://docs.example.test/sheet'}]}))
   p=next(p for p in d.collect(force=True)['projects'] if p['id']==pid)
   self.assertFalse(p.get('reference_only',False))
