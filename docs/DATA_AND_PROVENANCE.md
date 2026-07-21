# Data and Provenance

## Document Evidence

The repository contains five public Evidence PDFs. Two are sanitized
public-source exhibits. Three are controlled synthetic exhibits. Their digests,
page counts, exact matched text, and public PDF coordinates are frozen in
`demo_data/evidence_binding_manifest.public.json`.

The public binding manifest was generated from the final public PDFs, not copied
from internal PDF digests. Every target is rechecked against the final PDF text
layer by the public test suite.

## Deterministic values

The document-linked cost, reference values, counts, quantities, and coverage
warning are frozen downstream outputs. GPT does not calculate or modify them.

## Public API data

Public API values are stored separately in
`demo_data/public_api_provenance.json`. They are not converted into document
Evidence. The selected public price item has no exact document-item match and is
displayed as an API-only reference.

## Manifests

- `source_package_manifest.public.json`: public files and digests
- `evidence_binding_manifest.public.json`: public aliases and exact coordinates
- `public_export_manifest.json`: complete public-export file inventory
- `PUBLIC_EXPORT_AUDIT.json`: secret, path, personal-data, and asset audit

