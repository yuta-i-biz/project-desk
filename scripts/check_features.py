import argparse,json
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--static',action='store_true');parser.parse_args()
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'scripts/feature_manifest.json').read_text())
missing=[]
for name,markers in manifest.items():
 text=(root/name).read_text()
 missing.extend(name+': '+mark for mark in markers if mark not in text)
if missing:raise SystemExit('\n'.join(missing))
print('Feature markers:',sum(map(len,manifest.values())),'present')
