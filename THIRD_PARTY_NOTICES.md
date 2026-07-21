# Third-Party Notices

This public evaluation repository contains original HTML, CSS, JavaScript, and
Python code authored for the RATIN Build Week demonstration. It does not bundle
third-party source trees, font files, logos, music, or video.

Runtime and test dependencies are installed from PyPI:

| Component | Purpose | License |
|---|---|---|
| pypdfium2 | Render and inspect the frozen public Evidence PDFs | Apache-2.0 / BSD-3-Clause components; PDFium has additional third-party notices |
| pytest | Execute the public validation suite | MIT |

The optional live path calls the OpenAI Responses API over Python's standard
library HTTPS client. The OpenAI Python SDK is not bundled or required. Use of
OpenAI services is governed by the evaluator's applicable OpenAI terms.

The generated public PDFs use PDF standard/CID font references. No standalone
font file is stored in this repository.

Review the licenses published by each dependency for the authoritative terms.
The repository's custom evaluation license does not replace third-party terms.

