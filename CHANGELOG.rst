2026-10-27: Full references and reusable assets
---------------------------------------------
* Keep full sanitized reference snapshots; preview size no longer removes documents or tails.
* Supply full reference text to providers without file tools and a paged/searchable reader to file-capable providers.
* Retain project-scoped skills, components and programs with immutable versions and host verification evidence.
* Present reusable assets in system status; offer verified resources without extra AI classification calls.

2026-10-27: Independent review recovery
---------------------------------------
* Execute registered unittest suites in a disposable macOS sandbox copy.
* Permit loopback tests; deny external connections and writes outside the copy.
* Keep static reviewer read-only; attach host-owned hash-bound test evidence.
* Continue all review groups after an unverified group; never convert missing checks to success.

自律改善の反復
----------------

* 前回の修正済みコピー・追加/削除・検品記録を次の改善へ引継ぎ、最大3回で検証。
* 変更不要なら終了、検品の指摘は再改善、実行失敗や検証不能は停止。本番への自動反映なし。
* 引継ぎ元は同じ案件の自律改善記録だけ。原本の変更が検出された場合は引継ぎを拒否。

2026-10-27 共通設定・定期処理・自律改善・ML施策の検証
--------------------------------------------------

* 共通CLAUDE.mdと案件のGEMINI.mdも全AI向け資料に含め、渡したルールの指紋を記録。
* 業務用LaunchAgentsの状態・前回終了番号・ログ更新日時を読取り表示。生ログ・環境変数・認証情報は返さない。
* 明示的に有効化した場合だけ、登録コードのコピーで自律的に調査・修正・検品。同じ版・障害の再実行を抑止し、原本無変更と独立検品が揃うまで保留。本番反映は自動化しない。
* MLの登録範囲から予定売上・予定利益・買取件数を集計。重複・不正値・取得範囲の限界を検知した場合は表示を停止。古い値を最新として扱わない。
* MLの案件と検証指標の候補を並べ、月途中・店舗構成・同時施策の影響を区別。効果の因果関係は未検証。

Plaud・既存の夜間処理の可視化（反映前）
--------------------------------------

* 既存のPlaud取得・決定/TODO抽出・仕分け・夜間実行の記録を読取り、重複ワーカーを起動せず表示。
* 承認待ち、情報不足、AI側の検品失敗、他担当者、未判定を区別。未判定をAI不可と扱わない。
* 同一日・同一出所・同一IDの結果だけを照合。案件の曖昧な紐付けは推測しない。
* この変更だけでは、既存ランナーの対象外案件を自動実行しない。全案件への拡張は未完。

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

接続継承と承認済み工程の自律進行
--------------------------------

* Claudeの画面側プロセスへ依頼を渡す経路を追加。認証情報をコピーせず、接続成功の判定は実際の認証結果に限定。起動設定の有効化は明示操作。
* Google資料の読取り専用MCP接続を追加。依頼文で明示されたGoogleファイルIDだけを許可し、更新・送信・検索・削除は提供しない。
* 工程と完了条件を保存し、利用者が開始を承認した工程だけを順番に実行。実行成功と独立検品が揃わない場合、受付結果不明・再起動・利用制限の場合は停止。勝手な再実行をしない。
* 自動工程はCodexの隔離環境で実行し、既存MCPを無効にできたことを実効設定で確認する。
* 実環境のGoogle接続で読取り5機能と未存在ファイルの拒否を確認。Codex経由の実読取と正常時の連続実行は利用制限429のため未検証。実AIの自動工程は最初の失敗で停止し次工程が始まらないことを確認。

Claude画面側経路の実応答確認
--------------------------

* Mac miniの一時GUIワーカーでClaude契約ログイン、実際の固定文字応答、正常終了を確認。
* 認証情報のコピー・抽出・リセットは実施せず、一時ワーカーと検証フォルダは終了後に削除。
* 稼働版の起動経路変更と常用ワーカーの有効化は最終承認後に行う。
