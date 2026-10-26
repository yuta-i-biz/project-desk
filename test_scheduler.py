import threading,unittest
from scheduler import ProjectQueue
class SchedulerTests(unittest.TestCase):
 def test_same_project_serial_different_project_not_starved(self):
  q=ProjectQueue(max_workers=2);entered=threading.Event();release=threading.Event();other=threading.Event();order=[]
  def first():
   entered.set();release.wait(3);order.append('first')
  try:
   a=q.submit(first,key='A');self.assertTrue(entered.wait(1))
   b=q.submit(lambda:order.append('second'),key='A')
   c=q.submit(lambda:other.set(),key='B')
   self.assertTrue(other.wait(1),'Aの順番待ちでBを占有しない')
   self.assertFalse(b.done());release.set()
   for f in (a,b,c):f.result(3)
   self.assertEqual(order,['first','second'])
  finally:release.set();q.pool.shutdown(wait=True)
 def test_failure_and_cancel_do_not_stop_next_project_job(self):
  q=ProjectQueue(max_workers=1);gate=threading.Event()
  try:
   first=q.submit(lambda:gate.wait(3),key='A')
   canceled=q.submit(lambda:None,key='A');self.assertTrue(canceled.cancel())
   failed=q.submit(lambda:1/0,key='A');last=q.submit(lambda:'done',key='A');gate.set();first.result(3)
   with self.assertRaises(ZeroDivisionError):failed.result(3)
   self.assertEqual(last.result(3),'done')
  finally:gate.set();q.pool.shutdown(wait=True)
