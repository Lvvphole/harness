from __future__ import annotations

from enum import Enum
from typing import Any


class Phase(str, Enum):
    ADMIT_TASK = "ADMIT_TASK"
    LOAD_CONTRACT = "LOAD_CONTRACT"
    REQUEST_PROPOSAL = "REQUEST_PROPOSAL"
    VALIDATE_GENERATION = "VALIDATE_GENERATION"
    AUTHORIZE_TOOL_CALL = "AUTHORIZE_TOOL_CALL"
    EXECUTE_IN_SANDBOX = "EXECUTE_IN_SANDBOX"
    OBSERVE_RESULT = "OBSERVE_RESULT"
    RUN_ORACLE = "RUN_ORACLE"
    COMMIT = "COMMIT"
    RETRY = "RETRY"
    HALT = "HALT"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


TERMINAL = {Phase.PASS, Phase.FAIL, Phase.BLOCKED, Phase.HALT}


class RunState:
    def __init__(self, run_id: str, contract: dict[str, Any]):
        self.run_id = run_id
        self.contract = contract
        self.phase = Phase.ADMIT_TASK
        self.attempt = 0
        self.turns = 0
        self.files_touched = 0
        self.write_authorized = False
        self.identical_failures = 0
        self.last_failure: str | None = None
        self.proposal_sha256: str | None = None
        self.termination: str | None = None

    def advance(self, phase: Phase) -> None:
        self.phase = phase
        if phase in {Phase.PASS, Phase.FAIL, Phase.BLOCKED, Phase.HALT}:
            self.termination = phase.value

    def note_failure(self, reason: str) -> None:
        if reason == self.last_failure:
            self.identical_failures += 1
        else:
            self.identical_failures = 1
            self.last_failure = reason

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "phase": self.phase.value,
            "attempt": self.attempt,
            "turns": self.turns,
            "files_touched": self.files_touched,
            "write_authorized": self.write_authorized,
            "proposal_sha256": self.proposal_sha256,
            "termination": self.termination,
        }
