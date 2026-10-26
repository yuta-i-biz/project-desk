#!/bin/sh
set -eu
cd "$(dirname "$0")"
mode=${1:-test}
case "$mode" in test|prod) ;; *) echo 'Use: deploy.sh test | deploy.sh prod BASE_REVISION'; exit 2;; esac
PYTHONWARNINGS=ignore::ResourceWarning python3 -m unittest discover -p 'test_*.py' -q
for test_file in test_*.cjs test_*.js; do node "$test_file"; done
node --check static/app.js
python3 scripts/check_features.py --static
if [ "$mode" = prod ]; then
 test -n "${2:-}" || { echo 'A verified live base revision is required'; exit 2; }
 test -z "$(git status --porcelain)" || { echo 'Commit changes before release'; exit 2; }
 python3 scripts/release.py --base "$2"
fi
