# Public Architecture

```text
Public or controlled synthetic documents
    -> proprietary canonical pipeline (not included)
    -> sanitized frozen Evidence PDFs
    -> public binding manifest
    -> deterministic report packet and public API provenance
    -> optional GPT-5.6 structured interpretation
    -> Dual A4 decision brief and exact source navigation
```

The public server never parses procurement source files and never generates a
page or bbox. It verifies the frozen public PDF digests, reads runtime aliases
from `evidence_binding_manifest.public.json`, validates the cached or live GPT
decision, and renders the consumer.

The left A4 pane is an English decision brief. The right A4 pane is a continuous
stream of every public Evidence PDF page. Clicking a report fact resolves its
public Evidence alias through the binding manifest, scrolls to the matching PDF
page, and applies one or more exact highlights.

Deterministic and GPT responsibilities remain visually and structurally
separate. Costs, counts, coordinates, and public API values are frozen inputs.
GPT-5.6 interprets conflict and risk, suggests actions, asks clarification
questions, and writes the decision brief.

