# Node.js quickstart

Scan, mask and tokenize one string, then a protect/restore round trip through the AI
gateway, using the Node SDK.

```bash
cd examples/node-quickstart
pnpm install
export PIISHIELD_API_URL=http://localhost:8000
export PIISHIELD_API_KEY=YOUR_API_KEY        # from a project's API keys (write scope)
export PIISHIELD_PROJECT_ID=YOUR_PROJECT_ID  # that key's project
pnpm start
```

Output (ids and exact confidence scores vary with the backend's detectors; `category` is
always one of the five coarse categories, never a per-recognizer name):

```text
Input:
Customer: Rahul Sharma
Email: rahul@example.com
Phone: 9876543210

Found 2 finding(s):
  contact      [30:47] confidence=0.95
  contact      [55:65] confidence=0.80

Protected (method=full_mask, the default):
Customer: Rahul Sharma
Email: ****
Phone: ****

Protected (method=tokenize, scopeId=node-quickstart-demo):
Customer: Rahul Sharma
Email: [CONTACT_001]
Phone: [CONTACT_002]

AI gateway protected text (safe for a model): My PAN is [GOVERNMENT_ID_001]. Explain my tax record.
AI gateway restored text (for this app only): My PAN is ABCPE1234F. Explained my tax record.
```

See [../../sdks/node/README.md](../../sdks/node/README.md) for every method this SDK
exposes.
