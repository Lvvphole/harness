from __future__ import annotations

import math
import re
from collections import Counter

KEY_RE = re.compile(
    r"(?i)(aws_secret_access_key|secret_access_key|private_key|api_token)\s*[:=]\s*\S+"
)
PEM_RE = re.compile(r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----")
AWS_RE = re.compile(r"AKIA[0-9A-Z]{16}")


def _shannon(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def find_secret_hits(text: str, known: set[str] | None = None) -> list[str]:
    hits: list[str] = []
    if PEM_RE.search(text):
        hits.append("pem_private_key")
    if AWS_RE.search(text):
        hits.append("aws_access_key_id")
    if KEY_RE.search(text):
        hits.append("credential_assignment")
    for token in re.findall(r"[A-Za-z0-9_\-+/=]{24,}", text):
        if _shannon(token) >= 4.5:
            hits.append("high_entropy_token")
            break
    if known:
        for value in known:
            if value and value in text:
                hits.append("known_sensitive_value")
                break
    return hits
