import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from review import run
from routing import profile
class ReviewTests(unittest.TestCase):
 def review(self,visual=True,alter=False):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);(folder/'image.png').write_bytes(b'fixture');(folder/'response.txt').write_text('done')
   def fake(command,**kw):
    if command[1:3]==['login','status']:return subprocess.CompletedProcess(command,0,'Logged in using ChatGPT','')
    self.assertEqual(command[command.index('--sandbox')+1],'read-only')
    output=Path(command[command.index('--output-last-message')+1]);output.write_text(json.dumps({'status':'reviewed','summary':'確認しました','checks':[{'file':'image.png','kind':'visual' if visual else 'content','observation':'主メッセージが特典より大きい'},{'file':'response.txt','kind':'content','observation':'回答内容と成果物が対応'}]}))
    self.assertEqual(command[command.index('--image')+1],str(folder/'image.png'))
    if alter:(folder/'image.png').write_bytes(b'changed')
    return subprocess.CompletedProcess(command,0)
   with patch('review.subprocess.run',side_effect=fake):
    return run(folder,'新しい画像を作成',profile('新しい画像を作成'),[{'engine':'Codex','available':True}],{},[{'name':'image.png'}])
 def test_image_review_requires_image_input_and_per_image_findings(self):
  self.assertEqual(self.review(visual=False)['status'],'unverified')
  r=self.review();self.assertEqual(r['status'],'reviewed');self.assertEqual(r['input_images'][0]['file'],'image.png');self.assertEqual(len(r['input_images'][0]['sha256']),64)
 def test_artifact_change_invalidates_review(self):
  self.assertEqual(self.review(alter=True)['status'],'issues')
 def test_missing_reviewer_and_invalid_prompt_are_not_passes(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);(folder/'generation_prompts.json').write_text('{"B":"undefined Variant B"}')
   job=profile('画像を作成')
   self.assertEqual(run(folder,'画像を作成',job,[],{},[])['status'],'unverified')
   with patch('review.subprocess.run') as process:
    r=run(folder,'画像を作成',job,[{'engine':'Codex','available':True}],{},[{'name':'generation_prompts.json'}])
    self.assertEqual(r['status'],'issues');process.assert_not_called()

class RegisteredReviewTests(unittest.TestCase):
 def test_independent_runtime_review_needs_structured_execution(self):
  for actual_event in (False,True):
   with self.subTest(actual_event=actual_event),tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp);(folder/'main.py').write_text('print(1)');(folder/'response.txt').write_text('tests passed')
    def fake(command,**kw):
     if command[1:3]==['login','status']:return subprocess.CompletedProcess(command,0,'ChatGPT','')
     self.assertEqual(kw['env']['PYTHONDONTWRITEBYTECODE'],'1')
     output=Path(command[command.index('--output-last-message')+1]);output.write_text(json.dumps({'status':'reviewed','summary':'確認済み','checks':[{'file':n,'kind':'code','observation':'内容を点検'} for n in ['main.py','response.txt']]}))
     event={'type':'item.completed','item':{'type':'command_execution','command':'cd workspace && python3 -m unittest discover','exit_code':0,'aggregated_output':'Ran 1 test\nOK'}} if actual_event else {'type':'item.completed','item':{'type':'agent_message','text':'unittest OK'}}
     kw['stdout'].write(json.dumps(event)+'\n');kw['stdout'].flush();return subprocess.CompletedProcess(command,0)
    with patch('review.subprocess.run',side_effect=fake):r=run(folder,'コード修正',{'kind':'implementation','review_required':True,'registered_workspace':True},[{'engine':'Codex','available':True}],{},[{'name':'main.py'}])
    self.assertEqual(r['status'],'reviewed' if actual_event else 'unverified')
    if actual_event:self.assertEqual(r['tests'][0]['runner'],'unittest')
 def test_unverified_explanation_is_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);(folder/'response.txt').write_text('done')
   def fake(command,**kw):
    if command[1:3]==['login','status']:return subprocess.CompletedProcess(command,0,'ChatGPT','')
    Path(command[command.index('--output-last-message')+1]).write_text(json.dumps({'status':'unverified','summary':'実行記録が不足','checks':[]}));return subprocess.CompletedProcess(command,0)
   with patch('review.subprocess.run',side_effect=fake):r=run(folder,'コード修正',{'kind':'implementation','review_required':True},[{'engine':'Codex','available':True}],{},[])
   self.assertEqual(r['summary'],'実行記録が不足');self.assertEqual(r['status'],'unverified')


class BatchReviewTests(unittest.TestCase):
 def test_more_than_sixty_files_are_all_covered(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);names=['f'+str(i)+'.txt' for i in range(70)]
   for name in names+['response.txt']:(folder/name).write_text('fixture')
   calls=[]
   def single(folder,prompt,job,engines,env,files):
    group=[f['name'] for f in files]+['response.txt'];calls.append(group);return {'status':'reviewed','summary':'確認済み','independent':True,'checks':[{'file':n,'kind':'content','observation':'checked'} for n in group]}
   with patch('review._run_single',side_effect=single):r=run(folder,'verify',{'kind':'implementation','review_required':True},[],{},[{'name':n} for n in names])
   self.assertEqual(r['status'],'reviewed');self.assertEqual(len(calls),2);self.assertTrue(all(len(c)<=60 for c in calls));self.assertFalse(r['unreviewed_files'])
 def test_partial_batch_is_never_a_pass(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);files=[{'name':'f'+str(i)} for i in range(61)]
   for f in files:(folder/f['name']).write_text('fixture')
   with patch('review._run_single',return_value={'status':'unverified','summary':'not checked','independent':False,'checks':[]}):r=run(folder,'verify',{'kind':'implementation','review_required':True},[],{},files)
   self.assertEqual(r['status'],'unverified');self.assertEqual(len(r['unreviewed_files']),61)
