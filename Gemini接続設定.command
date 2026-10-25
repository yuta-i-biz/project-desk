#!/bin/zsh
cd "$(dirname "$0")" || exit 1
print 'Googleの契約アカウントでログインしてください。接続確認後は /quit で終了してください。'
./vendor/bin/agy
/usr/bin/python3 ./connect_gemini.py
read '?Enterで閉じる'
