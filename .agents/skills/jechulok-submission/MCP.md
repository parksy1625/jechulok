# 제출OK MCP v1.1 — local stdio server

**Purpose:** Let an MCP-capable AI assistant inspect files, prepare compliant JPG photos, extract PDF pages, and independently verify the output. Uses the same Python processing functions as the v0.1 CLI. **It does not upload files or expose an HTTP endpoint.** This is an independent Python implementation, not the JavaScript web site's engine.

## Install

Python 3.11+:

```bash
cd .agents/skills/jechulok-submission
python -m pip install -r requirements-mcp.txt
python scripts/mcp_server.py
```

The last command intentionally waits for an MCP client on **stdio**; no text appears in the shell. Use an MCP host to launch it instead of launching it manually.

## Connect from Codex

Edit `~/.codex/config.toml` (replace both absolute paths below with paths on **your computer**):

```toml
[mcp_servers.jechulok]
command = "/absolute/path/to/python"
args = ["/absolute/path/to/jechulok/.agents/skills/jechulok-submission/scripts/mcp_server.py"]
env = { JECHULOK_ALLOWED_DIRS = "/absolute/path/to/workspace" }
```

Alternatively use the Codex CLI to register a local stdio MCP server if your installed CLI supports the option. Verify with `codex mcp list`.

Important: The default allowed directory is the MCP process's working directory, which depends on the host. Set `JECHULOK_ALLOWED_DIRS` explicitly for predictable behavior. Paths supplied to tools must exist **within** an allowed directory. Multiple roots are separated by the OS path delimiter (`:` on macOS/Linux, `;` on Windows). Neither symlinks nor output overwrites are supported.

## Exposed MCP tools

| Tool | Purpose | Mutates files? |
|---|---|---|
| `check_file` | Detect real file signature, bytes, image pixels or PDF pages and check specified conditions | No |
| `prepare_image` | JPG/PNG/WebP → new JPG, exact pixels, optional max KB | Creates new file |
| `extract_pdf_pages` | Create a new PDF with 1-based range like `2-4,7` | Creates new file |
| `verify_submission` | Reopen output and verify **at least one** explicit condition | No |
| `parse_submission_rules` | Extract exact technical conditions and flag uncertain ones | No |
| `prepare_from_requirements` | Prepare a JPG or explicit PDF pages and reverify technical output | Creates a new file |
| `analyze_submission_notice` | Split explicit named file items and keep their source-line evidence | No |
| `prepare_submission_batch` | Preflight explicit item-to-file mappings and optionally process with double confirmation | Only with execution approval |
| `suggest_submission_files` | Read-only hints based on local filenames and compatible extensions, never auto-assigns | No |
| `suggest_submission_output_paths` | Suggest collision-free output filenames for explicitly reviewed mappings | No |
| `review_submission_plan` | Re-check a dry run, show approvals and reason-specific repair steps | No |
| `verify_submission_package` | Re-open final files and validate technical constraints with pending human checklist | No |
| `guide_submission_workflow` | Return one prioritized, concise next user question without automatic approval | No |
| `create_submission_html_report` | Preview or explicitly save a standalone offline HTML technical report | Only with separate dual approval |

All tool inputs and outputs refer to **local paths on the MCP server host**, not uploads from ChatGPT or remote URLs. `prepare_image` defaults to `mode="contain"` (white margins, no crop). `mode="cover"` requires the user's explicit permission and `crop_approved=true`.

`max_kb` is measured in **KiB**: 1 KB = 1,024 bytes. The original input is never overwritten. Each tool returns a structured object; `status: "pass"` represents only the explicit technical rules, not successful acceptance by an institution. `status: "info"`, `"unverified"` or `"error"` must **never** be called a pass.

### Recommended agent flow

1. Read the exact submission conditions provided by the user; do not infer institution-specific rules.
2. `check_file(input_path, expected_format="jpg", width=300, height=400, max_kb=500)`.
3. If not `pass`, call `prepare_image` with a new output path (or `extract_pdf_pages` for PDF). Only crop if explicitly approved.
4. `verify_submission` with **the same rules** on the generated file.
5. Return output path, checked conditions and warnings. If unverified, explain which requirement needs manual validation.

### Boundaries and limitations

- Inputs up to 50 MiB, PDF extraction up to 20 MiB; PDF selection maximum 300 pages.
- JPG / PNG / WebP input for image preparation; conversion to HEIC / AVIF or OCR is unavailable.
- PDF extraction may strip interactive forms, bookmarks, attachments or valid digital signatures.
- Portrait positioning, white background compliance, dimensions expressed in centimeters, content accuracy and website-specific acceptance are **not** verified.
- This is a local-tool integration. **Not** a remotely reachable ChatGPT connector or an automatically installed GitHub Skill.
- Host applications determine whether and when to approve local filesystem access. Limit `JECHULOK_ALLOWED_DIRS` to folders you intend the agent to use.

## Tests

```bash
python -m unittest discover -s tests -v
```

The repository's GitHub Actions checks both the CLI and the MCP layer on Python 3.11 and 3.13.

Official MCP SDK: https://py.sdk.modelcontextprotocol.io/


## v0.3: Korean submission instructions

`parse_submission_rules(requirements_text=...)` returns a structured `rules` object with format, maximum KB, exact pixel width/height and maximum PDF pages, as well as `issues` and `unsupported_conditions`.

`prepare_from_requirements(input_path, output_path, requirements_text, pages_to_extract=None, mode='contain', crop_approved=False)` refuses to edit when any rule is ambiguous or unverified. For PDF, the maximum number of pages does NOT indicate which pages to discard: supply `pages_to_extract` from the user's explicit instructions. For JPG, `mode='cover'` requires `crop_approved=true` and actual user authorization. Both new and existing tools respect `JECHULOK_ALLOWED_DIRS`, never overwrite existing files and never upload data.

This is deterministic rule parsing, NOT a language model, institution policy database or OCR. Multiple allowed formats, cm/mm, missing pixel units, strict '미만', portrait/background requirements and signatures require manual review. Size values use 1024-based KiB/MiB. An output `pass` attests only to verified technical constraints.

## v0.4 — Long notice & batch preparation

First call `analyze_submission_notice(notice_text)`, which only understands
explicitly labeled lines, e.g.:

```text
- 증명사진: JPG 300×400px 500KB 이하
- 이력서: PDF 5MB 이하, 최대 3페이지
```

It returns `item_01` (photo) and `item_02` (resume), with source line and
evidence, parsed technical conditions and unresolved conditions. Whole-document
`needs_review` blocks batch execution, including common conditions that cannot
be attributed to a named file. This parser does NOT automatically split PDFs
into documents, read scans, infer which local file is a resume, or infer which
pages should be discarded. It supports at most 12 recognized items and
20,000 notice characters.

Provide explicit user-reviewed mappings:

```json
{
  "notice_text": "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지",
  "assignments": [
    {"item_id": "item_01", "input_path": "/workspace/photo.png", "output_path": "/workspace/ready.jpg"},
    {"item_id": "item_02", "input_path": "/workspace/resume.pdf",
     "output_path": "/workspace/resume-selected.pdf", "pages_to_extract": "1-3"}
  ],
  "execute": false,
  "confirm_execution": false
}
```

1. Default: `execute=false` returns `status=planned` **without writing files**.
2. The user must explicitly approve the mapping and final page selections.
3. Only then `execute=true, confirm_execution=true` may create outputs.
4. All assignments are preflighted together; ambiguous or missing items block
   the entire batch. An operation failure removes outputs successfully created
   during the same batch.
5. Unchanged compliant PDFs can be verified with neither
   `pages_to_extract` nor `output_path`; such a step does not generate a copy.
6. Every new result is reopened and checked against its own technical rules.
   The tool cannot verify file contents, face positioning, e-signature validity,
   or institutional submission success.

CLI (analysis only):

```bash
python scripts/jechulok.py parse-notice --text $'- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지'
```



## v0.5 — Read-only local file suggestions

After `analyze_submission_notice`, call `suggest_submission_files` with an
**explicitly authorized directory** and the original notice:

```json
{
  "notice_text": "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지",
  "directory_path": "/workspace/submission"
}
```

- Only the top-level files inside the requested directory are considered (no recursion).
- At most 250 immediate directory entries are inspected, and the top five
  compatible filenames are shown per notice item. `truncated=true` means
  additional files may exist outside the inspected set.
- Matching uses **filenames and extensions only**, not file content, OCR or
  machine learning. A filename hint is never proof that a file is the right document.
- Files and subdirectories accessed through symlinks are rejected or skipped.
  The directory must be within `JECHULOK_ALLOWED_DIRS`.
- The result is `suggestions_only`, `no_candidates` or `needs_review`;
  none authorizes writing a file. Review even high-priority hints manually.
- Only after reviewing the paths and item IDs, explicitly pass assignments
  to `prepare_submission_batch`. First obtain its dry-run plan, and execute
  only after approval with both execution flags. Page selection remains manual.

The MCP server does not upload documents, scan recursively, submit forms, or
infer successful acceptance.


## v0.6 — Output-name proposals and technical progress

After the user confirms the item-to-input mappings, call
`suggest_submission_output_paths` with their original notice, reviewed file
paths, and an existing authorized output directory:

```json
{
  "notice_text": "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지",
  "assignments": [
    {"item_id":"item_01","input_path":"/workspace/photo.png"},
    {"item_id":"item_02","input_path":"/workspace/resume.pdf","pages_to_extract":"1-3"}
  ],
  "output_directory":"/workspace/ready"
}
```

This call **does not create or reserve any files**. It uses fixed category-based
names such as `제출용_증명사진.jpg` and `제출용_이력서.pdf` and appends
`_2`, `_3`, etc. when names already exist. These are only suggestions; a
different process may create the same name before execution.

A PDF already satisfying explicitly stated conditions is labeled
`verify_existing` and receives no output filename. A PDF that fails but has
no user-selected page range is labeled `select_pdf_pages` and blocks
preparation until the user selects pages. It never infers discarded pages.

**Next steps:** Let the user inspect each proposed path and choose/approve it.
Copy the explicitly approved paths into `prepare_submission_batch`. Call the
batch tool once with default `execute=false` to review the actual plan.
Only after explicit approval of this exact dry run use both
`execute=true` and `confirm_execution=true` to write files.

The batch result now includes `summary` with:
- `technically_verified`: successful machine checks, *not submission success*
- `generated_files` / `unchanged_verified`: successful new outputs vs.
  verification of original PDFs
- `not_verified`, `blocked_items`, and per-item `technical_status`
- `manual_review_required=true` and
  `institutional_submission_confirmed=false` unconditionally

Statuses `planned`, `awaiting_confirmation`, `blocked`,
`rolled_back`, and `not_executed` are not success. All files stay local.


## v0.7 — Human review, remediation and final technical checklist

**New read-only tools:** `review_submission_plan` and
`verify_submission_package`. There are now 12 MCP tools total.

### Before execution

After confirming actual input/output paths with the user, call
`review_submission_plan(notice_text, assignments)` using the same exact
assignments that would be used for `prepare_submission_batch`. It returns
a dry-run plan, unresolved issues, a machine-generated remediation guide,
and five **unchecked manual approval items**:

- Confirm each requirement against the original announcement
- Confirm actual input/output paths and the correct document content
- For PDFs, check user-selected pages and potential signature/form loss
- If cropping photos, obtain explicit permission
- Review the *exact* final dry-run plan and approve execution

`status=awaiting_human_approval` means the technical preflight succeeded;
**it is NOT approval** and does not authorize any file changes. Missing or
ambiguous items return `needs_review` and human-action repair suggestions.
Do not set `execute=true` or `confirm_execution=true` because of any
status returned by a read-only tool. The user must explicitly authorize
execution of the specific plan separately.

The existing `prepare_submission_batch` result now also includes
`remediation` and `approval_checklist`. The tool retains its original
dry-run default, explicit double execution flags and rollback protections.

### Just before submitting

Use `verify_submission_package` with the original notice and **exact final
file paths**, even if those files were previously marked `verified`:

```json
{
  "notice_text": "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지",
  "files": [
    {"item_id":"item_01","file_path":"/workspace/ready-photo.jpg"},
    {"item_id":"item_02","file_path":"/workspace/ready-resume.pdf"}
  ]
}
```

Each final file is opened again, its real signature, extension, size,
dimensions or page count evaluated against the notice, and mismatches mapped
to non-executable repair guidance. Ambiguous notices, missing/duplicate item
IDs, disallowed paths and unreadable files never receive a technical pass.

**Critical:** `status=technical_pass` means *only the explicitly stated
machine-checkable requirements* passed at inspection time. Even with all
items passing, `ready_to_submit=false`,
`institutional_submission_confirmed=false`, and every human checklist item
remains `verified=false`. The tool does not know whether an image is a
compliant portrait, whether PDFs retain signatures, whether the document
content is correct, or whether an institution accepted any upload.

No photos or PDFs are uploaded, modified, submitted or stored by these two
tools. Only authorized local files are read.


## v0.8 — One-question guided flow and offline HTML report

MCP now has **14 tools**. Use `guide_submission_workflow` to guide the
conversation through one decision at a time (it does not execute anything):

```json
{
  "notice_text": "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지",
  "assignments": []
}
```

The tool prioritizes:
1. Ambiguous/unassigned notice requirements (`clarify_notice`)
2. First unmapped required file (`choose_source`)
3. Technical problems with confirmed mappings (`fix_plan`)
4. Approval of the exact, fully specified dry-run plan (`approve_exact_plan`)
5. After final files exist, their current technical errors (`fix_final_files`)
6. Remaining manual content/acceptance checks (`check_original_content`)

The tool returns `question`, `next_action` and a short status; it never
records human consent. The agent must get **separate, real approval** for any
file-changing execution. `final_files` is optional and switches the workflow
to re-checking the actual final files. Do not infer that previously verified
files are still unchanged.

For a local printable technical report, call
`create_submission_html_report(notice_text, files, output_path)` with the
original notice and the confirmed **final** item-to-file paths:

```json
{
  "notice_text": "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지",
  "files": [
    {"item_id":"item_01","file_path":"/workspace/ready.jpg"},
    {"item_id":"item_02","file_path":"/workspace/ready.pdf"}
  ],
  "output_path": "/workspace/submission-check.html",
  "execute": false,
  "confirm_execution": false
}
```

- Default is `status=preview`: checks files again and returns a summary,
  **but writes nothing**. `execute=true` alone returns
  `needs_confirmation` and still writes nothing.
- Saving requires BOTH `execute=true` and `confirm_execution=true`,
  plus actual human authorization of the exact output path.
- Only a **new** `.html` path beneath `JECHULOK_ALLOWED_DIRS` is allowed;
  an existing file cannot be overwritten.
- Static UTF-8 HTML only; content security policy prevents scripts and external
  assets, and displayed text is HTML-escaped. The report includes item labels,
  final **basenames**, observed file bytes, technical status, and unchecked
  manual-review items. It does not embed file contents, full absolute paths,
  photos, PDF pages, or any external URLs.
- A report may still be created if technical verification fails, but is
  prominently labeled as such. A successful technical inspection is never
  equivalent to having submitted documents or having them accepted.
- Reports contain potentially identifying filenames. Keep generated HTML
  within authorized private local folders; never upload it automatically.

The HTML is a **snapshot**, not a live monitor. Re-run technical verification
after any modification of the final files. Neither new tool uploads or submits.


## v0.9 — Installation, configuration and local diagnostics

**All existing 14 MCP tools remain unchanged.** This release improves the
local setup lifecycle, not the file-processing permissions.

The standard-library setup helper, `scripts/setup_mcp.py`, provides:

```bash
# Only this command installs packages. Explicit invocation required.
python3 scripts/setup_mcp.py install --allowed-dir "/absolute/path/to/documents"

# Read-only environment diagnostics (no file output).
python3 scripts/setup_mcp.py doctor --allowed-dir "/absolute/path/to/documents"

# Print a Codex TOML snippet to copy into ~/.codex/config.toml.
python3 scripts/setup_mcp.py config --client codex --allowed-dir "/absolute/path/to/documents"

# Print JSON for a Cursor or Claude Desktop MCP configuration.
python3 scripts/setup_mcp.py config --client cursor --allowed-dir "/absolute/path/to/documents"
python3 scripts/setup_mcp.py config --client claude-desktop --allowed-dir "/absolute/path/to/documents"
```

The `install` command creates/reuses this skill's `.venv` and calls its
own Python's pip using `requirements-mcp.txt`. The `config` tool uses the
**virtualenv executable path as typed**, including if it is a symlink to
another binary. It never changes Codex/Cursor/Claude settings, silently grants
permissions, copies local files, uploads anything or uses a remote transport.

The `doctor` status is `pass` only if Python >= 3.11, the local stdio
server and environment Python exist, the allowed directory appears accessible,
and Pillow/pypdf/MCP SDK imports succeed in the selected virtualenv.
It checks the OS permissions heuristically and cannot guarantee an active
client connection. `needs_setup` reports individual checks with actionable
`fix` messages. No files are altered by the doctor.

Set `JECHULOK_ALLOWED_DIRS` to the **narrowest existing working directory**
required. The startup and setup scripts reject noncanonical aliases in the
setup-provided work directory. Use only absolute paths. Treat any generated
configuration snippet as sensitive local information if a directory name
reveals identity. MCP remains stdio only, with no exposed network API.

**Important:** the installed MCP server is not automatically available in
hosted cloud agents. A local-capable client must start it in the same filesystem
environment where the documents exist. Consult `QUICKSTART.md` for step-by-step
instructions and example prompts.


## v1.0 stable — Integration and security checks

Existing 14 MCP tools and their request contracts remain available. The
v1.0 release is a **stability pass**, not a submission/auto-upload feature.

Key changes:
- MCP file access now rejects `..` path aliases and intermediate symlink
  directories, even if they resolve inside an authorized root.
- Verification never reports `pass` for a recognized document whose file
  extension is unknown, or when an image/PDF integrity check reports an error.
  Such cases are `unverified`; agents must stop and request correction.
- Batch execution reauthorizes every source and destination after preflight
  and just before each operation. If authorization fails after an earlier
  item was generated, the earlier new output is rolled back.
- Real stdio client regression covers discovery, parsing, filename proposals,
  preflight, missing approval, actual file generation, final inspection,
  HTML preview and explicit HTML output approval.
- CI covers Ubuntu, macOS and Windows with Python 3.11 and 3.13 (six jobs).
  It checks dependencies, source compilation, unit/integration tests and the
  read-only setup doctor. Ubuntu/Python 3.11 additionally creates a **fresh**
  local virtualenv, installs MCP dependencies and tests a real MCP connection
  using the generated Codex TOML config.

These tests use **synthetic documents**. A machine-checkable `pass` remains
separate from content correctness, signature validity, visual requirements
and institutional receipt. See repository-root `SECURITY.md` for details.


## v1.1 — Live local connection probe and one-command status

No change to the 14 registered MCP tools or their permission boundaries.
The new standard-library `setup_mcp.py` CLI commands are **not** new MCP
tools:

```bash
# Real local stdio handshake, 14-tool discovery and synthetic rule parser.
python3 scripts/setup_mcp.py probe --allowed-dir "/absolute/path/to/submission-files"

# Doctor checks first, then handshake; combined JSON result.
python3 scripts/setup_mcp.py status --allowed-dir "/absolute/path/to/submission-files"
```

`doctor` only verifies the local runtime/dependencies. `probe` starts a
child MCP server using the installed `.venv` interpreter, discovers tools,
and invokes `parse_submission_rules` with **hard-coded synthetic text**
(`JPG 300×400px 500KB 이하`). It never selects, reads or writes user
documents, never calls any file-modifying MCP tool and never updates clients'
configuration. `status` skips the handshake if the environment checks fail.

Failure results provide machine-readable codes such as:
`venv_missing`, `server_missing`, `connection_timeout`,
`python_launch_failed`, `unexpected_probe_output`,
`tools_missing`, and `tool_call_failed`. No child stderr, document data,
absolute user-file paths or server stack traces are copied into the summary.

**Successful `probe` or `status` only confirms the server's local stdio
handshake**. It cannot guarantee a third-party AI client loaded the copied
MCP configuration, accepted permissions or can reach the same filesystem.
To confirm actual application integration, restart your MCP-capable local
client and ask it to call `parse_submission_rules` with synthetic text.

CI continues to run on Ubuntu/macOS/Windows with Python 3.11/3.13 and
performs an additional clean virtual environment install + local probe +
combined status smoke check on Ubuntu/Python 3.11.
