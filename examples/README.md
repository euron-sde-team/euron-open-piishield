# Examples

| Example | Shows | Needs a real API? |
| --- | --- | --- |
| [quickstart](quickstart/) | the brief's `shield.mask(text)` example, plus `scan` and `tokenize` | yes |
| [ai-gateway](ai-gateway/) | `protect`-then-`restore` round trip, with a stub transport standing in for both PIIShield and the external model | no |
| [node-quickstart](node-quickstart/) | the Node.js SDK: `scan`, `mask`, `tokenize`, and an AI-gateway `protect`/`restore` round trip | yes |

## Credentials

The examples that need a real API read `PIISHIELD_API_URL` and `PIISHIELD_API_KEY`. Get
both by running the project's own stack (`make up`) and creating a key on the
dashboard's API Keys page, or `make demo` for a seeded project and a printed login (sign
in, then create a key from the same page).
`ai-gateway` needs neither: it runs standalone against a stub transport that plays the
part of the API, so it works the moment the Python SDK is installed.
