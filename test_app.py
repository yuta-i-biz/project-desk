import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

spec=importlib.util.spec_from_file_location('desk',Path(__file__).with_name('app.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

class DeskTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name);self.home=self.root/'home'
        self.runtime=self.home/'.claude/runtime';self.runtime.mkdir(parents=True)
        ledger=self.runtime/'ledger/会社A';ledger.mkdir(parents=True)
        self.note=ledger/'【会社A：案件甲】.md'
        self.note.write_text('## 目的\n目的です\n## 現在地\n未検証\n## 次アクション\n確認をする\n## 未解決\n承認を待つ\n')
        (self.runtime/'project_state.json').write_text(json.dumps({'_updated':'2020-01-01','会社A':{'case-a':{'name':'案件甲','status':'進行中','next_action':'古い手順'}}}))
        (self.runtime/'gantt_cache.json').write_text(json.dumps({'updated':'2020-01-01','tasks':[{'id':1,'name':'既存タスク','st':'進行中','cat':'分類'}]}))
        (self.runtime/'meeting_ledger_cache.json').write_text(json.dumps({'updated':'2020-01-01','items':[]}))
        self.session=self.home/'.claude/projects/root/abc.jsonl';self.session.parent.mkdir(parents=True)
        self.session.write_text(json.dumps({'customTitle':'【会社A：案件甲】'})+'\n')
        self.desk=a.Desk(self.home,self.root/'data')
        self.pid=self.desk.snapshot()['projects'][0]['id']
    def tearDown(self):self.temp.cleanup()
    def test_cache_invalidation_near_monotonic_origin(self):
        from unittest.mock import patch
        with patch.object(a.time,'monotonic',return_value=1):
            self.desk.collect(force=True)
            created=self.desk.mutate('project',{'name':'新規案件','company':'会社B'})
            self.assertIn(created['id'],self.desk.project_ids())
    def create(self):return self.desk.mutate('create',{'project_id':self.pid,'title':'確認する仕事','next_action':'内容を検証'})
    def test_exact_match_and_source_preservation(self):
        before=hashlib.sha256(self.note.read_bytes()).hexdigest()
        s=self.desk.snapshot();self.assertEqual(len(s['projects']),1)
        p=s['projects'][0];self.assertEqual(len(p['sources']),2)
        self.assertEqual(len(p['sessions']),1);self.assertEqual(s['tasks'],[])
        self.assertIn('未確認',p['sessions'][0]['observed_status'])
        self.assertEqual(hashlib.sha256(self.note.read_bytes()).hexdigest(),before)
    def test_gantt_tabs_do_not_merge_when_header_is_copied(self):
        sheets=[]
        for i,title in enumerate(['承認待ち','備品']):
            sheets.append({'id':i+1,'name':'承認待ち','tab_name':title,'deadline':'2026/10/31','url':'https://example.com/'+str(i),'tasks':[{'source_id':'P1','row':5,'title':'別の作業'+str(i),'status':'未着手','detail':'','deadline':'2026/10/31'}]})
        (self.desk.data/'ml_gantt.json').write_text(json.dumps({'captured_at':'2026-10-26','projects':sheets}))
        data=self.desk.collect(force=True)
        canonical=[p for p in data['projects'] if p.get('canonical_gantt')]
        self.assertEqual({p['name'] for p in canonical},{'承認待ち','備品'})
        self.assertEqual(len({t['project_id'] for t in data['sheet_tasks']}),2)
    def test_schedule_validation_and_dependency_cycles(self):
        first=self.desk.mutate('create',{'project_id':self.pid,'title':'先の作業','due_date':'2026-10-30','start_date':'2026-10-26','effort_days':'2'})
        second=self.desk.mutate('create',{'project_id':self.pid,'title':'後の作業','depends_on':first['id']})
        with self.assertRaises(ValueError):self.desk.mutate('update',{'id':first['id'],'version':1,'status':'未着手','depends_on':second['id']})
        with self.assertRaises(ValueError):self.desk.mutate('create',{'project_id':self.pid,'title':'不正日','due_date':'2026-02-30'})
        with self.assertRaises(ValueError):self.desk.mutate('create',{'project_id':self.pid,'title':'逆転日','due_date':'2026-10-26','start_date':'2026-10-30'})
        self.desk.mutate('update',{'id':first['id'],'version':1,'status':'作業中','next_action':'検証'})
        task=next(t for t in self.desk.snapshot()['tasks'] if t['id']==first['id'])
        self.assertEqual(task['due_date'],'2026-10-30')
        self.assertEqual(len(self.desk.snapshot()['tasks']),2)
    def test_conversation_is_project_scoped_and_limited(self):
        from conversation import history
        other=self.desk.mutate('project',{'company':'会社B','name':'別案件'})
        ids=[]
        for i in range(5):
            t=self.create();ids.append(t['id'])
            folder=self.desk.data/'requests'/t['id'];folder.mkdir(parents=True)
            (folder/'receipt.json').write_text(json.dumps({'request':'依頼'+str(i),'summary':'結果'+str(i)}))
        t=self.desk.mutate('create',{'project_id':other['id'],'title':'別案件の秘密'})
        folder=self.desk.data/'requests'/t['id'];folder.mkdir(parents=True)
        (folder/'receipt.json').write_text(json.dumps({'request':'他案件','summary':'他案件の秘密'}))
        got=history(self.desk,self.pid)
        self.assertEqual(len(got),3)
        self.assertEqual([x['task_id'] for x in got],ids[-3:])
        self.assertNotIn(t['id'],[x['task_id'] for x in got])
        self.assertTrue(all(x['task_id'] in ids for x in got))
        self.assertFalse(history(self.desk,other['id'],t['id']))
    def test_no_fuzzy_merge(self):
        self.note.with_name('【会社A：案件甲_改修】.md').write_text('## 現在地\n別の記録')
        self.assertEqual(len(self.desk.collect(force=True)['projects']),2)
    def test_persistence_and_events(self):
        task=self.create();self.desk.mutate('update',{'id':task['id'],'version':1,'status':'作業中','next_action':'機能を確認'})
        other=a.Desk(self.home,self.root/'data');saved=other.snapshot()
        self.assertEqual(saved['tasks'][0]['status'],'作業中')
        self.assertEqual(len(saved['events']),2)
    def test_optimistic_concurrency(self):
        task=self.create();self.desk.mutate('update',{'id':task['id'],'version':1,'status':'作業中','next_action':'確認'})
        with self.assertRaises(a.Conflict):self.desk.mutate('update',{'id':task['id'],'version':1,'status':'保留','blocker':'待ち'})
        self.assertEqual(self.desk.snapshot()['tasks'][0]['status'],'作業中')
    def test_done_requires_evidence_and_wait_requires_reason(self):
        task=self.create()
        for fields in [{'status':'完了'},{'status':'保留'},{'status':'確認待ち'}]:
            with self.assertRaises(ValueError):self.desk.mutate('update',{'id':task['id'],'version':1,**fields})
        self.desk.mutate('update',{'id':task['id'],'version':1,'status':'完了','result':'確認コマンドの結果: OK'})
    def test_stale_running_is_not_claimed_current(self):
        task=self.create();self.desk.mutate('update',{'id':task['id'],'version':1,'status':'作業中'})
        with self.desk.connect() as c:c.execute("UPDATE tasks SET updated='2020-01-01T00:00:00+09:00'")
        self.assertTrue(self.desk.snapshot()['tasks'][0]['needs_check'])
    def test_bind_unassigned_session_and_import(self):
        self.session.write_text(json.dumps({'customTitle':'【会社A：別の案件】'})+'\n')
        s=self.desk.collect(force=True);self.assertEqual(len(s['unlinked']),1)
        self.desk.mutate('bind',{'source_id':s['unlinked'][0]['id'],'project_id':self.pid})
        self.desk.mutate('bind',{'source_id':s['imported_tasks'][0]['id'],'project_id':self.pid})
        s=self.desk.snapshot();self.assertEqual(len(s['unlinked']),0)
        self.assertEqual(s['imported_tasks'][0]['project_id'],self.pid)
    def test_invalid_target_rejected(self):
        with self.assertRaises(ValueError):self.desk.mutate('create',{'project_id':'missing','title':'test'})
        with self.assertRaises(ValueError):self.desk.mutate('bind',{'source_id':'missing','project_id':self.pid})
    def test_remote_login_and_no_local_host_bypass(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),a.Handler);server.desk=self.desk;server.remote_access=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        try:
            for path in ['/api/state','/api/access']:
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(origin+path)
                self.assertIn(error.exception.code,[401,403]);error.exception.close()
            bypass=urllib.request.Request(origin+'/api/state',headers={'Host':'127.0.0.1:18765'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(bypass)
            self.assertEqual(error.exception.code,403);error.exception.close()
            body=json.dumps({'code':self.desk.access['code']}).encode()
            request=urllib.request.Request(origin+'/api/login',data=body,headers={'Origin':origin,'X-Desk-Token':self.desk.token})
            with urllib.request.urlopen(request) as response:
                self.assertIn('HttpOnly',response.headers['Set-Cookie'])
                cookie=response.headers['Set-Cookie'].split(';',1)[0]
            request=urllib.request.Request(origin+'/api/state',headers={'Cookie':cookie})
            with urllib.request.urlopen(request) as response:
                result=json.load(response);self.assertIn('projects',result)
                self.assertNotIn(self.desk.access['code'],json.dumps(result))
        finally:server.shutdown();server.server_close();thread.join()

    def test_http_api_and_origin_guard(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),a.Handler);server.desk=self.desk
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(origin+'/') as response:
                self.assertIn(self.desk.token,response.read().decode())
                self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
            body=json.dumps({'project_id':self.pid,'title':'ブラウザからのタスク'}).encode()
            request=urllib.request.Request(origin+'/api/tasks',data=body,headers={'Origin':origin,'X-Desk-Token':self.desk.token,'Content-Type':'application/json'})
            with urllib.request.urlopen(request) as response:self.assertEqual(json.loads(response.read())['status'],'未着手')
            bad=urllib.request.Request(origin+'/api/tasks',data=body,headers={'Origin':'https://example.com','X-Desk-Token':self.desk.token})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(bad)
            self.assertEqual(error.exception.code,403)
            bad_host=urllib.request.Request(origin+'/api/state',headers={'Host':'example.com'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(bad_host)
            self.assertEqual(error.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(origin+'/../app.py')
            self.assertEqual(error.exception.code,404)
        finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main(verbosity=2)
