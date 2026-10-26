---
name: jechulok-submission
description: Parse Korean technical submission criteria, prepare JPG images or selected PDF pages on local disk, and recheck output requirements. Use when users ask to resize a photo to exact pixels, limit a JPG file to a KB threshold, inspect image/PDF format and dimensions/pages, or prepare a locally verifiable submission file. Do not use for document content review, passport-photo compliance, OCR, legally binding signatures, Office conversions, or automatic uploads.
license: MIT
compatibility: Python 3.11+ with Pillow and pypdf installed. Local filesystem read/write permission required; no network access used during processing.
metadata:
  author: jechulok
  version: "2.6.0"
---

# JeChulOK Submission Agent Skill

## v2.6 — Voluntary categorical feedback insights, locally only

`scripts/feedback_insights_v26.py` implements read-only `prioritize`
and `compare` over **explicit user-selected local v2.5 feedback
folders**. Its ranking is category frequency among opt-in responses,
not a severity score. The comparison reports descriptive per-cohort
proportions but does not claim measured product improvement or causality.

The analyzer **reuses v2.5 privacy suppression**, and additionally
requires at least 10 records in each relevant cohort. Sparse issue
categories cause that entire ranking/comparison to be withheld.
No raw feedback records, paths, names, contents, notices, file inputs
or user-level activity are included in result JSON. No network use,
auto-sharing, writes or client instrumentation.

Because entries contain no timestamps, human identity or real
product-version attribution, duplicates/independent cohorts cannot
be verified. Results are strictly self-selected descriptive evidence
to guide *future independent human testing*, not a real-user quality
measurement. CI runs 20 synthetic checks from
`scripts/feedback_insights_audit_v26.py --check` plus unit tests.
The existing **20 MCP tools** and separate file-execution approval
rules remain unchanged. See RELEASE_NOTES_v26.md and FEEDBACK.md.


## v2.5 — Human-initiated, categorical, local-only feedback

A separate CLI, `scripts/feedback_v25.py`, now supports `preview`,
`save` and `summary` for voluntary product feedback. This is NOT
automatic MCP telemetry: no tracking, email, freeform notice text,
source paths, timestamps, user IDs, system fingerprint or network
access is allowed. Three fields only: stage, issue and impact categories.

Preview makes no changes. Saving requires an explicit existing canonical
destination directory and creates an exclusive local JSON record with
POSIX 0600 permission. The local `summary` command suppresses
all breakdowns if there are under five entries and suppresses an entire
dimension if any category count is under three. Sharing results requires
a separate manual privacy review; the tool never uploads data.

`python scripts/feedback_audit_v25.py --check` exercises 30 invented
responses and one aggregate safety check. These **31 synthetic conditions**
are NOT actual user feedback, user satisfaction scores or a representative
sample. No external volunteers were recruited by this release.

Full instructions: FEEDBACK.md and RELEASE_NOTES_v25.md.
All existing 20 MCP tools, local file scope and manual approvals remain.


## v2.4 — First-run guided UX state (no new permissions)

The existing `assist_submission` MCP tool adds a path-free **experience**
result with current stage (of 5), next human action, curated next-step help,
unselected input count, safe item IDs/formats, unresolved notice/plan issue
count, and whether a separate exact-plan approval is required.

The original workflow response with full reviewable paths is preserved;
the new `experience` card omits notice text, file paths and telemetry.
Its progress percentage is **only a step indicator**, NOT preparation
completion, upload status or institutional acceptance. Filename hints
never auto-select files; opening a preview never grants consent.

Run `python scripts/first_run_audit_v24.py --check` for a deterministic
**24-case synthetic** UX audit (6 invented two-document notices × 4 states).
It checks group file requests, errors, safe approval prompting, progress,
no side effects and absence of private paths in the new summary.
Reported question-count savings are against a **hypothetical**
one-prompt-per-file comparator, NOT measured real-world improvements.
No users were recruited, surveyed or tracked by this release.

See RELEASE_NOTES_v24.md. All 20 MCP tools, consent gates, local file
restrictions and existing v2.3 recovery checks remain unchanged.



## v2.3 — Explicit, read-only recovery plan and 14 synthetic lifecycle regressions

`python scripts/setup_mcp.py recovery-plan --allowed-dir YOUR_WORK_FOLDER
--archive TRUSTED_RELEASE_ZIP --destination NEW_SKILL_FOLDER` inspects the
current skill's VERSION/manifest diagnostics and validates a manually
provided portable ZIP and nonexistent destination. This command is
**read-only**, omits sensitive absolute paths and returns sanitized JSON
with the safe **manual** extraction, dependency-install, MCP recheck and
client-configuration switch/rollback sequence. It does not execute a
possibly compromised old installation, authenticate a publisher, install
dependencies or modify user files. Always run it from a **trusted copy**.

`python scripts/recovery_scenarios_v23.py --check` runs **14 disposable
synthetic** lifecycle/error/rollback scenarios: verified ZIP, read-only
preview, deliberate old-source corruption, unsafe destination/archive
rejection, new side-by-side extraction, local manifest validation,
copy-only client configuration, actual 20-tool stdio MCP handshake and
preservation of mock user files. CI uploads its aggregate report.
This is NOT real human beta validation; it does not install a new venv
in the recovered copy. The independent real fresh-vEnv CI test remains.

No new MCP tool, network client, automatic update, client config editing
or file-creation consent was added. See RELEASE_NOTES_v23.md and SECURITY.md.


## v2.2 — Accessible, read-only onboarding and safe repair priorities

`python scripts/setup_mcp.py guide --allowed-dir YOUR_FOLDER` is a
**read-only, Korean-language** setup wizard in plain text. It supports
`--language en`, `--format json`, and `--client codex|cursor|claude-desktop`.
No ANSI colors, private work paths, document content or subprocess logs
are exposed in the guide output.

The guide prioritizes dangerous VERSION/manifest inconsistencies over
ordinary venv/dependency failures. On source tampering, it refuses to
suggest executing a potentially modified installer; the user must obtain
a trusted copy separately and install into a new folder.

When doctor passes, the guide presents `probe` as a separate step.
It **never launches a probe unless `--probe` is explicitly supplied**.
After a successful 20-tool stdio handshake it suggests a copy-only MCP
client config command; it never edits host settings or verifies host
registration. Only the user can separately approve installs/repairs.

This feature does not add MCP tools (20 remain), network calls, telemetry,
automatic repair, file conversions, or institutional uploads. Run the
v2.2 ZIP packaging/integration suite before distributing the version.
See RELEASE_NOTES_v22.md and QUICKSTART.md.


## v2.1 — Explicit opt-in update checks and manifest-backed local doctor

No MCP tool count or execution consent changes; **20 tools** remain.

The setup CLI now supports `updates`. Without `--online`, the command
reads local version metadata only and performs **zero network requests**.
With explicit `--online`, it requests the fixed GitHub HTTPS endpoint for
the latest **published stable release**, validates bounded metadata and
compares strict version triplets. It never downloads, installs or transmits
document data. Missing published releases or network errors are reported
without modifying the installation.

`doctor` verifies the VERSION/SKILL.md metadata and, **only when a
packaged installation includes MANIFEST.json**, checks the hashes and byte
lengths of each installed source file. A Git checkout is marked
**not manifest verified** rather than inaccurately passing integrity.
This self-contained manifest is not a publisher signature and cannot
authenticate the source if the manifest and code were both tampered with.

`beta-check` produces a local-only compact diagnostic. It checks Python,
dependency imports, source consistency and real MCP stdio connection.
It does not inspect applicant documents or send telemetry. It also cannot
confirm that an external host IDE registered the MCP server.

Read BETA_GUIDE.md for an opt-in, synthetic-data tester protocol, and
RELEASE_NOTES_v21.md for limitations. No real external beta feedback or
independent audit has been collected in this release.


## v2.0 — Tested portable ZIP and opt-in side-by-side upgrade

The skill version is now 2.0.0, but all **20 existing local MCP tools** retain
their names and authorizations. `scripts/release_v20.py` builds a portable
source ZIP plus SHA-256 sidecar and independently checks each release member
against the bundled manifest. The ZIP excludes tests, private evaluation
corpora, generated files and local runtime virtual environments.

Use `python scripts/setup_mcp.py upgrade --allowed-dir WORK_DIR --archive
LOCAL_ZIP --destination NEW_FOLDER` to **preview**. Only a separate command
with `--execute` extracts to a new, not-yet-existing folder. The running
MCP server, previous installation, dependency environment and client config
are never silently replaced. The user must explicitly run the new folder's
install, doctor, probe and copy the newly generated config to switch.

A CI job checks that the extracted archive starts a real 20-tool MCP stdio
server. A v2.0.0 tag-triggered workflow is **configured** to run a release
gate and publish archives; it does not publish anything until that Git
tag is intentionally created. Checksums are NOT publisher signatures.
No third-party security audit or real-user acceptance study is implied.
Read RELEASE_NOTES_v2.md and SECURITY.md before external deployment.


## v1.9 — Local real-notice evaluation framework, never fabricated results

The local evaluator `scripts/evaluate_real_v19.py` accepts an **external,
private** JSONL corpus of legally reusable, manually redacted submission
rules. This release **does not include** any real notices, real annotators,
or real-world quality scores. Its value is a reproducible evaluation
workflow ready for independently collected evidence.

The input requires exactly two different human reviewer IDs and labels
per notice (explicit parsed rules or ambiguous/needs_review). Disagreements
are excluded until adjudicated by a different third reviewer. The evaluator
reports aggregate agreement rate, field-value precision and recall,
constraint omission/wrong-value rates, exact notice matches, unsafe
acceptance of ambiguous notices and false blocking of valid notices.

It validates mandatory reuse authorization and human privacy-review
attestations, rejects duplicate cases/notices and obvious email, phone or
resident-number patterns. These checks do **not** prove that a real notice
is anonymized or redistributable. Never place actual corpus content in
the GitHub repository or CI artifacts. Input is evaluated locally only,
and output contains **aggregate counts**, not notice texts/IDs/reviewer
names. Use `--strict` to require all annotation conflicts resolved.

For repeatable CI only, an explicitly **synthetic** four-case JSONL fixture
is provided; its results do not count as real-world evaluation.
See REAL_EVALUATION.md for corpus schema, review protocol and metrics.
No new MCP tool was added, and no file-generation permission changed.


## v1.8 — Evidence-based synthetic guidance regression evaluation

For reproducible local quality checks, run
`python scripts/evaluate_v18.py --check` from the skill directory.
This produces JSON results from exactly **100 distinct synthetic notices**
in four controlled groups of 25:
explicit rules, ambiguous notice rejection, candidate-selection safeguards,
and unauthorized execution rejection.

The **expected ground truths are defined independently** of the product
outputs in the evaluation script. Case identifiers and pass/fail counts are
inspectable in the JSON artifact published by GitHub Actions for Linux
Python 3.11. The entire existing functional/security suite continues to run
on Windows, macOS, and Linux / Python 3.11 and 3.13.

The runner creates only synthetic throwaway fixtures, including misleading
filenames whose bytes are deliberately invalid, to confirm that name-based
hints are never presented as content-verified or auto-selected. It never
touches real user documents or grants execution approval.

**Never describe a synthetic 100/100 score as real-world notice parsing
accuracy, real candidate relevance, or actual user satisfaction.** The
single grouped-choice question is a static two-item fixture observation,
not a measured user conversation. See EVALUATION.md for definitions,
limitations and the required independent real-world evaluation.


## v1.7 — Concise and grounded human-facing guidance

The MCP tool count remains **20**. `assist_submission` now optionally
accepts `source_directory` for read-only file hints, but **never scans a
directory automatically**. Only when the caller explicitly provides an
authorized directory AND some submission items lack inputs does it inspect
up to 250 immediate directory entries using the existing
`suggest_files` helper. It returns at most 3 filename/extension-only
candidate hints per missing item. The user must personally select each
input; do not label hints as correct, inspect their contents, or auto-map.

When multiple items still lack input paths, present **one human prompt**
covering all missing items. The result includes `file_selection.items`
with `item_id`, expected format, optional hints, and
`requires_explicit_user_selection=true`. No input selection is saved.

For ambiguous notices, show `notice_explanation.issues` with a bounded
source-line number, short original evidence, static issue code, explanation,
and specific next human action. This is not an AI-generated correction:
ambiguous global rules and duplicate document types continue to block
execution. For invalid plans show `problem_explanation`, which translates
real preflight blockers into static actionable guidance while preserving the
original reason excerpt and the conservative read-only behavior.

The older `guide_submission_workflow` tool and all action names,
submission flags and plan fingerprint checks remain compatible.
Neither clarification nor source-directory hints counts as human approval.
No generated output or institutional upload is permitted before an
unambiguous plan, separate consent and final locked preflight.


## v1.6 — Single guided entry point, no automatic consent

For new conversational workflows, prefer the new **`assist_submission`**
tool (20 tools total). It is a stateless local guide with five steps:
1. Validate notice, ask the user to clarify ambiguous requirements.
2. Request explicit file-to-item mappings (never pick files silently).
3. Present the exact input/output/page/crop plan with
   `approval_fingerprint` (SHA-256 of deterministic plan JSON).
4. With **separate real human approval**, call
   `assist_submission(action="start", notice_text=..., assignments=...,
   approval_fingerprint=..., execute=true, confirm_execution=true)`.
   The server recomputes the plan and checks the fingerprint both before
   and after acquiring the existing cross-process writer lock. It refuses
   changed plans and does not auto-reuse a previous approval.
5. Poll with `assist_submission(action="status", job_id=...)` (or use
   `action="cancel"` to request cooperative cancellation). After
   completion call `assist_submission(action="verify", notice_text=...,
   final_files=...)`. Technically passing files STILL require manual
   content and submission-receipt checks.

`action="next"` is read-only. `action="start"` without **both**
execution flags AND a matching fingerprint is also read-only. A plan
fingerprint proves only that the supplied paths/rules correspond to the
last preview; it is NOT a signature, a file-content hash or reliable
proof of actual human consent. The agent must show the preview to the user
and obtain explicit approval. It must not synthesize approval itself.

This tool stores no notices or assignments on disk; approved background
jobs still use the v1.4/v1.5 private journal and protections.
Existing MCP tools remain available unchanged.


## v1.5 — Cross-process write safety and understandable recovery

The local-only stdio MCP server retains **19 tools**. Approved background
batches now acquire an **OS-managed exclusive lock** in the first allowed
directory's private `.jechulok-jobs/.writer.lock` before reading crash
journals or creating output stages. Only one compliant JeChulOK v1.5 MCP
instance using the **same first allowed root** may write/publish at a time.
The lock stays held through job completion, rollback and journal update.
The operating system releases a lock on process exit; its presence on
disk does NOT imply a running job, and must not be deleted manually.

If another process holds this lock, `start_submission_job` returns
`status=busy` and `code=folder_writer_active`, and does not create output.
Explicit interrupted-job cleanup also refuses to act while another
process holds the lock. Preview/inspection is read-only and does not
create a lock directory. The crash journal is rescanned *after*
acquiring the lock to prevent a stale state from authorizing execution.
Never reuse earlier approval after a refused, interrupted or cancelled job.

To make recovery understandable, `list_interrupted_submission_jobs`
returns `interrupted_job_count` and each recovered job now includes
`staging_file_count`, `final_output_count`, whether the previous
process might still be active, and a single recommended next action.
A currently running job in the **same MCP instance** is not incorrectly
shown as a crashed job. Final files are never deleted during recovery
and explicit user confirmation is still required for temporary-file cleanup.

This is **advisory OS locking**, not a secure sandbox or distributed lock.
It does not stop other software or previous JeChulOK versions from
modifying the same directory, nor protect overlapping work folders when
the MCP instances use **different first-root configurations**. Use one
canonical directory as the shared first root and keep filesystem
permissions narrow. Multi-file publication is not fully atomic.


## v1.4 — Crash-safe local job records and explicit recovery

The local MCP now exposes **19 tools**. Approved background jobs
(`start_submission_job` with two execution flags *after real user approval*)
write a **private, local, atomic job journal** in
`JECHULOK_ALLOWED_DIRS`'s first configured root under
`.jechulok-jobs/`. On POSIX the directory and files are created with
restrictive permissions. Records contain a job ID, state, staged and final
output paths and progress counts, but **no notice text, source file paths,
document contents, upload tokens or reusable approval**.

New jobs prepare JPG/PDF into a random, exclusive, same-directory
`.*.jechulok-<job-id>-<item-id>.jpg/pdf` staging name. Every item is
technically checked before publishing. Published files use an exclusive
hard link to prevent overwriting another process's final filename.
The original files remain unchanged. A cancelled/failed normal batch
cleans up its private staging files. Publishing is **not a single atomic
multi-file transaction**: an OS crash in the publishing phase may leave
some approved final outputs. Those outputs are never automatically deleted.

After a crash or forced restart, call `list_interrupted_submission_jobs`
to inspect **recorded** unfinished jobs, temp filename presence and
possible final outputs. An old job is **never restarted automatically**;
starting a new approved job is blocked until interrupted records are reviewed.

To resolve, call `resolve_interrupted_submission_job(job_id)` first
(read-only preview). ONLY after the user checks final output paths and
authorizes private temp cleanup, call it with
`cleanup_staging=true`, `confirm_cleanup=true`, and
`checked_final_outputs=true`. The tool verifies the stored random stage
name, scope and symlink safety, refuses cleanup if the old PID may be alive,
and deletes **only** verified staging files; it leaves all final output
files intact. It then marks the journal as reviewed, never as reapproved.

The journal itself may contain sensitive **output paths**. Never upload it
or commit it to Git. Job history isn't a verified receipt. The current
user and operating system are still responsible for protecting local
folders; interrupted writes have residual race and crash risks.


## v1.3 — Real per-item polling and cooperative cancel

The local stdio MCP server now exposes **17 tools**. For a long-running batch,
call `start_submission_job(notice_text, assignments, execute=false,
confirm_execution=false)` to perform an ordinary **read-only dry run**. It
starts no background job by default and shows the exact paths, PDF pages and
crop choice. After the user explicitly approves that specific plan, call with
**both** `execute=true` and `confirm_execution=true` to start a worker.

The response includes a random `job_id`. Call
`get_submission_job(job_id)` to poll the *real, current* per-item state.
This is **polling**, not server-push subscriptions or streaming from a
single blocking tool. At most **one batch job** can execute at once in the
local MCP process.

Call `cancel_submission_job(job_id)` to *request* cancellation. The worker
is not forcibly interrupted while processing an individual image/PDF; it
honors the flag at safe item boundaries, then removes **new files created
by the current batch**. Poll until the terminal state is `cancelled`,
`failed` or `completed`; `cancel_requested` alone is not final.
The original inputs remain untouched. Previously existing outputs are never
overwritten.

**Safety boundaries:** job state is in-memory and exists only in the currently
running MCP server process. If the process exits/crashes, job state and
cancel controls are lost and the user must manually inspect the local folder
before retrying. The worker is not a preemptive OS sandbox. Approval flags
cannot cryptographically prove human consent; the agent must obtain real
user permission. Restarting or retrying a completed/cancelled job never
reuses the old approval or automatically re-runs an operation.

Use `prepare_submission_batch` for traditional synchronous execution when
polling/cancellation is unnecessary. Only the local Skill/MCP implementation
is affected; no institutional upload is implemented.


## v1.2: Fast JPEG pass, timing and safe retry

When a photo has an explicit maximum KB size, the encoder first tries its
highest supported JPEG quality (95). If that **already meets** the size limit,
it needs only one encode. Otherwise it retains the lower-quality binary
search and verifies the resulting output from disk. `prepare_image` returns
`encoding_attempts` and `duration_ms`; `prepare_pdf` returns
`duration_ms`. Avoid promising a percentage performance increase from a
single timing.

`prepare_submission_batch` retains its default dry-run and double-confirmation.
Its result now includes a **completed-response snapshot**, `progress`, with
`phase`, `completed_items`, `total_items`, `percent` and
`live_streaming=false`, plus `duration_ms` and per-item durations for
successful items. This is not a live progress event subscription; an MCP caller
receives it only once the request finishes.

On blocked or failed batch results, show `retry_guidance`. Never automatically
retry, reuse former user consent, overwrite previous files or guess PDF pages.
After failure, inspect the filesystem for unexpected outputs, repair the
cause, run a new dry-run and obtain user approval for the revised exact plan.

For reproducible, **synthetic-only** local measurements, run
`python scripts/benchmark_v12.py`. Its temporary fixtures are deleted;
real user files are never measured by this script.



**v1.0 안정화:** The 14 MCP tools remain compatible with v0.9. File paths must
be canonical and may not pass through symlinked intermediate directories or
`..` aliases. A file with an unrecognized extension or unreadable image/PDF
structure must **never** be treated as technically compliant. After preparing a
batch, independently re-inspect final files; keep all institutional/content
checks manual. The new `tests/test_release_v10.py` exercises a real stdio MCP
session from notice parsing to offline reporting using synthetic files.
Read `SECURITY.md` at repository root for the explicit threat boundaries.


Use the bundled Python CLI to prepare **local** submission files. Read the user's file paths and institution's exact requirements before executing. The tool never uploads files and never replaces an existing file.

## v1.1: Confirm real local MCP connectivity

After local installation, run the `probe` command to connect to the actual
stdio MCP server and call only `parse_submission_rules` on synthetic example
text. The diagnostic **does not open the user's documents** and never changes
a client configuration. To inspect both installation and handshake in one
command, run:

```bash
python3 scripts/setup_mcp.py status --allowed-dir "/absolute/path/to/submission-files"
```

For separate checks use `doctor` for Python/dependency diagnostics and
`probe` for live local MCP handshake. `status=pass` proves that this
computer can start the MCP subprocess, *not* that the user's Codex/Cursor/Claude
client has connected. If `needs_attention`, show the returned `code`,
`fix` and any failing `doctor.checks`; do not guess, auto-write client
settings, or ask the user to share real documents as a diagnostic.

## v0.9: Guided local installation

For first-time installation, prefer the standard-library setup helper (Python
3.11+) rather than installing packages into the system Python:

```bash
python3 scripts/setup_mcp.py install --allowed-dir "/absolute/path/to/submission-files"
python3 scripts/setup_mcp.py doctor --allowed-dir "/absolute/path/to/submission-files"
python3 scripts/setup_mcp.py config --client codex --allowed-dir "/absolute/path/to/submission-files"
```

Use an existing, real, canonical directory. The installer creates a private
`.venv` in the skill folder and installs pinned-range dependencies there. It
does **not** modify the Codex, Cursor, or Claude Desktop MCP configuration.
The `config` command prints an escaped snippet to copy into the appropriate
client settings; choose `--client cursor` or `--client claude-desktop` for
JSON. Never automatically copy/edit another application's existing config,
expose all of the user's home directory or launch the server as a remote
network endpoint. `doctor` performs read-only local environment checks and
reports specific remediation items. A successful doctor cannot guarantee that
a particular AI client has connected to the MCP server.

For installation walkthrough and troubleshooting see `QUICKSTART.md`.
The installer may access the internet only when an individual user
explicitly runs the `install` command to obtain Python dependencies.

## CLI-only setup (alternative)

From this skill directory (`.agents/skills/jechulok-submission/`):

```bash
python -m pip install -r requirements.txt
python scripts/jechulok.py --help
```

If dependencies are unavailable, explain that setup failed; do not claim that a file was processed. Processing works offline after installation.

## MCP integration (v0.9, optional)

An MCP-capable agent may call fourteen local stdio tools. The original tools include `parse_submission_rules`, `prepare_from_requirements`, `check_file`,
`prepare_image`, `extract_pdf_pages`, `verify_submission`; multi-file tools are described below. If the JeChulOK MCP
server is connected, prefer these tools over shell commands. See [MCP.md](MCP.md)
for installation, allowed-directory settings and the security boundary.

```bash
python -m pip install -r requirements-mcp.txt
python scripts/mcp_server.py  # launched by your MCP host; not a network server
```

If the MCP server is unavailable, continue using the existing CLI. Do **not**
claim that simply cloning GitHub attaches the MCP server to ChatGPT or Codex.
The MCP server only accepts local paths within the configured allowed folders,
never overwrites files, and requires `crop_approved=true` for center-crop jobs.
Always run `verify_submission` on the produced file. A `pass` checks only the
user's explicitly provided technical requirements.

## v0.4: Long notices and multiple files

Use `analyze_submission_notice` when a recruitment announcement names separate
file items such as “증명사진: JPG 300×400px 500KB 이하” and
“이력서: PDF 5MB 이하, 최대 3페이지”. The deterministic parser returns
`item_01`, `item_02` etc., original line numbers and text evidence.

If any item is ambiguous, any common/unassigned format or numeric rule exists,
or the announcement does not label items explicitly, **stop and ask for review**.
No automatic matching of source files to labels. This is not semantic document
understanding, OCR, or an institutional policy lookup.

Then call `prepare_submission_batch` with one **explicit**
`{item_id,input_path,output_path,pages_to_extract}` mapping per recognized item.
First call with `execute=false` (the default) to see the full plan. Only after
the user explicitly approves the mapped plan should an agent call it with
`execute=true, confirm_execution=true`.

- JPG operations always create a separate JPG, preserving the original.
- PDF operations need user-chosen pages for extraction. If the existing PDF
  already meets its limits, omit `pages_to_extract` **and** `output_path` to
  verify it unchanged. A maximum-page limit never selects pages automatically.
- Central cropping needs `crop_approved=true` and real user permission.
- All paths must be under `JECHULOK_ALLOWED_DIRS`; outputs cannot overwrite
  originals, existing files, or each other.
- On a batch processing failure, newly completed batch outputs are rolled back.
  Do not claim partial completion as a success.
- Always report technical limitations, check files before sending, and never
  claim actual institutional acceptance.

CLI read-only analysis is also available:

```bash
python scripts/jechulok.py parse-notice --text '- 증명사진: JPG 300×400px 500KB 이하'
```

## v0.5: Suggest local candidate files, never auto-assign

When the user provides an authorized local directory containing possible
submission files, call `suggest_submission_files(notice_text, directory_path)`.
This tool is **read only** and scans only immediate files, up to 250 directory
entries. It ranks compatible filename/extension hints for each named item but
never inspects document contents, determines suitability, selects the file or
executes conversions.

Show the suggestions and unresolved items. Ask the user to review each
`item_id` → `input_path` selection before constructing an assignment. If a
filename suggests a resume, this is not proof the file is a resume.
`needs_review`, `no_candidates`, or `truncated=true` must be stated.
Symlinks and paths outside `JECHULOK_ALLOWED_DIRS` are not accepted. Do not
treat suggestions as permission to upload, edit, or submit data.

Then retain the v0.4 rule: obtain the dry-run plan from
`prepare_submission_batch(execute=false)` and require real user approval of
the exact paths and PDF page selections before the double-confirmed execution.
Never call execution immediately after suggestion without this separate review.

## v0.6: Read-only output naming and technical status tracking

Once the user **manually confirms** each item-to-input mapping, call
`suggest_submission_output_paths(notice_text, assignments, output_directory)`
to propose new output filenames. This tool does not generate, reserve, or
approve files. Report any missing PDF page selection as a manual decision.
Existing compliant PDFs can be checked without generating copies.

Present the suggested paths to the user for review. The human-approved mapping
must then pass `prepare_submission_batch(execute=false)` preflight.
Only after separately approving that exact plan may the agent execute with
both `execute=true` and `confirm_execution=true`.

Read `summary.items[].technical_status` to report per-item progress:
`planned`, `awaiting_confirmation`, `blocked`, `rolled_back`,
`not_executed`, or `verified`. A `verified` result checks **only technical
file constraints**. Never equate this with a real submission or an institution's
acceptance. Do not treat preview proposals as approved final paths.

## v0.7: Separate review from technical success

Use `review_submission_plan` to show an exact, read-only preflight and
specific unresolved approvals or repair actions. Never infer permission from
`awaiting_human_approval`: this means the work is NOT approved yet. Confirm
the source files, output paths, PDF page range and crop permission with the
actual user, then obtain a separate explicit instruction to run
`prepare_submission_batch(execute=true, confirm_execution=true)`.

After files are produced, use `verify_submission_package` with the original
notice and each final `{item_id, file_path}` to independently re-open and
recheck them. A previous `pass` result or matching filename is not evidence
that a now-modified file will still pass. If any `remediation` item appears,
show the repair guidance and stop before actual submission.

Even `technical_pass` leaves every manual checklist item unchecked.
Never claim `ready_to_submit`, accepted/received by an institution, correct
photo composition, digital signature preservation, or validated document
content. No actual form submission is implemented.

## v0.8: Prioritized next question and private offline report

Prefer `guide_submission_workflow` when the user needs a conversational
walkthrough rather than a raw MCP tool protocol. It returns a single,
prioritized `question` and `next_action` using only the current notice,
the user-confirmed file mapping and (when supplied) the final files.
Never treat `awaiting_human_approval` as approval, and never select source
files or PDF pages without human input. Only after real approval of the
**exact** dry-run may you execute with the previous double-confirmed batch
call. The guided tool **never changes files**.

When the user wants an offline record, call
`create_submission_html_report(notice_text, files, output_path)` to preview
the current final-file inspection without writing. Show that preview and the
planned `.html` output path to the user. Only with explicit permission save
via `execute=true, confirm_execution=true`. The new HTML is local-only and
cannot overwrite an existing file. It includes basenames, technical statuses,
repair hints and unchecked human review steps, never file contents, full
filesystem paths or upload links. It may contain personal information inside
filenames. Do not send it to a server.

Even if `technical_pass` is reported, do not claim submitted/accepted.
Institution policies, applicant identity, image composition, PDF signature
validity and receipt remain manually checked.

## Decision flow

1. **Understand the specification.** Ask for or use explicit pixel dimensions, max size, allowed file type, and PDF page limits. Don't invent rules from the user's institution. `--max-kb` uses KiB (1 KiB = 1,024 bytes).
2. **Inspect first.** Run `check` and parse JSON stdout. `pass` means **specified machine-checkable conditions** matched; it does not mean admission or submission success. `info` means no limits were requested. `fail` means a condition was violated. `unverified` means a requested property could not be checked.
3. **Select a supported operation:** `prepare-image` produces JPG from JPG/PNG/WebP, or `prepare-pdf` extracts requested pages from an unencrypted PDF <=20 MiB. HEIC, AVIF, OCR, office files, signable PDFs, PDF recompression, and edits to existing PDF text are not supported by this skill version.
4. **Keep content intact unless permitted.** Use `--mode contain` by default (white padding, no cropping). Only use `--mode cover` if the user explicitly authorizes center cropping. Explain that converting transparent images to JPG replaces transparency with white.
5. **Generate a new output.** The CLI refuses to overwrite existing files or output onto the input. If the destination exists, choose another new name.
6. **Recheck and inspect result JSON.** Both preparation commands internally re-parse and verify the new output. For the final response, report the returned output path, exact measured bytes/pixels/pages, and what remains unverified. Never report completion when exit code != 0 or `status` is not `pass`.
7. **Warn about limitations.** Original PDF signatures, attachments, interactive forms and bookmarks may not survive page extraction. A matching file format/pixel size/KB limit does not validate an applicant photo's background, face positioning, or institution-specific requirements.

## Commands

```bash
# Check a candidate photo (does not modify it).
python scripts/jechulok.py check --input /path/photo.png --format jpg --width 300 --height 400 --max-kb 500

# Create a separate JPG, preserving the whole photo with white padding by default.
python scripts/jechulok.py prepare-image --input /path/photo.png --output /path/photo-ready.jpg --width 300 --height 400 --max-kb 500 --mode contain

# Crop the center only after explicit authorization.
python scripts/jechulok.py prepare-image --input /path/photo.png --output /path/photo-cropped.jpg --width 300 --height 400 --max-kb 500 --mode cover

# Verify original PDF length and a size limit.
python scripts/jechulok.py check --input /path/portfolio.pdf --format pdf --max-kb 10240 --max-pages 8

# Extract pages 2-4 and 7, in that order. Output is new, not overwritten.
python scripts/jechulok.py prepare-pdf --input /path/portfolio.pdf --output /path/portfolio-selected.pdf --pages 2-4,7 --max-pages 4
```

## Tool contract

- **JSON on stdout.** The CLI emits one JSON object. `check` returns `status`, `file`, `checks`, `limitations`. `prepare-*` returns `status`, `input`, `output`, `report`, `warning`.
- **Exit codes:** `0` = success or informational check; `1` = processing error; `2` = failed rule; `3` = unverified required property.
- **Paths:** Use user-approved local paths; quote any shell paths and do not pass untrusted text as a shell program. Default output is `<stem>-jechulok.jpg` or `<stem>-jechulok.pdf` next to the input. Never silently overwrite.
- **Resource limits:** input up to 50 MiB, PDFs read/modified up to 20 MiB, output up to 50 MiB, image output <=24 million pixels, PDF extract up to 300 pages.
- **Security:** Process third-party images/PDFs as untrusted. Dependencies must be installed from trusted repositories, and local path access should stay inside the user-authorized workspace.

See [CONTRACT.md](references/CONTRACT.md) for detailed invariants and unsupported features.
