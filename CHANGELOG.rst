開発記録
========

2026-10-26
----------

* アプリと共有記録をMac miniへ移行。
* チャット中心の画面に案件の現在地と実行結果を統合。
* Codex・Claude Code・Geminiの接続確認と利用可能なAIへの振り分けを追加。
* CodexとGeminiのアプリ経由の実行・結果取得を確認。
* 期限超過、期日未設定、工程管理上の不足を表示する読み取り専用の一覧を追加。
* コピーされた表内タイトルで別タブの案件が混ざる問題を修正。
* 端末ごとの読み上げ、重要箇所の要約、停止、明示的な音声会話モードを追加。
* Pythonの16検証に合格。音声の案件限定・パス除去・長文制限の5検証に合格。
* 実機のマイク・スピーカー検証は未完了。

追加検証と反映
--------------

* 期日・開始予定日・所要日数・前工程・完了条件を追加。
* 日付の妥当性、日付の逆転、別案件の前工程、依存の循環を検査。
* DBの既存行を保持する項目追加と、日程を維持する状態更新を実装。
* Pythonの17検証に合格。音声要約の5検証に合格。
* 音声入力中・入力欄の操作中の再描画を抑制。認識に失敗した際の自動送信を防止。
* 外出先接続は利用者の許可待ち。過去の会話の自動引継ぎも許可待ち。

許可済みの会話引継ぎ
--------------------

* 選択した案件の直近3件までの依頼・返答を次の実行へ渡す。
* 別案件の履歴、今回の依頼自身、未取得の返答は含めない。
* 同じ秒に作成された会話も登録順で判定する。
* Pythonの18検証に合格。公開接続の方式は選定中で、外部接続は未有効。

Funnel接続の準備
----------------

* 利用者の指定によりTailscale Funnelを接続候補として追加。
* 専用認証口のみ転送し、既存の別サービスがある場合は停止する。
* tailnet管理者によるFunnel有効化を検出。管理者操作待ちで、外部接続の検証は未完了。

Authenticated remote access verified
------------------------------------

* Enabled Tailscale Funnel on the Mac mini runtime.
* Verified public HTTPS login, protected project and artifact endpoints, and Secure/HttpOnly cookies.
* Updated mobile connection guidance; physical phone voice testing remains pending.

Voice request controls
----------------------

* Added explicit end-of-speech request submission and live transcription.
* Prevented automatic submission after recognition errors or page hiding.
* Verified four recognition lifecycle cases plus five existing summary checks.
* Physical mobile microphone testing remains pending.
