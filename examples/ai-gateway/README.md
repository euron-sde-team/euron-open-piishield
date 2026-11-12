# AI gateway (Python)

A `protect`-then-`restore` round trip, simulating "send protected text to an external
model, get a response, restore it for the calling application." Runs with **no real
PIIShield API and no model API key**: a stub HTTP transport stands in for the API (it
masks a PAN pattern with a tokenize placeholder, exactly like the real vault would), and
a stub function stands in for the external model call.

```bash
pip install ./sdks/python                 # from the repository root
python examples/ai-gateway/ai_gateway_demo.py
```

Output:

```text
Original prompt: 'My PAN is ABCDE1234F. Explain my tax record.'

Protected text (safe to send to a model): 'My PAN is [PAN_001]. Explain my tax record.'
Scope id (keep server side only):         'scope_b2c86457d325'

  -> sending to external model: 'My PAN is [PAN_001]. Explain my tax record.'
  <- external model responded: 'Based on the record, [PAN_001]. Explain my tax record.'

Restored text (for the calling application only): 'Based on the record, ABCDE1234F. Explain my tax record.'
```

What this proves: `protected.protected_text`, the only thing `call_external_model`
receives, never contains the real PAN, and `protected.scope_id` (the value that makes
restoration possible, matching the real API's `ai_gateway.schemas.GatewayProtectOut`) is
never part of that text either. See
[../../sdks/python/README.md](../../sdks/python/README.md#ai-gateway-safety-property) for
why this separation matters.

To run the same flow against a real backend, replace `StubTransport` with a real
connection: `PIIShield(api_url="http://localhost:8000", api_key="YOUR_API_KEY", project_id="YOUR_PROJECT_ID")`.
Every call to `shield.protect` and `shield.restore` stays exactly as written.
