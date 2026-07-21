# Testing

## One command

```powershell
.\run_tests.ps1
```

Equivalent command:

```powershell
python -m pytest tests -q
```

## Coverage

The public tests verify:

- Packet and public manifest structure
- Public PDF SHA-256 digests and page counts
- Every matched text and exact bbox against the final public PDF text layer
- Multi-target Evidence behavior
- Zero fallback and zero unverified Evidence
- Cached GPT source/schema/prompt digest matching
- Strict decision schema and Evidence-ID authorization
- Unauthorized-number rejection
- Runtime-relative public paths
- Cross-clone public export manifest hashes with normalized text line endings
- Absence of private HWP/HWPX, internal RUN paths, secrets, and oversized files
- Upload button multi-file drag/drop wiring

Regenerate the audit and proof artifacts before the tests:

```powershell
python tools\build_public_proofs.py
```
