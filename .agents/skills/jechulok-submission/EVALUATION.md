# JeChulOK Agent Skill — Synthetic Evaluation v1.8

This is a **reproducible component regression benchmark**, not an independent
AI model benchmark and **not** evidence of accuracy on real submission notices.

## Run

From the .agents/skills/jechulok-submission directory after installing
requirements-mcp.txt, run:

    python scripts/evaluate_v18.py --check

The command prints one structured JSON document. A nonzero exit code means at
least one scenario fails or the expected fixture count is incomplete.
It operates entirely on deterministic synthetic notices and files in a
temporary directory, which is removed on exit. It does not access user
documents, call a model, send network requests, or grant file-write approval.

## Dataset and independent ground truth

The dataset consists of **100 distinct synthetically generated notice
strings**, equally divided among four component evaluations:

| Fixture family | Count | Ground truth / required outcome |
|---|---:|---|
| Explicit technical rules | 25 | Independent expected (format, max_kb, width, height, max_pages) tuples must exactly match the parser and notice must be parsed |
| Ambiguous or unsupported rules | 25 | Known unassigned/duplicate/unsupported/multi-format/conflicting rules must produce needs_review and the corresponding issue category |
| Human file choice | 25 | No implicit directory scan, opt-in candidate hints only, never auto-select or mark name-based candidates verified, one grouped question, no file writes |
| Unsafe execution attempts | 25 | Omitted confirmation, missing/wrong fingerprint, edited plan, and unapproved crop must be refused without creating files or journals |

Fixture parameters and expected decisions are defined in
[scripts/evaluate_v18.py](scripts/evaluate_v18.py). They are **not** derived
from measured outputs. The 100 notice strings span systematic variations;
they are **not** 100 independently sampled institutional notices.
The 25 candidate scenarios include purposely misleading filenames whose
contents are invalid, ensuring that hints are never falsely certified.
**They do not measure candidate ranking correctness or content relevance.**

Each family receives passed, total and pass_rate. The primary score
is passed_cases / evaluated_cases, with all counts auditable. The tests
also assert that the suite has exactly 100 **distinct notice strings**.

The following fields deliberately remain null:
- real_world_accuracy and real_notice_generalization
- candidate_semantic_accuracy
- real_user_satisfaction

The metric missing_document_selection_prompt_count = 1 describes the
single grouped question in a **static two-item synthetic fixture**.
It is not the average number of questions asked in real conversations.

## CI and audit

GitHub Actions runs the full unit/regression suite on Ubuntu, macOS and Windows,
each with Python 3.11 and 3.13. Ubuntu/Python 3.11 also runs the evaluation
as a separate check and uploads the result JSON as the
jechulok-eval-v18-synthetic artifact (30-day retention).
Source cases and ground-truth fixture oracle are version-controlled.
Failures print only synthetic case identifiers and generic descriptions.
The JSON contains no real file paths or user-uploaded content.

## Limitations and next evidence needed

This benchmark tests deterministic parser and guarded workflow behavior.
It **does not** establish that arbitrary Korean notices are correctly
understood, that filename hints point to the user's intended documents,
that PDF/image contents are valid for a particular institution, or that a
human has given consent. A plan fingerprint only compares a preview,
not proof of a user's approval or a content-integrity signature.

Next, test a legally reusable, manually labelled set of varied real notices
with independent reviewers and privacy safeguards; report precision/recall
with uncertainty and separate regression tests for discovered errors.
Never include personal documents or identifying source paths in the
open-source repository or the public evaluation artifact.


## v1.9 extension: independently reviewed local corpus

v1.8 synthetic regression remains unchanged. For empirical analysis of
licensed, manually redacted real notices, v1.9 adds a separate evaluator
documented in [REAL_EVALUATION.md](REAL_EVALUATION.md).
**No real records are bundled or were evaluated for this release.**
The CLI supports two independent human labels, third-party adjudication,
precision/recall and fail-closed assessment, and aggregate-only output.
Do not confuse its public synthetic example fixture with real-world
accuracy or expose a real corpus in GitHub CI.
