"""Read-only file inventory with streaming digests and no symlink traversal."""
import argparse,hashlib,json,os
from pathlib import Path

def inventory(root):
 root=Path(root)
 if root.is_symlink() or not root.is_dir():raise ValueError('a real directory is required')
 rows=[];groups={};skipped=[]
 for parent,dirs,files in os.walk(root,followlinks=False):
  parent=Path(parent)
  for name in dirs[:]:
   if (parent/name).is_symlink():skipped.append(str((parent/name).relative_to(root)));dirs.remove(name)
  for name in sorted(files):
   path=parent/name;relative=str(path.relative_to(root))
   if path.is_symlink() or not path.is_file():skipped.append(relative);continue
   digest=hashlib.sha256();before=path.stat()
   with path.open('rb') as stream:
    for chunk in iter(lambda:stream.read(65536),b''):digest.update(chunk)
   after=path.stat()
   if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('file changed during inventory')
   key=digest.hexdigest();rows.append({'file':relative,'bytes':before.st_size,'sha256':key});groups.setdefault(key,[]).append(relative)
 return {'files':rows,'total_files':len(rows),'total_bytes':sum(r['bytes'] for r in rows),'duplicates':[names for names in groups.values() if len(names)>1],'skipped_links_or_special_files':skipped,'source_modified':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('folder',type=Path);a=p.parse_args();print(json.dumps(inventory(a.folder),ensure_ascii=False))
