# JeChulOK v1.9 — Independently labelled real-notice evaluation

This version provides the **local evaluation machinery** for licensed or
otherwise authorized real submission notices. **No real-world notice dataset
was available or included**, and no real-world accuracy is claimed.

## Data collection and privacy

Create a private dataset under the Git-ignored directory
.agents/skills/jechulok-submission/private-evaluation/ .
Do not commit, share or upload the notice corpus. Use only notices for which
you are legally entitled to copy, process and label the text. Publicly
viewable does not automatically mean redistributable.

Before adding a notice, a human must remove all applicant-specific data,
contact information, identifiers, authentication tokens, addresses and other
personal or confidential content. Prefer copying **only the relevant
technical submission-rule paragraph** rather than a full notice. A limited
local scan rejects obvious phone numbers, emails and Korean resident numbers;
it **cannot** certify that a document contains no personal information.
Ensure the review and permissions flags truthfully reflect human review.
Never upload this dataset into public CI, issue trackers or pull requests.

Two different human reviewers independently annotate the *same* notice
before seeing parser output. Reviewer IDs should be neutral pseudonyms.
The third reviewer may resolve disagreements with a reason and an
independently supplied adjudication label. No user approval is inferred
from these labels.

## JSONL corpus schema

Each line contains **one JSON object** with:

- id: unique non-identifying slug (letters, numbers, underscores, hyphens)
- notice: manually reviewed and minimized technical requirement text
- rights: an object with basis (public_domain, open_license, permission or
  authorized_internal) and confirmed=true
- privacy_reviewed: true after human review
- labels: exactly two independent assessments, each with reviewer, decision
  (parsed or needs_review) and items
- optional adjudication: reason and third distinct reviewer label, permitted
  only when the original two disagree

Each item has category (photo, resume, cover_letter, graduation, employment,
transcript, portfolio or certificate), and rules. Allowed rule fields are
expected_format, max_kb, width, height and max_pages. Units are KiB-style
kilobytes for max_kb, exact pixels for width/height, integer pages for max_pages.
The human-gold items of a needs_review assessment must be an empty list:
ambiguous conditions are **never** an executable task.

See the committed, fully invented public example:
tests/fixtures/v19_example_synthetic.jsonl. Never replace it with genuine
notice data.

## Run (local computer only)

After installing requirements-mcp.txt:

    cd .agents/skills/jechulok-submission
    python scripts/evaluate_real_v19.py private-evaluation/notices.notice-eval-private.jsonl --strict

The tool validates the schema, size, authorization attestations, privacy
review flags, duplicated notices, reviewer identity separation, and
adjudication requirements. On invalid input it emits only a generic error
category and line number where appropriate, not the raw notice.
With --strict, any unresolved disagreement results in a nonzero exit code.

The program **does not use the network, call a remote model, write generated
documents, or edit the corpus**. Standard output is aggregate JSON only:
it never prints the case IDs, reviewer IDs, notice text, input path or
per-case raw output. Avoid keeping these numbers on public systems unless
the corpus terms and consent permit sharing even aggregate statistics.

## Metric definitions

Gold labels are frozen by independent human reviewers, never inferred from
the parser being evaluated. Disagreements are excluded until third-party
adjudication. Metrics apply only to **resolved cases**.

- Independent reviewer agreement rate = initially agreeing cases / all cases
- Gold field-value precision = true-positive (category, field, value)
  tokens / all predicted tokens on gold-parsed cases
- Gold field-value recall = true-positive tokens / all gold tokens
- Constraint omission rate = false-negative gold tokens / all gold tokens
- Wrong-constraint rate = false-positive predicted tokens / all predicted
  tokens on gold-parsed cases
- Exact notice match rate = parsed cases whose complete item set and
  field values match gold / all gold-parsed cases
- Unsafe accept rate = gold-needs_review notices incorrectly marked parsed /
  all gold-needs_review notices
- False block rate = gold-parsed notices not marked parsed /
  all gold-parsed notices

Wrong field *values* count as one missed truth and one incorrect prediction;
this is intended, so omission and wrong-constraint rates can both increase.
An ambiguous notice is **never** treated as safe to process merely because
some fields were extracted. Counts and error types are recorded without
exposing source text. Zero-denominator metrics are null, not 0%.
These are descriptive **sample** measures, NOT population performance
estimates unless the collection method supports that inference.

## Continuous integration and evidence

CI includes unit tests of the real-data evaluator built from invented
examples only, on Windows, macOS and Ubuntu with Python 3.11 / 3.13.
CI executes the public sample JSONL and uploads an **aggregate synthetic
example report**, never actual user content.

Real notice collection, double annotation and external validation remain
future evidence-gathering steps and cannot be simulated by this release.
For fair comparisons, label notices without showing the model result,
keep the final test set separate from development examples, document the
sampling procedure, and compare versions against the same frozen gold.
