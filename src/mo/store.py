"""Plain-file storage for MO profiles.

v0.1 keeps everything as human-readable files under ``$MO_HOME`` (default ``~/.mo``)::

    active                     name of the active profile
    recent_drafts.json         hashed fingerprints of drafts MO checked (drift guard)
    sessions/<id>.json         @MO tune session state
    logs/calls.jsonl           one line per tool call, including failures (no text)
    logs/trace.jsonl           dev only (MO_TRACE=1): full inputs and outputs of every call
    profiles/<name>/
        profile.yaml           rules (stated by the user, or results of finished @MO tune runs)
        cases.jsonl            append-only case archive (source of truth)
        exemplars/<register>/  the user's own writing, one .md or .txt file per piece
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PROFILE = "default"
REGISTERS = ("email", "essay", "cover_letter", "article", "notes", "other")
MAX_CASE_TEXT = 4000
DRAFT_TTL = 14 * 24 * 3600
MAX_DRAFTS = 50

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def mo_home() -> Path:
    return Path(os.environ.get("MO_HOME", Path.home() / ".mo"))


def validate_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise ValueError(f"Invalid name {name!r}: use lowercase letters, digits, - or _ (max 40)")
    return name


def validate_register(register: str) -> str:
    if register not in REGISTERS:
        raise ValueError(f"Unknown register {register!r}; expected one of {', '.join(REGISTERS)}")
    return register


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].strip("-")
    return slug or "sample"


@dataclass(frozen=True)
class Exemplar:
    register: str
    name: str
    text: str
    modified: float
    source: str = "unknown"


class Profile:
    def __init__(self, name: str = DEFAULT_PROFILE, home: Path | None = None):
        self.name = validate_name(name.strip().lower())  # "ELI5-reader" and "eli5-reader" are the same profile
        self.root = (home or mo_home()) / "profiles" / self.name

    @property
    def exists(self) -> bool:
        return self.root.is_dir()

    def load(self) -> dict[str, Any]:
        path = self.root / "profile.yaml"
        data = (yaml.safe_load(path.read_text()) if path.exists() else None) or {}
        data.setdefault("rules", [])
        data.setdefault("candidates", [])
        return data

    def rules(self) -> list[dict[str, Any]]:
        return list(self.load()["rules"])

    def save(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "profile.yaml").write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    def add_rule(self, rule: str, scope: list[str], registers: list[str] | None = None) -> dict[str, Any]:
        data = self.load()
        for existing in data["rules"]:
            if existing["rule"].lower() == rule.lower():
                # Approving a rule that already exists reinforces it instead of duplicating it.
                existing["hits"] = int(existing.get("hits", 0)) + 1
                self.save(data)
                return {**existing, "reinforced": True}
        # The user stated it, so it starts strong (weight 0.8, 'always'); tune evidence moves it from there.
        entry = {"rule": rule, "scope": scope, "hits": 3, "misses": 0, "source": "user-approved",
                 "added": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if registers:
            entry["registers"] = [validate_register(r) for r in registers]
        data["rules"].append(entry)
        self.save(data)
        return entry

    def record_pick(self, task: str, axis: str, options: dict[str, str], chosen: str) -> dict[str, Any]:
        """A finished tune run, stored in code: the picked option gains a hit, the passed-over ones a miss.

        Rules are worded from MO's own option labels, so nothing the host wrote is stored.
        """
        data = self.load()
        by_text = {r["rule"]: r for r in data["rules"]}
        for key, label in options.items():
            text = f"{axis}: {label}"
            rule = by_text.get(text)
            if rule is None:
                rule = {"rule": text, "scope": [task], "hits": 0, "misses": 0, "source": "tune"}
                data["rules"].append(rule)
                by_text[text] = rule
            rule["hits" if key == chosen else "misses"] = int(rule.get("hits" if key == chosen else "misses", 0)) + 1
        self.save(data)
        return by_text[f"{axis}: {options[chosen]}"]

    def remove_rule(self, rule: str) -> bool:
        data = self.load()
        kept = [r for r in data["rules"] if r["rule"].lower() != rule.lower()]
        if len(kept) == len(data["rules"]):
            return False
        data["rules"] = kept
        self.save(data)
        return True

    def exemplars(self, register: str) -> list[Exemplar]:
        folder = self.root / "exemplars" / register
        if not folder.is_dir():
            return []
        found = []
        for path in sorted(folder.iterdir()):
            if path.suffix in (".md", ".txt") and path.is_file():
                raw = path.read_text()
                meta, text = {}, raw
                if match := _FRONT_MATTER_RE.match(raw):
                    meta = yaml.safe_load(match.group(1)) or {}
                    text = raw[match.end():]
                text = text.strip()
                if text:
                    found.append(Exemplar(register, path.stem, text, path.stat().st_mtime,
                                          meta.get("source", "unknown")))
        return found

    def registers_with_exemplars(self) -> list[str]:
        return [r for r in REGISTERS if self.exemplars(r)]

    def add_exemplar(self, register: str, name: str, text: str, source: str = "user-provided") -> str:
        folder = self.root / "exemplars" / validate_register(register)
        folder.mkdir(parents=True, exist_ok=True)
        stem, n = slugify(name), 2
        final = stem
        while (folder / f"{final}.md").exists():
            final, n = f"{stem}-{n}", n + 1
        added = datetime.now(timezone.utc).isoformat(timespec="seconds")
        front = yaml.safe_dump({"source": source, "added": added}, sort_keys=False)
        (folder / f"{final}.md").write_text(f"---\n{front}---\n{text.strip()}\n")
        return final

    def remove_exemplar(self, register: str, name: str) -> bool:
        folder = self.root / "exemplars" / validate_register(register)
        for suffix in (".md", ".txt"):
            path = folder / f"{name}{suffix}"
            if path.is_file() and path.parent == folder:
                path.unlink()
                return True
        return False

    def append_case(self, case: dict[str, Any]) -> str:
        case_id = f"c{int(time.time())}-{uuid.uuid4().hex[:6]}"
        record = {"id": case_id, "profile": self.name, "at": time.time(), **_trim(case)}
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "cases.jsonl").open("a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return case_id

    def cases(self) -> list[dict[str, Any]]:
        path = self.root / "cases.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def list_profiles(home: Path | None = None) -> list[str]:
    folder = (home or mo_home()) / "profiles"
    return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []


def active_profile(home: Path | None = None) -> str:
    path = (home or mo_home()) / "active"
    name = path.read_text().strip() if path.exists() else ""
    return name if _NAME_RE.match(name) else DEFAULT_PROFILE


def set_active_profile(name: str, home: Path | None = None) -> None:
    home = home or mo_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "active").write_text(validate_name(name) + "\n")


def resolve_profile(name: str | None) -> Profile:
    return Profile(name or active_profile())


class RecentDrafts:
    """Fingerprints of drafts MO checked, so AI-written text can't be saved as the user's writing.

    Only hashed word 5-grams are stored, never the text.
    """

    SHINGLE = 5
    MATCH = 0.5

    def __init__(self, home: Path | None = None):
        self.path = (home or mo_home()) / "recent_drafts.json"

    @classmethod
    def fingerprint(cls, text: str) -> set[str]:
        words = re.findall(r"[a-z0-9']+", text.lower())
        grams = {" ".join(words[i : i + cls.SHINGLE]) for i in range(len(words) - cls.SHINGLE + 1)}
        return {hashlib.sha256(g.encode()).hexdigest()[:12] for g in grams}

    def _load(self) -> list[dict[str, Any]]:
        items = json.loads(self.path.read_text()) if self.path.exists() else []
        now = time.time()
        return [item for item in items if now - item["at"] < DRAFT_TTL]

    def remember(self, draft: str) -> None:
        shingles = self.fingerprint(draft)
        if not shingles:
            return
        items = self._load()[-(MAX_DRAFTS - 1):] + [{"at": time.time(), "shingles": sorted(shingles)}]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items))

    def similarity(self, text: str) -> float:
        """Highest overlap with any recent draft, in either direction (0..1)."""
        sample = self.fingerprint(text)
        best = 0.0
        for item in self._load():
            draft = set(item["shingles"])
            shared = len(sample & draft)
            if sample and draft:
                best = max(best, shared / len(sample), shared / len(draft))
        return best


def log_call(tool: str, details: dict[str, Any], home: Path | None = None) -> None:
    folder = (home or mo_home()) / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool": tool, **details}
    with (folder / "calls.jsonl").open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def tracing() -> bool:
    return os.environ.get("MO_TRACE") == "1"


def trace_call(tool: str, args: dict[str, Any], result: Any = None, error: str | None = None) -> None:
    """Dev only: keep everything that went in and out, so the trace page can show it. Stays local."""
    folder = mo_home() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    record = {"at": time.time(), "tool": tool, "args": args, "result": result, "error": error}
    with (folder / "trace.jsonl").open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_trace() -> list[dict[str, Any]]:
    path = mo_home() / "logs" / "trace.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _trim(value: Any) -> Any:
    """Cap stored text so cases keep spans, not whole documents."""
    if isinstance(value, str):
        return value[:MAX_CASE_TEXT]
    if isinstance(value, dict):
        return {k: _trim(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_trim(v) for v in value]
    return value
