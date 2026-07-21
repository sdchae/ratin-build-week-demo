# RATIN — OpenAI Build Week Submission Draft

## 1. Project name

**RATIN — Evidence-Linked Procurement Decision Intelligence**

## 2. Tagline

Turn mixed-format procurement files into a concise decision brief with every
fact, conflict, and action linked to its exact source.

## 3. Category recommendation

**Work and Productivity.** RATIN is a back-office review and decision-support
workflow that helps procurement teams inspect complex document packages faster
and with stronger auditability. This matches the
[official track description](https://openai.devpost.com/rules) for tools that
make teams faster or more effective.

## 4. One-sentence summary

RATIN combines deterministic Evidence binding with GPT-5.6 interpretation to
surface procurement requirements, conflicts, risks, and actions while keeping
every document-derived statement traceable to an exact PDF sentence or
spreadsheet cell.

## 5. Short project description

Procurement facts are often scattered across notices, contract conditions,
rendered office documents, and spreadsheets. RATIN presents an English decision
brief beside a continuous Evidence stream: click a fact or either side of a
conflict and the viewer scrolls to the verified source page and highlights the
exact text or cells. Deterministic code owns facts, coordinates, arithmetic, and
provenance; GPT-5.6 interprets only the verified context under a strict schema.

## 6. Full project description

RATIN is an evidence-linked review interface for complex procurement packages.
The Build Week demonstration uses one fixed, sanitized package containing five
source-document roles across PDF, HWP, and XLSX origins. The left pane summarizes
bid metadata, entry requirements, cost and market context, cross-document
conflicts, GPT-5.6 findings, and required actions. The right pane preserves a
continuous Evidence PDF stream with active file/page bookmarks and exact
highlighting.

The package deliberately contains three review problems: a 4-hour versus 2-hour
response requirement, a 50-day versus 49-day delivery term, and a 42 EA versus
42식 quantity-unit discrepancy. Selecting either side opens the exact source.
One worksheet Evidence link expands to six exact row targets on the same page.

The public repository is intentionally a downstream evaluation consumer, not a
release of the proprietary canonical document-processing engine. It contains
sanitized frozen artifacts, public manifests, a validated cached GPT decision,
the viewer, tests, and audit proofs. This makes the judging experience
reproducible without publishing internal pipeline code, source RUNs, or private
documents.

## 7. What it does

- Shows procurement metadata and bid-entry requirements with Evidence links.
- Places conflicting requirements side by side for A/B inspection.
- Jumps to exact text or cell coordinates in a continuous source stream.
- Highlights multiple worksheet targets simultaneously when one logical fact
  spans several cells or rows.
- Separates document Evidence from public-API provenance.
- Shows deterministic cost context without asking GPT-5.6 to calculate values.
- Uses GPT-5.6 for bounded conflict judgment, risk interpretation, actions,
  issuer questions, and an English decision brief.
- Rejects unauthorized Evidence IDs, numbers, malformed output, and guessed
  fallback navigation.

## 8. Why it matters

A page-level citation is often too broad for high-stakes review. Reviewers need
to know which sentence or cell supported a conclusion, whether a newer document
changed a requirement, and whether a value came from the package or an external
API. RATIN keeps interpretation useful without giving the language model control
over source truth, arithmetic, or coordinates.

## 9. How Codex was used

Codex inspected the existing pipeline outputs and reference UI, built the fixed
downstream adapter and consumer, connected the strict GPT-5.6 response contract,
implemented cache and fail-closed validation, verified every public Evidence
jump against the final PDF text layer, performed browser QA, authored tests,
rebuilt sanitized public exhibits, and executed security, privacy, path, and
secret audits. Codex did not publish or reconstruct the proprietary canonical
engine.

## 10. How GPT-5.6 was used

GPT-5.6 receives only frozen verified Evidence text, deterministic values,
allowed Evidence IDs, allowed numbers, public-API provenance, and a strict JSON
schema. It may return conflict judgment, risk interpretation, required actions,
one issuer question, an English decision brief, and Evidence-ID selections.

GPT-5.6 does **not** extract source documents, create coordinates, calculate
amounts or statistics, generate source facts, or invent Evidence IDs. The app
rejects malformed or semantically unauthorized output before display or cache
write. Cached mode is the reproducible judging baseline. A final optional-live
proof request was rejected by the local semantic gate and did not replace the
validated frozen cache; the exact result is disclosed in
`docs/GPT56_LIVE_CALL_PROOF.md`.

## 11. What existed before Build Week

- Proprietary canonical document-processing pipeline
- Document normalization and Evidence PDF generation
- Coordinate-binding infrastructure
- Earlier Dual A4 reference interface

These components are not included in the public repository.

## 12. What was built or materially extended during Build Week

- Controlled mixed-format demonstration package
- Sanitized public procurement detail-page integration
- Fixed downstream projection contract
- GPT-5.6 strict structured decision layer
- Runtime-resolved public Evidence aliases
- Continuous Evidence stream consumer and file/page bookmarks
- Three exact A/B conflict comparisons
- Same-page multi-target highlighting
- Public-API provenance drawer and document/API separation
- Cache, schema, Evidence-ID, and allowed-number gates
- Upload-first simultaneous multi-file drag/drop replay
- Public proof generation, clean-install tests, and repository audit

## 13. Technical implementation

The public app is a small Python 3.11 HTTP server with a dependency-light
HTML/CSS/JavaScript interface. It loads a sanitized Evidence packet, public
binding manifest, source manifest, API-provenance snapshot, strict GPT schema,
and validated frozen cache. At startup it verifies file digests, page counts,
coordinates, cache digests, Evidence IDs, and authorized numbers.

The viewer renders Evidence PDF pages with `pypdfium2`. Navigation is resolved at
runtime from public Evidence aliases to manifest entries; physical pages and
bboxes are not embedded in click handlers. The proof builder reopens every final
PDF, requires each target text to be unique, recalculates its bbox from the text
layer, and verifies the coordinate frame. Optional live mode calls the OpenAI
Responses API with strict Structured Outputs and writes only a successfully
validated result to a gitignored runtime cache.

## 14. Testing instructions

```powershell
git clone https://github.com/sdchae/ratin-build-week-demo.git
cd ratin-build-week-demo
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\build_public_proofs.py
.\run_tests.ps1
```

The suite checks public manifests, PDF digests and page counts, exact text and
bboxes, multi-target behavior, zero fallbacks, cache/source/schema/prompt digest
matching, strict decision validation, unauthorized-number rejection, public
paths, upload wiring, and the export audit.

## 15. Cached-mode execution instructions

```powershell
.\.venv\Scripts\python.exe app\server.py --cached
```

Open <http://127.0.0.1:8794/?autoload=1> to load the validated report directly,
or open <http://127.0.0.1:8794/> and drop the five extracted sample PDFs together
onto the upload button.

## 16. Optional live-mode instructions

Set the API key only in the current process environment:

```powershell
$env:OPENAI_API_KEY="<your evaluator key>"
$env:OPENAI_MODEL="gpt-5.6"
.\.venv\Scripts\python.exe app\server.py --live
```

Live output is displayed or cached only after the same schema, Evidence-ID,
allowed-number, and semantic validation used for the frozen cache. Failure falls
back to a digest-matching cache and is reported rather than presented as live.

## 17. Synthetic sample disclosure

This is a controlled synthetic demonstration, not an actual procurement or bid.
The public package includes two sanitized public-source exhibits and three
controlled synthetic exhibits. Every synthetic PDF page carries a disclosure.
Contradictions were inserted deliberately to demonstrate review behavior.

## 18. Limitations

- The proprietary canonical engine is not included; the public app consumes
  frozen sanitized outputs.
- The demo supports one fixed package, not a general upload pipeline.
- Bidder eligibility cannot be determined without a bidder profile.
- Public-price data is dated, reference-only, and not an exact package-item
  match in this example.
- The sample does not establish generalized extraction or accuracy performance.
- The output is not an actual bid, cost, expected profit, eligibility decision,
  or final procurement decision.
- The video's closing 22-link count predates final provenance review. One
  derived API-candidate-to-XLSX link was removed because the items were not an
  exact match; the validated public metric is 21/21 logical links, 26 physical
  targets, and zero fallback.

## 19. GitHub URL

<https://github.com/sdchae/ratin-build-week-demo>

## 20. YouTube URL

<https://youtu.be/reSHijMlEnU>

## 21. Final validated metrics

- Source-document roles: 5
- Original formats represented: 3 (PDF, HWP, XLSX)
- Logical Evidence links: 21 / 21 exact
- Physical text/cell targets: 26 exact
- Multi-target logical links: 1 (`EV-056`, six worksheet-row targets)
- Page/document/table/nearest/offset/first-page fallbacks: 0
- Unverified Evidence used: 0
- Hardcoded physical anchors found by static scan: 0
- Deliberate A/B conflict comparisons: 3

Metric definitions and the video-copy discrepancy are documented in
`docs/METRIC_ACCOUNTING.md`.

## 22. Codex Session ID

**[INSERT CODEX SESSION ID BEFORE SUBMISSION]**
