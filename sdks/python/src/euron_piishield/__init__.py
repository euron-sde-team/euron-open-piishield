"""Euron Open PIIShield for Python.

Detect, mask, redact, tokenize and anonymize personally identifiable and financial
information across text, JSON, documents and AI agent prompts and responses::

    from euron_piishield import PIIShield

    shield = PIIShield(
        api_url="http://localhost:8000", api_key="YOUR_API_KEY", project_id="YOUR_PROJECT_ID"
    )
    text = "Customer: Rahul Sharma\\nEmail: rahul@example.com\\nPhone: 9876543210"
    result = shield.mask(text)
    print(result.protected_text)

    # AI gateway: protect before sending to an external model, restore after.
    protected = shield.protect("My PAN is ABCDE1234F. Explain my tax record.")
    # Send only protected.protected_text to the external AI provider.

For asyncio code, use :class:`AsyncPIIShield` instead: the same methods, awaited. See the
README for the full wire format, every exception type, and the vault-scope and
AI-gateway safety properties.
"""

from euron_piishield._version import __version__
from euron_piishield.aio import AsyncPIIShield
from euron_piishield.client import PIIShield
from euron_piishield.errors import (
    APIError,
    ConnectionError,
    PIIShieldError,
    PolicyViolationError,
    UnsupportedFileTypeError,
    VaultPermissionError,
)
from euron_piishield.models import (
    AuditLogEntry,
    AuditLogPage,
    ColumnFinding,
    DatabaseScanResult,
    DetokenizeResult,
    DocumentScanReport,
    Finding,
    Policy,
    ProtectionJsonResult,
    ProtectionResult,
    ProtectResult,
    RestoreResult,
    ReviewItem,
    ScanResult,
)

__all__ = [
    "APIError",
    "AsyncPIIShield",
    "AuditLogEntry",
    "AuditLogPage",
    "ColumnFinding",
    "ConnectionError",
    "DatabaseScanResult",
    "DetokenizeResult",
    "DocumentScanReport",
    "Finding",
    "PIIShield",
    "PIIShieldError",
    "Policy",
    "PolicyViolationError",
    "ProtectResult",
    "ProtectionJsonResult",
    "ProtectionResult",
    "RestoreResult",
    "ReviewItem",
    "ScanResult",
    "UnsupportedFileTypeError",
    "VaultPermissionError",
    "__version__",
]
