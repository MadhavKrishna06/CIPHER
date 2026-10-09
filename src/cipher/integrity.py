"""Knowledge base integrity: SHA-256 manifest of every ingested document.

Guards against a poisoned or tampered knowledge base. Every file under RAW_DIR
is hashed before it is chunked and embedded. The manifest is committed to git,
so any later change to a source document (or a file swapped in by an attacker)
shows up as a hash mismatch and ingestion of that file is refused until a human
explicitly re-approves it with --accept-changes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import MANIFEST_PATH, RAW_DIR, SUPPORTED_EXTENSIONS

_CHUNK = 1 << 20  # 1 MiB read buffer


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(_CHUNK):
            h.update(block)
    return h.hexdigest()


def list_documents(raw_dir: Path = RAW_DIR) -> list[Path]:
    return sorted(
        p for p in raw_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    if not path.exists():
        return {"files": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(manifest: dict, path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


@dataclass
class VerifyResult:
    ok: list[Path]        # hash matches manifest
    new: list[Path]       # not in manifest yet
    changed: list[Path]   # in manifest, hash differs  -> refuse unless accepted
    missing: list[str]    # in manifest, file gone


def verify(raw_dir: Path = RAW_DIR, manifest: dict | None = None) -> VerifyResult:
    """Compare on-disk documents against the manifest. Does not modify anything."""
    manifest = manifest if manifest is not None else load_manifest()
    known = manifest.get("files", {})
    result = VerifyResult(ok=[], new=[], changed=[], missing=[])

    seen: set[str] = set()
    for path in list_documents(raw_dir):
        rel = path.relative_to(raw_dir).as_posix()
        seen.add(rel)
        digest = sha256_file(path)
        if rel not in known:
            result.new.append(path)
        elif known[rel]["sha256"] == digest:
            result.ok.append(path)
        else:
            result.changed.append(path)

    result.missing = sorted(set(known) - seen)
    return result


def record(paths: list[Path], raw_dir: Path = RAW_DIR, manifest: dict | None = None) -> dict:
    """Add or update manifest entries for the given files and return the manifest."""
    manifest = manifest if manifest is not None else load_manifest()
    files = manifest.setdefault("files", {})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for path in paths:
        rel = path.relative_to(raw_dir).as_posix()
        files[rel] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "ingested_at": now,
        }
    manifest["updated_at"] = now
    return manifest
