"""Recognize successful test runner calls from structured CLI events, not prose."""
import hashlib,json,re,shlex
from pathlib import Path

def runner(command,depth=0):
 if depth>2:return None
 try:words=shlex.split(command)
 except ValueError:return None
 if not words:return None
 if Path(words[0]).name in ('sh','bash','zsh') and len(words)>=3 and words[1] in ('-c','-lc'):return runner(words[2],depth+1)
 if any(w in words for w in ('||',';','|','&')):return None
 segments=[[]]
 for word in words:
  if word=='&&':segments.append([])
  else:segments[-1].append(word)
 for parts in segments:
  while parts and (re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*',parts[0]) or parts[0]=='env'):parts=parts[1:]
  if not parts:continue
  name=Path(parts[0]).name
  if re.fullmatch(r'python(?:\d+(?:\.\d+)*)?',name) and parts[1:3]==['-m','unittest']:return 'unittest'
  if re.fullmatch(r'python(?:\d+(?:\.\d+)*)?',name) and parts[1:3]==['-m','pytest']:return 'pytest'
  if name in ('pytest','pytest-3'):return 'pytest'
  if name in ('npm','pnpm','yarn') and (parts[1:2]==['test'] or parts[1:3]==['run','test']):return name+' test'
 return None

def successful_tests(path):
 found=[]
 with path.open(errors='replace') as stream:
  for line in stream:
   try:event=json.loads(line)
   except ValueError:continue
   if not isinstance(event,dict):continue
   item=event.get('item',{})
   if event.get('type')!='item.completed' or not isinstance(item,dict) or item.get('type')!='command_execution' or item.get('exit_code')!=0:continue
   command=item.get('command')
   if not isinstance(command,str):continue
   name=runner(command)
   if name=='unittest':
    count=re.search(r'Ran\s+(\d+)\s+tests?',str(item.get('aggregated_output','')))
    if not count or int(count.group(1))==0:continue
   if name:found.append({'runner':name,'exit_code':0,'command_sha256':hashlib.sha256(command.encode()).hexdigest(),'source':'structured CLI command_execution'})
 return found
