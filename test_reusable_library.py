import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from app import Desk
from project_context import bundle,instruction
from reusable_library import capture,catalog,materialize

class ReferenceAccessTests(unittest.TestCase):
 def test_no_document_count_or_total_text_is_dropped_and_tail_is_readable(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);home=root/'home';ledger=home/'.claude/runtime/ledger';ledger.mkdir(parents=True);folder=root/'request';folder.mkdir();desk=type('Desk',(),{'home':home,'machine':'このMac'})()
   sources=[]
   for i in range(12):
    p=ledger/(str(i)+'.md');p.write_text('あ'*20000+'TAIL'+str(i));sources.append({'type':'ledger','machine':'このMac','path':str(p)})
   result=bundle(desk,{'sources':sources},folder);self.assertEqual(len(result['documents']),12);self.assertFalse(any('上限' in d['reason'] for d in result['unavailable']))
   text=instruction(result,folder,full_text=True);self.assertIn('TAIL11',text);self.assertIn('TAIL0',text)
   spec=importlib.util.spec_from_file_location('reader',Path(__file__).parent/'reusable/project-reference-reader/scripts/read_reference.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   doc=result['documents'][0];alltext='';offset=0
   while True:
    page=module.read(folder,doc['id'],offset=offset,length=11000);alltext+=page['content'];offset=page['next_offset']
    if page['done']:break
   self.assertTrue(alltext.endswith('TAIL0'));self.assertEqual(len(module.read(folder,doc['id'],query='TAIL')['content']),1)
 def test_full_snapshot_is_redacted_and_tampering_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);home=root/'home';p=home/'.claude/CLAUDE.md';p.parent.mkdir(parents=True);p.write_text('password: hidden\n'+'x'*17000+'END');folder=root/'r';folder.mkdir();desk=type('Desk',(),{'home':home})()
   result=bundle(desk,{},folder);self.assertNotIn('hidden',instruction(result,folder,True));(folder/result['documents'][0]['full_path']).write_text('forged')
   with self.assertRaises(ValueError):instruction(result,folder,True)

class LibraryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.desk=Desk(self.root/'home',self.root/'data');self.pid=self.desk.mutate('project',{'name':'One','company':'Test'})['id'];self.other=self.desk.mutate('project',{'name':'Two','company':'Test'})['id']
 def package(self,kind='skill'):
  task=self.desk.mutate('create',{'project_id':self.pid,'title':'reuse test','next_action':'test'});tid=task['id'];folder=self.desk.data/'requests'/tid;package=folder/'workspace/reusable/sample';package.mkdir(parents=True)
  value={'name':'sample','kind':kind,'description':'fixture transformation','tags':['transform'],'files':['SKILL.md']};(package/'manifest.json').write_text(json.dumps(value));(package/'SKILL.md').write_text('---\nname: sample\ndescription: Transform fixture inputs.\n---\nRead the input and validate the output.')
  if kind!='skill':
   value['files'].append('transform.py');(package/'transform.py').write_text('def transform(value): return value.strip()\n');(package/'manifest.json').write_text(json.dumps(value))
  hashes={str(p.relative_to(folder/'workspace')):hashlib.sha256(p.read_bytes()).hexdigest() for p in package.iterdir()}
  receipt={'execution_status':'succeeded','review':{'status':'reviewed','independent':True,'checks':[{'file':str(p.relative_to(folder))} for p in package.iterdir()],'test_evidence':{'status':'passed','manifest':hashes}}};return tid,folder,package,receipt
 def test_verified_skill_is_versioned_project_scoped_and_reused_without_ai(self):
  tid,folder,package,receipt=self.package();capture(self.desk,self.pid,tid,receipt);capture(self.desk,self.pid,tid,receipt)
  self.assertEqual(len(catalog(self.desk,self.pid)),1);self.assertEqual(catalog(self.desk,self.other),[])
  dest=self.root/'next';dest.mkdir();assets=materialize(self.desk,self.pid,dest,'transform this');asset=next(a for a in assets if a['name']=='sample');self.assertTrue((dest/asset['path']/'SKILL.md').is_file());self.assertEqual(catalog(self.desk,self.pid)[0]['offered'],1)
  second=self.root/'other';second.mkdir();self.assertNotIn('sample',[a['name'] for a in materialize(self.desk,self.other,second,'transform')])
 def test_unreviewed_and_changed_programs_are_candidates_not_activated(self):
  for verified in (False,True):
   tid,folder,package,receipt=self.package('program')
   if not verified:receipt['review']['status']='unverified'
   else:(package/'SKILL.md').write_text('changed after test')
   capture(self.desk,self.pid,tid,receipt)
  self.assertTrue(all(a['state']=='candidate' for a in catalog(self.desk,self.pid)))
 def test_wrong_project_and_symlink_cannot_be_saved(self):
  tid,folder,package,receipt=self.package();self.assertEqual(capture(self.desk,self.other,tid,receipt),[])
  (package/'SKILL.md').unlink();(package/'SKILL.md').symlink_to('/etc/passwd');self.assertEqual(capture(self.desk,self.pid,tid,receipt),[])

 def test_verified_program_is_usable_and_changed_saved_copy_is_not(self):
  tid,folder,package,receipt=self.package('program');capture(self.desk,self.pid,tid,receipt)
  self.assertEqual(catalog(self.desk,self.pid)[0]['state'],'ready')
  import reusable_library
  with self.desk.connect() as c:record=dict(c.execute('SELECT * FROM reusable_assets').fetchone())
  (Path(record['folder'])/'SKILL.md').write_text('altered stored asset')
  dest=self.root/'tampered';dest.mkdir();self.assertNotIn('sample',[a['name'] for a in materialize(self.desk,self.pid,dest,'transform')])
 def test_candidate_upgrades_only_after_validated_receipt(self):
  tid,folder,package,receipt=self.package();receipt['review']['status']='unverified';capture(self.desk,self.pid,tid,receipt)
  self.assertEqual(catalog(self.desk,self.pid)[0]['state'],'candidate')
  receipt['review']['status']='reviewed';capture(self.desk,self.pid,tid,receipt)
  self.assertEqual(catalog(self.desk,self.pid)[0]['state'],'ready');self.assertEqual(len(catalog(self.desk,self.pid)),1)
