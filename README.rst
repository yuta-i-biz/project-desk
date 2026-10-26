Project Desk
============

Mac miniで動く個人用の案件・タスク管理アプリです。チャット、案件の進捗、実行結果、音声入出力を一つの画面にまとめます。

実行場所
--------

アプリ本体とAIの実行はMac miniだけで行います。スマホはブラウザを使う操作端末です。GitHubはコードと開発記録の保管先で、アプリや業務データの実行・保管先ではありません。

既存のCodex / Claude Code / Gemini契約ログインを使います。APIキーを追加する方式へ自動で切り替えることはありません。GeminiはGoogleの後継Antigravity CLIで利用可能なGeminiモデルを確認します。AI側のログインと契約が別途必要です。

起動
----

Mac mini上でPython 3.9以降を使い、プロジェクトの起動.commandを開きます。アプリは127.0.0.1:18765で動きます。外部接続用の認証付き口は127.0.0.1:18767です。通常の起動だけで外部公開はしません。

音声
----

読み上げONは端末ごとに設定します。重要事項や新しい結果の短い説明を読みます。会話モードは音声入力の自動送信を明示的にONにした場合だけ使います。マイクの許可が必要です。ブラウザによって音声認識は外部の認識サービスを利用します。画面が閉じた状態・ロック状態・バックグラウンドでの継続動作は保証しません。実際のスマホでの検証は別途必要です。

公開対象
--------

このリポジトリにはアプリのコード、検証、開発記録だけを置きます。案件名簿・会話履歴・SQLite・認証情報・ログ・スクリーンショット・成果物は公開しません。元の業務ファイルは変更せず、作業記録は実行端末のdataフォルダに保存します。送信・金銭・原本上書き・本番反映の承認条件は維持します。

検証
----

python3 -m unittest discover -p 'test_*.py'
node test_voice.cjs

既知の未完了
------------

* 既存の期日未設定タスクの工程化と、期間を描画するガント表示
* スマホ実機での音声入出力と表示の検証
* 実行中にサーバーが終了した場合のジョブ再開
* 外部公開する場合の安定URLと個別端末セッションの整備
* 各端末の認証・画面操作権限の検証

日程の登録
----------

新規依頼には任意の期日を指定できます。作業の状態更新画面で開始予定日、期日、所要日数、前工程、期日未設定の理由、完了条件を登録できます。同じ案件以外を前工程にしたり、循環する前工程を登録したりすることはできません。日付は未確定のまま保存でき、システムが勝手に締切を作ることはありません。

外出先接続
----------

start_remote_access.pyは明示的な--enable指定でCloudflareの一時HTTPS接続を作ります。専用の認証付き口だけを転送します。案件データの通信はCloudflareを通るため、利用者の明示的な許可後だけ有効にしてください。一時URLは変わるため、安定した本番URLとは扱いません。

Tailscale Funnel
---------------

Mac miniの既存Tailscaleを使う代替接続を追加しました。スマホ側はTailscaleアプリやVPN操作が不要です。tailnetの管理者がFunnelを有効にした後、Mac miniで start_funnel.py --enable を実行します。認証付きの127.0.0.1:18767だけを接続し、既存の443番の別サービスを上書きしません。公開URLでもアプリの接続コードは必要です。

File intake and previews
------------------------

The Mac mini runtime uses its existing ~/.claude/tools/google_auth.py OAuth helper for Drive storage. It requires google-api-python-client and google-auth-oauthlib in the runtime Python environment. Credentials are not part of this repository. Drive files are created privately; existing shared folders are not used automatically. Generated Drive IDs are persisted before upload for safe retries.

macOS PDFKit/Vision OCR is compiled from native/file_reader.swift on first use when needed. Files are limited to 50 MB each; PDF reading is bounded to 40 pages and textual previews to 100,000 characters. AI context contains up to 16,000 characters per selected attachment, with originals copied to the dedicated request folder. Audio/video and unsupported binary formats are stored without claiming transcription or full content understanding.

Artifact previews are limited to 20 MB. Office previews show extracted contents, not the original page layout. HTML previews cannot execute scripts or make external requests.
