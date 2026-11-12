"""The five-minute path: mask one string.

    export PIISHIELD_API_URL=http://localhost:8000
    export PIISHIELD_API_KEY=YOUR_API_KEY
    export PIISHIELD_PROJECT_ID=YOUR_PROJECT_ID
    python quickstart.py

Needs a running PIIShield API, a project API key and that project's id (create a project,
then a key under its API keys). See ../README.md for how to get all three locally.
"""

from __future__ import annotations

import os
import sys

from euron_piishield import APIError, PIIShield


def main() -> int:
    shield = PIIShield(
        api_url=os.environ.get("PIISHIELD_API_URL", "http://localhost:8000"),
        api_key=os.environ["PIISHIELD_API_KEY"],
        project_id=os.environ["PIISHIELD_PROJECT_ID"],
    )

    text = "Customer: Rahul Sharma\nEmail: rahul@example.com\nPhone: 9876543210"
    print("Input:")
    print(text)
    print()

    try:
        scanned = shield.scan(text)
    except APIError as exc:
        print(f"scan failed: {exc.message} ({exc.code})", file=sys.stderr)
        return 1

    print(f"Found {len(scanned.findings)} finding(s):")
    for finding in scanned.findings:
        print(f"  {finding.category:12} [{finding.start}:{finding.end}] confidence={finding.confidence:.2f}")
    print()

    result = shield.mask(text)
    print("Protected (method=full_mask, the default):")
    print(result.protected_text)
    print()

    tokenized = shield.tokenize(text, scope_id="quickstart-demo")
    print("Protected (method=tokenize, scope_id=quickstart-demo):")
    print(tokenized.protected_text)

    shield.close()
    return 0 if scanned.findings else 1


if __name__ == "__main__":
    sys.exit(main())
