"""Delivery Stop Memory: store interface plus SQLite/in-memory implementation.

The SQLite store implements the same fields as the BigQuery DDL in
sql/driver_intelligence_schema.sql, so the local demo runs with zero
cloud cost and the production path is a schema swap, not a redesign.

Security rules enforced here, not left to callers:
- Gate codes are never stored as values. Only a reference (for example
  gate_code_ref: ref_gate_a1) plus a verification status is stored.
- Any text that looks like a gate code value is redacted on ingest.
- Authorization is checked through driver_assignments before memory is
  returned by the agent layer; this module also exposes is_authorized
  so callers cannot forget the check.
- A reported-bad gate code loses verified status and can only regain
  it through an explicit re-verification, never through a driver claim
  alone.
"""

import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..logging import get_logger

log = get_logger(__name__)

VERIFICATION_STATUSES = ("verified", "unverified", "expired", "invalid")
FEEDBACK_TYPES = (
    "gate_code_incorrect",
    "entrance_inaccessible",
    "placement_outdated",
    "locker_unavailable",
    "instructions_changed",
    "access_problem",
)

# Priority rank: lower wins. Safety restrictions are handled separately
# and always win, regardless of this ranking.
PRIORITY = {
    "verified_customer": 1,
    "policy_restriction": 2,
    "verified_operational": 3,
    "verified_historical": 4,
    "unverified_historical": 5,
    "unverified_driver": 6,
}
PRIORITY_LABEL = {
    1: "verified customer instructions",
    2: "policies/restrictions",
    3: "verified operational updates",
    4: "verified historical observations",
    5: "unverified historical observations",
    6: "unverified driver reports",
}

_GATE_CODE_RE = re.compile(
    r"(gate\s*code[^A-Za-z0-9]{0,12})([A-Za-z0-9#*]*\d[A-Za-z0-9#*]*)",
    re.IGNORECASE)
_INJECTION_RE = re.compile(
    r"(ignore\s+(previous|all|prior)\s+instructions|reveal\s+the\s+gate\s+code"
    r"|override\s+the\s+policy|disregard\s+the\s+restriction)",
    re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_text(text: str) -> str:
    """Replace any gate code value with a reference-only placeholder.

    The reference itself is kept (it is not a secret); the value is not.
    """
    if not text:
        return text
    redacted = _GATE_CODE_RE.sub(r"\1[gate code reference only]", text)
    return redacted


def looks_like_injection(text: str) -> bool:
    return bool(text) and bool(_INJECTION_RE.search(text))


@dataclass
class StopProfile:
    stop_id: str
    address_id: str = ""
    building_type: str = ""
    preferred_entrance: str = ""
    preferred_placement: str = ""
    contact_preference: str = ""
    access_instructions: str = ""
    gate_code_ref: str = ""
    gate_verification_status: str = "unverified"
    leave_unattended_restriction: bool = False
    leave_restriction_reason: str = ""
    known_access_problems: str = ""
    instruction_source: str = ""
    verification_status: str = "unverified"
    confidence: float = 0.0
    created_at: str = ""
    updated_at: str = ""
    expires_at: str = ""
    is_current: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Observation:
    stop_id: str
    kind: str
    text: str
    source_type: str
    verification_status: str = "unverified"
    created_at: str = ""
    is_restriction: bool = False
    observation_id: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InstructionCandidate:
    kind: str
    text: str
    source_type: str
    verification_status: str = "unverified"
    created_at: str = ""
    is_restriction: bool = False

    @property
    def priority(self) -> int:
        return PRIORITY.get(self.source_type, 5)


@dataclass
class ConflictOutcome:
    kind: str
    winner: Optional[InstructionCandidate]
    losers: list = field(default_factory=list)
    restriction: Optional[InstructionCandidate] = None
    reason: str = ""
    rule: str = ""


def resolve_conflicts(candidates: list) -> dict:
    """Deterministic conflict resolution, grouped by instruction kind.

    Returns a dict with keys: winners (kind -> candidate dict), losers,
    restrictions (kind -> candidate dict), reasons (list of strings),
    rules (list of strings). Safety restrictions always win: a
    restriction is returned separately and also suppresses any
    conflicting non-restriction winner for the same kind.
    """
    by_kind: dict = {}
    for cand in candidates:
        by_kind.setdefault(cand.kind, []).append(cand)
    winners, restrictions, losers, reasons, rules = {}, {}, [], [], []
    for kind, group in sorted(by_kind.items()):
        restriction = next((c for c in group if c.is_restriction), None)
        if restriction is not None:
            restrictions[kind] = restriction
            rules.append("SAFETY_RULE: restrictions always win")
            reasons.append(
                f"kind={kind}: restriction kept regardless of conflicts: "
                f"{redact_text(restriction.text)}")
        pool = [c for c in group if not c.is_restriction]
        if not pool:
            continue
        ordered = sorted(pool, key=lambda c: (c.priority, c.created_at or ""))
        winner = ordered[0]
        winners[kind] = winner
        for loser in ordered[1:]:
            losers.append(loser)
            rule = (
                f"PRIORITY_RULE: {PRIORITY_LABEL[winner.priority]} "
                f"(rank {winner.priority}) beat "
                f"{PRIORITY_LABEL[loser.priority]} (rank {loser.priority})")
            rules.append(rule)
            reasons.append(
                f"kind={kind}: winner '{redact_text(winner.text)}' "
                f"({winner.source_type}) beat loser "
                f"'{redact_text(loser.text)}' ({loser.source_type}); {rule}")
        if restriction is not None:
            reasons.append(
                f"kind={kind}: restriction overrides winner "
                f"'{redact_text(winner.text)}' for enforcement; "
                "the winner is shown only as context, never as permission")
    return {
        "winners": {k: asdict(v) for k, v in winners.items()},
        "restrictions": {k: asdict(v) for k, v in restrictions.items()},
        "losers": [asdict(c) for c in losers],
        "reasons": reasons,
        "rules": sorted(set(rules)),
    }


class StopMemoryStore:
    """SQLite stop memory. Default is in-memory; pass a path to persist."""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS driver_assignments (
            driver_id TEXT NOT NULL, stop_id TEXT NOT NULL,
            PRIMARY KEY (driver_id, stop_id));
        CREATE TABLE IF NOT EXISTS stop_profiles (
            stop_id TEXT PRIMARY KEY, address_id TEXT, building_type TEXT,
            preferred_entrance TEXT, preferred_placement TEXT,
            contact_preference TEXT, access_instructions TEXT,
            gate_code_ref TEXT, gate_verification_status TEXT,
            leave_unattended_restriction INTEGER,
            leave_restriction_reason TEXT, known_access_problems TEXT,
            instruction_source TEXT, verification_status TEXT,
            confidence REAL, created_at TEXT, updated_at TEXT,
            expires_at TEXT, is_current INTEGER);
        CREATE TABLE IF NOT EXISTS stop_observations (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            stop_id TEXT, kind TEXT, text TEXT, source_type TEXT,
            verification_status TEXT, created_at TEXT, is_restriction INTEGER);
        CREATE TABLE IF NOT EXISTS driver_feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id TEXT, stop_id TEXT, feedback_type TEXT, note TEXT,
            created_at TEXT, applied TEXT);
        """)
        self.conn.commit()

    def assign_driver(self, driver_id: str, stop_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO driver_assignments VALUES (?, ?)",
            (driver_id, stop_id))
        self.conn.commit()

    def is_authorized(self, driver_id: str, stop_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM driver_assignments WHERE driver_id=? AND stop_id=?",
            (driver_id, stop_id)).fetchone()
        return row is not None

    def upsert_profile(self, profile: StopProfile) -> StopProfile:
        profile.access_instructions = redact_text(profile.access_instructions)
        profile.preferred_placement = redact_text(profile.preferred_placement)
        profile.preferred_entrance = redact_text(profile.preferred_entrance)
        if not profile.created_at:
            profile.created_at = now_iso()
        profile.updated_at = now_iso()
        d = profile.to_dict()
        d["leave_unattended_restriction"] = int(profile.leave_unattended_restriction)
        d["is_current"] = int(profile.is_current)
        cols = list(d.keys())
        self.conn.execute(
            f"INSERT OR REPLACE INTO stop_profiles ({','.join(cols)}) "
            f"VALUES ({','.join('?' * len(cols))})",
            [d[c] for c in cols])
        self.conn.commit()
        log.info("upserted stop profile %s status=%s",
                 profile.stop_id, profile.verification_status)
        return profile

    def get_profile(self, stop_id: str) -> Optional[StopProfile]:
        row = self.conn.execute(
            "SELECT * FROM stop_profiles WHERE stop_id=? AND is_current=1",
            (stop_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["leave_unattended_restriction"] = bool(d["leave_unattended_restriction"])
        d["is_current"] = bool(d["is_current"])
        return StopProfile(**d)

    def add_observation(self, obs: Observation) -> Observation:
        obs.text = redact_text(obs.text)
        if not obs.created_at:
            obs.created_at = now_iso()
        cur = self.conn.execute(
            "INSERT INTO stop_observations (stop_id, kind, text, source_type,"
            " verification_status, created_at, is_restriction)"
            " VALUES (?,?,?,?,?,?,?)",
            (obs.stop_id, obs.kind, obs.text, obs.source_type,
             obs.verification_status, obs.created_at,
             int(obs.is_restriction)))
        obs.observation_id = cur.lastrowid
        self.conn.commit()
        return obs

    def list_observations(self, stop_id: str) -> list:
        rows = self.conn.execute(
            "SELECT * FROM stop_observations WHERE stop_id=? ORDER BY created_at",
            (stop_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["is_restriction"] = bool(d["is_restriction"])
            out.append(Observation(**d))
        return out

    def record_feedback_row(self, driver_id: str, stop_id: str,
                            feedback_type: str, note: str,
                            applied: str) -> None:
        self.conn.execute(
            "INSERT INTO driver_feedback (driver_id, stop_id, feedback_type,"
            " note, created_at, applied) VALUES (?,?,?,?,?,?)",
            (driver_id, stop_id, feedback_type, redact_text(note or ""),
             now_iso(), applied))
        self.conn.commit()

    def expire_stale(self, stop_id: str) -> bool:
        """Mark a profile expired when expires_at is in the past.

        Returns True when a change was made. Expiration is deterministic
        and time based; it does not delete history.
        """
        profile = self.get_profile(stop_id)
        if not profile or not profile.expires_at:
            return False
        if profile.expires_at < now_iso() and profile.verification_status != "expired":
            profile.verification_status = "expired"
            profile.gate_verification_status = "expired"
            self.upsert_profile(profile)
            return True
        return False

    def reverify_gate_code(self, stop_id: str, gate_code_ref: str) -> bool:
        """Explicit re-verification path for an invalidated gate code.

        Only this function (plus a verified customer update via
        upsert_profile) can move a gate code back to verified. A driver
        report alone cannot.
        """
        profile = self.get_profile(stop_id)
        if not profile:
            return False
        profile.gate_verification_status = "verified"
        profile.gate_code_ref = gate_code_ref
        profile.verification_status = "verified"
        self.upsert_profile(profile)
        return True
