# GPT-5.6 Live-Call Proof

## Result

**Live success: No.** One request was made through the repository's existing
Responses API path with requested model `gpt-5.6`. The response was parsed as
structured JSON, but the local fail-closed contract rejected it with:

```text
Not Found in Package must not cite unrelated Evidence
```

The application therefore selected the validated frozen cache. This result is
not represented as a successful live call.

## Recorded evidence

- Attempt completion observed at: `2026-07-21T22:32:47.7538962Z`
- Requested model: `gpt-5.6`
- Returned model: unavailable because the rejected raw payload is not retained
- Response ID: unavailable for the same reason
- Request status: response received; local validation rejected
- Structured JSON parse: PASS
- Local schema and semantic policy validation: FAIL
- Runtime cache written: No
- Frozen cache changed: No
- Input packet SHA-256:
  `1690210412dd3f450dc74971504d6d84cd5d91da03887214f0d63d627bce9513`
- Frozen cache SHA-256 before and after:
  `cd23170db07d18f25be21a34d62710f61f79a831d5aab3accdb761abe592941b`

The machine-readable record is
[`proofs/gpt56_live_call_proof.public.json`](../proofs/gpt56_live_call_proof.public.json).
Its JSON Schema is
[`proofs/gpt56_live_call_proof.schema.json`](../proofs/gpt56_live_call_proof.schema.json).

## Why no live response or cache digest exists

`app/server.py` validates the parsed decision before its atomic runtime-cache
write. The semantic rejection occurred at that gate, so the repository correctly
did not preserve or publish the rejected response and did not update either the
runtime or frozen cache. Consequently, returned-model, response-ID, raw-response
SHA-256, runtime-cache SHA-256, and live/cache equality are unavailable rather
than inferred.

## Reproduction

Set the key only in the current process environment; do not save it in this
repository.

```powershell
$env:OPENAI_API_KEY="<evaluator key in the current process only>"
$env:OPENAI_MODEL="gpt-5.6"
.\.venv\Scripts\python.exe app\server.py --live
```

The server attempts live mode once at initialization. On the recorded failure,
its startup output reports `Decision mode: CACHED GPT` and a fallback note with
the exact rejection above. The frozen cache remains the reproducible judging
baseline.
