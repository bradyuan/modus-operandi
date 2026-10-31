"""Plain-file storage for MO profiles.

v0.1 keeps everything as human-readable files under ``$MO_HOME`` (default ``~/.mo``)::

    active                     name of the active profile
    pending.json               writing samples awaiting the user's confirmation
    logs/calls.jsonl           one line per tool call
    profiles/<name>/
        profile.yaml           rules, candidates
        cases.jsonl            append-only case archive (source of truth)
        exemplars/<register>/  the user's own writing, one .md or .txt file per piece
"""

from __future__ import annotations

import json
import os
import re
import secrets
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
PENDING_TTL = 30 * 60

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
        self.name = validate_name(name)
        self.root = (home or mo_home()) / "profiles" / name

    @property
    def exists(self) -> bool:
        return self.root.is_dir()

    def load(self) -> dict[str, Any]:
        path = self.root / "profile.yaml"
        if not path.exists():
            return {"rules": [], "candidates": []}
        data = yaml.safe_load(path.read_text()) or {}
        data.setdefault("rules", [])
        data.setdefault("candidates", [])
        return data

    def rules(self) -> list[dict[str, Any]]:
        return list(self.load()["rules"])

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


class PendingSamples:
    """Writing samples waiting for the user's explicit yes (the guard against saving AI text)."""

    def __init__(self, home: Path | None = None):
        self.path = (home or mo_home()) / "pending.json"

    def _load(self) -> dict[str, Any]:
        items = json.loads(self.path.read_text()) if self.path.exists() else {}
        now = time.time()
        return {code: item for code, item in items.items() if now - item["created"] < PENDING_TTL}

    def _save(self, items: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, ensure_ascii=False))

    def add(self, profile: str, register: str, name: str, text: str) -> str:
        items = self._load()
        code = secrets.token_hex(3).upper()
        items[code] = {"profile": profile, "register": register, "name": name, "text": text, "created": time.time()}
        self._save(items)
        return code

    def pop(self, code: str) -> dict[str, Any] | None:
        items = self._load()
        item = items.pop(code.strip().upper(), None)
        self._save(items)
        return item


def log_call(tool: str, details: dict[str, Any], home: Path | None = None) -> None:
    folder = (home or mo_home()) / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool": tool, **details}
    with (folder / "calls.jsonl").open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _trim(value: Any) -> Any:
    """Cap stored text so cases keep spans, not whole documents."""
    if isinstance(value, str):
        return value[:MAX_CASE_TEXT]
    if isinstance(value, dict):
        return {k: _trim(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_trim(v) for v in value]
    return value
