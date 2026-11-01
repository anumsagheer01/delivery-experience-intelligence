"""Driver Intelligence Agent extension (Delivery Experience Intelligence 2.0).

Synthetic data only in demos and evals. No GCP calls, no network calls,
no messages sent. The agent is a single agent with a real tool calling
loop: every approach event produces a trace of multiple tool calls plus
decisions that cite the deterministic rule used. LLM summarization, when
present, is the last step only and is validated against the deterministic
card; when it is unavailable or fails validation, the deterministic
fallback card is used.
"""

from .memory import (
    InstructionCandidate,
    Observation,
    StopMemoryStore,
    StopProfile,
    redact_text,
    resolve_conflicts,
)
from .agent import DriverAgent, ToolTrace
from .feedback import process_feedback

__all__ = [
    "DriverAgent",
    "InstructionCandidate",
    "Observation",
    "StopMemoryStore",
    "StopProfile",
    "ToolTrace",
    "process_feedback",
    "redact_text",
    "resolve_conflicts",
]
