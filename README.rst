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

Request outcomes and projects
-----------------------------

Use the request progress menu to see final deliverables and remaining work. An individual request can be opened with /?view=results&task=TASK_ID. New projects are available from desktop and mobile menus and require choosing a company/activity; a new company/activity can also be entered. Existing same-name projects within the same company are rejected to avoid duplicate records. PDF previews render the first 20 pages as images for browser compatibility.

Execution quality milestone
---------------------------

Routing now checks the current adapter's supported operations, including selected image attachments. The text-only Gemini adapter is excluded from image inspection and image generation. The restricted Claude adapter is excluded from jobs requiring a shell test runner; this restriction is reported rather than silently weakening the job. This is an adapter capability inventory, not a live test of every installed tool.

Up to three different projects may run concurrently. Requests within one project remain sequential; waiting requests do not occupy workers. Recent conversation context and schedule snapshots are refreshed when a queued request starts. Unexpected execution errors are recorded as paused work.

Image and implementation jobs request a separate Codex read-only review after successful generation, using the existing subscription login. This consumes subscription usage and can add up to five minutes. Missing authentication, unavailable reviewers, malformed results, missing image inputs or per-image findings, and changing output files remain unverified. Actual image files are attached to the review invocation, with file hashes recorded in the receipt. Per-image findings must cover every output image; model prose alone without image input cannot establish visual inspection. Without a registered code copy, code review remains static. A registered code copy can receive a read-only test rerun; runtime success needs a structured successful test-runner event, and zero-test unittest runs are not accepted. Review logs remain private and are not served as artifacts.

The UI distinguishes execution failure, review findings, and incomplete verification. User-level Claude resources and configured integration names are inventoried without copying tokens or server configuration values. User-level MCP settings are inherited by Claude Code itself; the built-in --tools restriction does not disable MCP tools. Actual connections and project-level settings still require verification. Existing hooks are not a universal enforcement boundary for every AI.

Parity with the existing VS Code workspace remains incomplete: project workspace isolation, native command/MCP capability checks, GUI Keychain access for the background worker, and end-to-end image review on the Mac mini remain outstanding. This milestone does not enable direct edits to existing business files or deploy the running app.

Registered code workspaces
--------------------------

For implementation and file-editing requests, the app can now copy an explicitly registered local Git repository into the request's workspace/ directory. It copies the working files, including uncommitted changes, instead of modifying the original checkout or its Git metadata. Registration is a local administrator command, not an HTTP field supplied by the chat or AI:

python3 workspace.py --data /path/to/project-desk/data --project-id EXISTING_PROJECT_ID --source /path/to/project-repository

Only the registered project uses that source. Cross-project chat never activates a source workspace. Credential/configuration roots, secret file names, Git metadata, symlinks, database files, dependency caches and build/data directories are excluded. Copies are bounded to 5,000 files, 5 MB per file and 100 MB total; an oversized eligible source fails before AI execution rather than silently taking an incomplete code snapshot. Excluded files and dependencies can still prevent a test from running and are explicitly reported.

The AI works inside the request's copy under the existing Codex workspace-write sandbox. Original-file hashes are checked after execution and a reviewable workspace_changes.patch is generated for text changes. Binary changes are listed separately and are not silently represented as a text patch. Raw copied source files and the private manifest are excluded from the deliverable list; the changed source files are passed to the read-only reviewer. Original business files are never automatically patched or deployed. This is a bounded code-copy workflow, not full Git history or full VS Code parity.

Claude authentication diagnostics now distinguish a confirmed subscription login from an unverified status or an inaccessible Keychain in the background context. No credentials or account identities are exported, no password is requested by the app, and no API-key fallback is introduced. An inaccessible Keychain remains unresolved until the Mac mini's local access is established.

Registered-code reviewers may run tests only inside the copied workspace under the read-only sandbox, with Python bytecode writes disabled. Uploaded programs remain excluded from execution. Hosts provide copy/change checks, while successful runtime checks require structured CLI command events rather than model prose. If a test needs writes, dependencies, external access or unavailable tools, verification remains incomplete.

案件資料の引継ぎ
----------------

選択案件のローカル台帳と実行基準、登録されたコードのCLAUDE.md・AGENTS.mdを、各AIへ本文の抜粋として渡します。別端末の参照先は同名のローカルファイルで代用しません。1資料16KB、合計48KB、8資料まで。取得日時・更新時刻・抜粋ハッシュ・全文未読・未取得を記録します。既知の鍵・トークン形式は伏せますが、秘密情報の完全検出を保証するものではありません。認証ファイルや記憶全体を収集する仕組みはありません。

検証の限界
----------

Codexの隔離環境でソケットの作成が制限される場合、HTTPサーバーを使用するテストは実行できません。CLIの終了コード0と全テスト成功は同じではありません。登録したコードの原本不変と、モデル側の実行結果、ホスト側の回帰検証を区別してください。
