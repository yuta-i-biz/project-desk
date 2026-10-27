import json,subprocess,tempfile,unittest,hashlib
from pathlib import Path
from remote_export import export
from peer_receiver import receive,fingerprint
from macbook_sync import sync

class PeerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.home=self.root/'home';ledger=self.home/'.claude/runtime/ledger/Test';ledger.mkdir(parents=True);self.note=ledger/'【Test：Case】.md';self.note.write_text('## 現在地\noriginal\npassword: hidden\n'+('long text\n'*3000));sessions=self.home/'.claude/projects/work';sessions.mkdir(parents=True);(sessions/'abc.jsonl').write_text(json.dumps({'type':'user','cwd':'/work/case','message':{'content':'DO NOT EXPOSE THIS MESSAGE'}})+'\n');self.data=self.root/'mini';self.data.mkdir();(self.data/'desk.sqlite3').touch()
 def envelope(self):
  snap=export(self.home,'MacBook',True);return {'machine':'MacBook','captured_at':snap['captured_at'],'snapshot':snap,'fingerprint':fingerprint(snap)}
 def test_full_reference_and_untitled_session_are_kept_without_message_bodies(self):
  envelope=self.envelope();snapshot=envelope['snapshot'];self.assertEqual(len(snapshot['sources']),1);self.assertEqual(snapshot['coverage']['untitled_included'],1);self.assertNotIn('DO NOT EXPOSE',json.dumps(snapshot));self.assertNotIn('hidden',json.dumps(snapshot))
  result=receive(self.data,envelope);self.assertTrue(result['ok']);stored=json.loads((self.data/'peer_snapshot.json').read_text());ref=stored['sources'][0]['peer_document'];self.assertTrue((self.data/'peer_documents'/(ref['sha256']+'.md')).read_text().endswith('long text\n'));self.assertIn('password: hidden',self.note.read_text())
 def test_unchanged_heartbeat_requires_matching_snapshot_and_repairs_missing_copy(self):
  envelope=self.envelope();digest=envelope['fingerprint'];receive(self.data,envelope);heartbeat={'machine':'MacBook','captured_at':envelope['captured_at'],'snapshot':None,'fingerprint':digest};self.assertTrue(receive(self.data,heartbeat)['ok'])
  for p in (self.data/'peer_documents').glob('*.md'):p.unlink()
  self.assertTrue(receive(self.data,heartbeat)['needs_full'])
 def test_invalid_data_preserves_previous_and_codex_metadata_is_not_dropped(self):
  old={'sources':[],'sessions':[{'id':'codex:one','type':'Codex'}]};(self.data/'peer_snapshot.json').write_text(json.dumps(old));envelope=self.envelope();envelope['snapshot']['documents'][0]['text']='forged'
  with self.assertRaises(ValueError):receive(self.data,envelope)
  self.assertEqual(json.loads((self.data/'peer_snapshot.json').read_text()),old)
  receive(self.data,self.envelope());self.assertTrue(any(s['id']=='codex:one' for s in json.loads((self.data/'peer_snapshot.json').read_text())['sessions']))
 def test_sender_is_noninteractive_and_reuses_last_snapshot_on_failure(self):
  packets=[]
  def runner(command,**kw):
   self.assertIn('BatchMode=yes',command);self.assertIn('StrictHostKeyChecking=yes',command);packets.append(json.loads(kw['input']));return subprocess.CompletedProcess(command,0,json.dumps(receive(self.data,json.loads(kw['input']))),'')
  state=self.root/'state';first=sync(state,self.home,runner);second=sync(state,self.home,runner);self.assertTrue(first['ok']);self.assertTrue(second['ok']);self.assertIsNone(packets[-1]['snapshot'])
  failure=sync(state,self.home,lambda *a,**kw:subprocess.CompletedProcess(a,1,'',''));self.assertFalse(failure['ok']);self.assertEqual(failure['last_success'],second['last_success']);self.assertTrue((self.data/'peer_snapshot.json').exists())
 def test_symlinks_and_unreadable_sources_cannot_be_published_as_complete(self):
  self.note.unlink();self.note.symlink_to('/etc/passwd');r=sync(self.root/'state',self.home,lambda *a,**kw:self.fail('must not connect with partial source'));self.assertFalse(r['ok'])

class StateTests(unittest.TestCase):
 setUp=PeerTests.setUp
 envelope=PeerTests.envelope
 def test_freshness_never_calls_old_or_future_records_current(self):
  from peer_state import freshness
  import datetime as dt
  now=dt.datetime(2026,10,27,8,tzinfo=dt.timezone.utc)
  self.assertFalse(freshness({'ok':True},'2026-10-26T00:00:00+00:00',now)['fresh']);self.assertFalse(freshness({'ok':True},'2026-10-28T00:00:00+00:00',now)['fresh']);self.assertTrue(freshness({'ok':True},'2026-10-27T07:59:00+00:00',now)['fresh'])
 def test_different_machine_records_are_kept_separately(self):
  from peer_state import differences
  rows=[{'id':'a','type':'案件台帳','machine':'MacBook','sections':{'現在地':'draft'}},{'id':'b','type':'案件台帳','machine':'Mac mini','sections':{'現在地':'review'}}]
  result=differences(rows);self.assertEqual(len(result),1);self.assertEqual(len(result[0]['records']),2);self.assertEqual(rows[0]['sections']['現在地'],'draft')
 def test_only_verified_selected_remote_reference_is_available(self):
  from project_context import bundle
  from types import SimpleNamespace
  receive(self.data,self.envelope());snapshot=json.loads((self.data/'peer_snapshot.json').read_text());request=self.root/'request';request.mkdir();desk=SimpleNamespace(home=self.root/'mini-home',data=self.data,machine='Mac mini')
  result=bundle(desk,{'sources':snapshot['sources']},request);doc=next(d for d in result['documents'] if d['kind']=='project_ledger');self.assertEqual(doc['origin']['machine'],'MacBook');self.assertTrue((request/doc['full_path']).read_text().endswith('long text\n'))
  ref=snapshot['sources'][0]['peer_document'];(self.data/'peer_documents'/(ref['sha256']+'.md')).write_text('forged');self.assertFalse(bundle(desk,{'sources':snapshot['sources']},request)['documents'])


class CacheTests(unittest.TestCase):
 setUp=PeerTests.setUp
 envelope=PeerTests.envelope
 def test_unchanged_session_files_are_not_read_again(self):
  from remote_export import scan_sessions
  from unittest.mock import patch
  target=self.home/'.claude/projects/work/abc.jsonl';cache={};opened=[];real=Path.open
  def open_file(path,*args,**kw):
   if path==target:opened.append(path)
   return real(path,*args,**kw)
  with patch.object(Path,'open',open_file):
   first=scan_sessions(self.home,'MacBook',cache);second=scan_sessions(self.home,'MacBook',cache)
  self.assertEqual(first,second);self.assertEqual(len(opened),1)
 def test_older_snapshot_cannot_replace_newer_records(self):
  envelope=self.envelope();receive(self.data,envelope);before=(self.data/'peer_snapshot.json').read_bytes();envelope['captured_at']='2020-01-01T00:00:00+00:00'
  with self.assertRaises(ValueError):receive(self.data,envelope)
  self.assertEqual((self.data/'peer_snapshot.json').read_bytes(),before)


class SecretTests(unittest.TestCase):
 setUp=PeerTests.setUp
 envelope=PeerTests.envelope
 def test_private_keys_are_absent_from_both_previews_and_full_copies(self):
  self.note.write_text('## 現在地\n-----BEGIN PRIVATE KEY-----\nFAKE_PRIVATE_BODY\n-----END PRIVATE KEY-----\nnormal work\n')
  packet=self.envelope();self.assertNotIn('FAKE_PRIVATE_BODY',json.dumps(packet));self.assertIn('normal work',json.dumps(packet))
