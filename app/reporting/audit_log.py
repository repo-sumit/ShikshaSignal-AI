"""Build and write the per-run audit log.

The audit log is a load-bearing trust signal: it records exactly which data files were
read, which policy lookup was used, which LLM provider answered (and whether the
factory fell back to mock — at construction OR per-section), which model name was
used, and which files were written. Anyone reproducing a run can diff this against
their own.

run_id is a deterministic SHA-1 of the command args + a UTC timestamp so the same
invocation in the same second produces the same id; this keeps tests stable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


SYNTHETIC_DATA_NOTICE: str = (
    "All inputs are SYNTHETIC and public-safe. No real student, teacher, school, or "
    "district names appear in the data; no PII is processed. Generated with a fixed "
    "seed so runs are reproducible."
)


@dataclass
class AuditLog:
    run_id: str
    timestamp: str
    command_args: dict
    data_files_used: list[str]
    policy_docs_used: list[str]
    llm_provider: str              # actual provider that produced the memo
    requested_llm_provider: str    # what the caller asked for
    fallback_used: bool            # True if construction OR any section fell back
    output_files: list[str]
    risk_formula_version: str
    risk_weights: dict
    # ---- Milestone 4 additions ----
    actual_llm_provider: str = ""     # mirror of llm_provider for spec compatibility
    model_name: str | None = None     # concrete model that answered (e.g. gemini-1.5-flash)
    fallback_reason: str | None = None
    grounding_failures: dict = field(default_factory=dict)   # section -> [tokens]
    provider_latency_ms: float = 0.0   # summed across all section calls
    section_metadata: dict = field(default_factory=dict)     # section -> dict
    # -------------------------------
    synthetic_data_notice: str = SYNTHETIC_DATA_NOTICE
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "command_args": self.command_args,
            "data_files_used": list(self.data_files_used),
            "policy_docs_used": list(self.policy_docs_used),
            "llm_provider": self.llm_provider,
            "actual_llm_provider": self.actual_llm_provider or self.llm_provider,
            "requested_llm_provider": self.requested_llm_provider,
            "model_name": self.model_name,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "grounding_failures": dict(self.grounding_failures),
            "provider_latency_ms": round(self.provider_latency_ms, 2),
            "section_metadata": dict(self.section_metadata),
            "output_files": list(self.output_files),
            "risk_formula_version": self.risk_formula_version,
            "risk_weights": self.risk_weights,
            "synthetic_data_notice": self.synthetic_data_notice,
            "extra": self.extra,
        }


def _stable_run_id(command_args: dict, timestamp: str) -> str:
    payload = json.dumps(command_args, sort_keys=True) + "|" + timestamp
    return "run_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def build_audit_log(
    command_args: dict,
    data_files_used: list[Path],
    policy_docs_used: list[Path],
    llm_provider: str,
    requested_llm_provider: str,
    fallback_used: bool,
    output_files: list[Path],
    risk_formula_version: str,
    risk_weights: dict,
    timestamp: str | None = None,
    extra: dict | None = None,
    model_name: str | None = None,
    fallback_reason: str | None = None,
    grounding_failures: dict | None = None,
    provider_latency_ms: float = 0.0,
    section_metadata: dict | None = None,
) -> AuditLog:
    ts = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return AuditLog(
        run_id=_stable_run_id(command_args, ts),
        timestamp=ts,
        command_args=dict(command_args),
        data_files_used=[str(p) for p in data_files_used],
        policy_docs_used=[str(p) for p in policy_docs_used],
        llm_provider=llm_provider,
        actual_llm_provider=llm_provider,
        requested_llm_provider=requested_llm_provider,
        fallback_used=bool(fallback_used),
        output_files=[str(p) for p in output_files],
        risk_formula_version=risk_formula_version,
        risk_weights=dict(risk_weights),
        model_name=model_name,
        fallback_reason=fallback_reason,
        grounding_failures=dict(grounding_failures or {}),
        provider_latency_ms=float(provider_latency_ms),
        section_metadata=dict(section_metadata or {}),
        extra=dict(extra or {}),
    )


def write_audit_log(audit: AuditLog, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit.to_dict(), indent=2, sort_keys=False), encoding="utf-8")
    return path
