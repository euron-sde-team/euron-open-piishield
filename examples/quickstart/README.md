# Quickstart (Python)

Mask one string: the exact example from the product brief.

```bash
pip install ./sdks/python                 # from the repository root
export PIISHIELD_API_URL=http://localhost:8000
export PIISHIELD_API_KEY=YOUR_API_KEY        # from a project's API keys (write scope)
export PIISHIELD_PROJECT_ID=YOUR_PROJECT_ID  # that key's project
python examples/quickstart/quickstart.py
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

Protected (method=tokenize, scope_id=quickstart-demo):
Customer: Rahul Sharma
Email: [CONTACT_001]
Phone: [CONTACT_002]
```

See [../../sdks/python/README.md](../../sdks/python/README.md) for every method this SDK
exposes, and that README's "Wire format" section for exactly which endpoints these calls
map to on the real API.
