# JeChulOK CLI v0.1 contract

## Design intent

This is an independently implemented Python CLI for AI agents, **not** a wrapper around the deployed JeChulOK website. The website currently runs separate client-side JavaScript code. Do not claim byte-for-byte equivalence or a shared core library. Neither the CLI nor the image/PDF logic connects to external networks during processing.

## Operations

- `check` sniffs a file signature, compares known extension, size, image pixels, or PDF page count against explicit rules. It never modifies files. `status: "info"` is not a compliance guarantee.
- `prepare-image` reads JPG/PNG/WebP, applies EXIF orientation, converts to RGB JPG, scales to exact dimensions and encodes under an optional byte limit. `contain` pads white without discarding image regions; `cover` center-crops. It writes a new output **only after** finding an encoding that meets the user-specified size. Then it reopens the file and checks format/pixels/size.
- `prepare-pdf` reads an unencrypted PDF, uses 1-based ranges like `1-3,5`, deduplicates while preserving the user-requested order, copies selected pages to a new PDF, and verifies actual output page count and optional file-size limit. It may change PDF structure or strip functionality.

## Status meanings

| status | interpretation |
|---|---|
| `pass` | All requested technical conditions were verifiably met. **Not** proof of institutional acceptance. |
| `fail` | At least one requested condition failed or file header is unknown/mismatched. |
| `unverified` | Cannot verify a requested property, for example pages of encrypted PDF. |
| `info` | File information only; no specific requirements were supplied. |
| `error` | Command could not be executed or output could not be created. |

Rule checks include `file_signature`, `extension_matches_content`, `format`, `max_kb`, `width`, `height`, and `max_pages`. `max_kb` is kibibytes (1,024 B each); check downstream institution definitions for decimal kB ambiguity.

## Invariants and limitations

- User input file is never changed. Output uses exclusive creation (`xb`) and refuses existing files, including symlinks.
- Input over 50 MiB is refused. PDF page reading/extraction over 20 MiB is refused/unverified. A maximum of 300 PDF pages can be extracted in a single operation.
- The tool does not guarantee malicious/corrupt document safety beyond the chosen parsing libraries. Run inside a sandbox when analyzing unknown files.
- PDF extraction does not reliably preserve signing, forms, attachments, bookmark structures, annotations, or embedded document-level metadata. Inspect the result visually if those matter.
- Photo requirements about face position, dimensions in centimeters, DPI, studio backgrounds and institution acceptance are **not** checked.
- For images, sharp details may be softened by resizing, white padding is added in `contain`, and alpha is flattened to white. Preserve originals.
- PDF compression and Office document conversion are not available in v0.1. HEIC/AVIF are identified by headers but not decoded or converted.
- JSON may contain local file paths. Avoid uploading logs if paths are sensitive.

## Maintenance

Run `python -m unittest discover -s tests -v` in the skill directory before publishing changes. The GitHub workflow rechecks the same cases on every push and pull request. For future website/CLI parity, extract and test a common algorithm library rather than asserting that the separate implementations are equivalent.
