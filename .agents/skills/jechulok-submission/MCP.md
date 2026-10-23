# 제출OK MCP v0.4 — local stdio server

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

