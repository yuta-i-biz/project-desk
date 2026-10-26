"""Bounded parallel projects; a project's waiting jobs never occupy a worker."""
from collections import defaultdict,deque
from concurrent.futures import ThreadPoolExecutor,Future
import threading
class ProjectQueue:
 def __init__(self,max_workers=3):
  self.pool=ThreadPoolExecutor(max_workers=max_workers)
  self.lock=threading.RLock();self.pending=defaultdict(deque);self.active=set()
 def submit(self,fn,key=None):
  key=key if key is not None else object();future=Future()
  with self.lock:
   self.pending[key].append((fn,future))
   if key not in self.active:
    self.active.add(key);self.pool.submit(self._run,key)
  return future
 def _run(self,key):
  with self.lock:fn,future=self.pending[key].popleft()
  try:
   if future.set_running_or_notify_cancel():
    try:future.set_result(fn())
    except BaseException as error:future.set_exception(error)
  finally:
   with self.lock:
    if self.pending[key]:self.pool.submit(self._run,key)
    else:self.active.remove(key);del self.pending[key]
