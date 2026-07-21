# Security and Responsible Evaluation

## Secrets

Never commit an API key. Copy `.env.example` only as a local reference and set
`OPENAI_API_KEY` in the current process environment for optional live mode.
The server does not print request headers or credentials. Successful live
responses are written only to the gitignored `.runtime` directory.

## Public data boundary

This repository intentionally excludes the proprietary canonical processing
engine, internal RUN trees, private databases, source HWP/HWPX files, customer
corpora, patent materials, virtual environments, and raw Codex logs.

## Reporting

For a security concern, contact the repository owner through the private
Build Week submission channel. Do not open a public issue containing a secret,
personal data, or an unredacted source document.

## Audit

Run:

```powershell
python tools\build_public_proofs.py
```

The command regenerates `proofs/PUBLIC_EXPORT_AUDIT.json` and fails if a public
secret, absolute local path, private RUN path, personal contact value, prohibited
asset, oversized file, HWP/HWPX source, or forbidden directory is found.

