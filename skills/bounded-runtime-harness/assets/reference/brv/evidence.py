from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class DecisionRecord:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.payload['run_id']}-{self.payload['attempt']}.json"
        body = json.dumps(self.payload, indent=2, sort_keys=True) + "\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(path, flags, 0o644)
        except FileExistsError as exc:
            raise FileExistsError(
                f"evidence record already exists: {path.name}"
            ) from exc
        with os.fdopen(fd, "w") as fh:
            fh.write(body)
        return path


def make_record(
    run_id: str,
    attempt: int,
    proposal_sha256: str,
    contract_id: str,
    gates: dict[str, str],
    decision: str,
    reasons: list[str],
    content_sha256: str | None = None,
    kind: str = "edit",
) -> DecisionRecord:
    write_authorized = decision == "ACCEPT"
    payload = {
        "run_id": run_id,
        "attempt": attempt,
        "proposal_sha256": proposal_sha256,
        "contract_id": contract_id,
        "kind": kind,
        "gates": gates,
        "decision": decision,
        "write_authorized": write_authorized,
        "reasons": reasons,
    }
    if content_sha256:
        payload["content_sha256"] = content_sha256
    return DecisionRecord(payload)
