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

Company deadlines and multiple project requests
----------------------------------------------

* Grouped overdue tasks and projects by company/activity with filters and source timestamps.
* Separated missing dates and unassessed projects from overdue work.
* Added up to six project-specific requests in one submission, queued for sequential processing.
* Verified date formats, company isolation, completion exclusion and bulk request payload separation. Python: 18 tests passed.

Cross-project chat and connected gantt
-------------------------------------

* Added task/project instructions directly from deadline cards.
* Added cross-project search and AI chat with explicit all-project scope and a reusable conversation project.
* Added app-local gantt charts and validated explicit user-backed date/status updates from AI receipts.
* Kept source Google documents unchanged using local schedule overrides for imported tasks.
* Verified 24 Python tests, JS checks, browser navigation/search, and real Codex start/due date updates on an isolated Mac mini test project.

Files, Drive storage and in-app artifact previews
------------------------------------------------

* Added authenticated 50 MB file intake, project classification and private Drive storage under Project Desk/company/project.
* Added bounded text, modern Office, PDF and image OCR reading; unsupported files remain stored with explicit status.
* Added selected attachments to project AI requests with project isolation.
* Added inline image/SVG/PDF/text/table/Office-content previews and sandboxed HTML previews.
* Added configurable company aliases without changing project IDs or source ledgers.
* Verified 34 Python tests, browser preview/file controls, native PDF/image OCR, and real private Drive upload with byte verification.

Request outcomes and project creation
-------------------------------------

* Prioritized final deliverables, friendly request titles, and outstanding work in request results.
* Collapsed implementation assets and added direct links to individual request outcomes.
* Added desktop/mobile project creation with company/activity selection and duplicate prevention.
* Replaced embedded PDF frames with native page-image previews for mobile and in-app browser compatibility (up to 20 pages).
* Verified 36 Python tests, request summary checks, company-selection validation and real multi-page PDF display.

Manual project visibility fix
-----------------------------

* Fixed new manual projects being hidden by legacy-source filtering when a canonical company gantt exists.
* Displayed company names in project selection and chat headers.
* Reproduced the defect with a failing test, then verified all 37 Python tests and the live project deep link.

2026-10-26 接続確認と成果物表示の改善
---------------------------------------
* サーバー再起動後も下書きを保持し、送信直前に同一サイトの接続確認情報を更新。確認失敗時は送信せず、二重送信もしない。
* 長いPDF・画像の閲覧中も、ファイル名と閉じるボタンを上部に固定。
* 古い接続情報、更新失敗、単回送信の自動検証と実画面のスクロール確認を実施。

2026-10-26 AI selection, review and parallel execution
-----------------------------------------------------

* Route selected image attachments and image generation requests only to adapters exposing the required operations. Keep restricted adapters from silently replacing implementation-plus-test work with text output.
* Run up to three projects concurrently, keep each project's requests sequential, and refresh conversation and schedule context when execution starts.
* Add a separate read-only Codex review with actual image attachments and file fingerprints. Distinguish review findings, incomplete verification and execution failure in chat and results. Keep review sessions ephemeral and private.
* Preserve longer responses and expose configured Claude resource names without copying credentials. Configuration presence does not establish connection availability or full workspace parity.
* Fix invalidation of project snapshots when the monotonic clock is near its origin, reproduced on the Mac mini's Python 3.9.6.
* Validation: 51 Python tests passed locally and in an isolated Mac mini package; all six JavaScript test programs passed. Live synthetic-image checks accepted a matching blue square and rejected a blue square incorrectly described as red.
* This release also includes the previously prepared waiting-task navigation, unified chat scrolling and expandable input controls. Full existing-workspace execution and background Claude authentication remain incomplete.

Post-deployment viewport check
-----------------------------

* Reduced the project picker, conversation heading and composer spacing after the real 1280x720 screen showed too little space for messages. Kept the input anchored and the conversation independently scrollable.

Registered source copies and authentication diagnostics
-------------------------------------------------------

* Added local-only registration of project Git repositories and bounded request-local working copies, preserving dirty working files while excluding credentials, symlinks and dependency/data directories.
* Added original-file hash verification, text patches, changed-file review inputs and in-app copy/change summaries. Original checkouts and their Git metadata are not edited.
* Distinguished background Keychain access failures from a confirmed logout. The SSH path still cannot read the login Keychain; a temporary GUI-context diagnostic did not establish successful authentication. No credentials were copied or reset.
* Real isolated Mac mini execution fixed a two-file calculation fixture in the copy, passed the fixture's unit test, left originals unchanged and produced a patch. Independent review outcomes are recorded separately from successful execution.

* Final validation for this milestone: 66 Python tests and six JavaScript test programs passed. Mac mini Python 3.9.6 also passed all 66 tests. The real isolated Codex workflow completed the source-copy fix, an independent read-only review/test rerun, original-file verification and patch generation. The new code is prepared for rollout; existing workspace parity remains incomplete.

チャット入力欄を下部に固定
--------------------------

* 会話・全案件検索・ガントチャートを同じスクロール領域にまとめ、入力欄を下部に維持。
* スマートフォンの表示領域縮小に追従。拡大操作ではレイアウトを縮めない。
* 表示領域の5検証とJavaScript構文検証に合格。スマートフォンの実機確認は未完了。

本人対応とAI側の作業を区別
--------------------------

* 「あなたの対応」画面を追加。会社・案件ごとに理由、次の一手、記録された期限、対象画面へのボタンを表示。
* 検品不足・失敗・古い作業中記録をAI側へ分類。一般的な確認待ちは担当未確定として扱う。
* この分類は助言のみで、自動実行権限を付与しない。

案件資料を全AIへ引き継ぐ
------------------------

* 選択案件の台帳、実行基準、登録コードのルールを、3つのAIへ本文抜粋で渡す処理を追加（ユーザーの明示許可済み）。
* 別端末の同名ファイル、別案件、認証ファイルは対象外。更新時刻、抜粋ハッシュ、全文未読・未取得を記録。秘密情報の既知パターンを伏せる。
* 認証確認の時間切れをログアウトと区別。GUI側の確認コマンド成功だけではClaude接続成功としない。
