#!/usr/bin/env python3
"""Shared utilities for madness scripts.

Centralizes JSON I/O, asset loading, constants, and date helpers
used across manage_assets, validate_genes, inject_claudemd, etc.
"""

import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ASSET_FILES = {"gene": "genes.json", "sop": "sops.json", "pref": "prefs.json"}

VALID_ASSET_TYPES = {"gene", "sop", "pref"}

VALID_STATUSES = {"active", "provisional", "deprecated"}

INJECTABLE_STATUSES = {"active", "provisional"}

# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def today_iso() -> str:
    """Return today's date as YYYY-MM-DD."""
    return date.today().isoformat()


def utc_now_iso() -> str:
    """Return current UTC datetime in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def utc_today_iso() -> str:
    """Return today's UTC date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def read_json(path):
    """Read a JSON file. Return None if the file does not exist."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_json_list(path):
    """Read a JSON file expected to contain a list. Return [] if missing."""
    data = read_json(path)
    if data is None:
        return []
    return data


def write_json_atomic(path, data):
    """Write *data* as JSON to *path* atomically via tempfile + os.replace."""
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Asset loading
# ---------------------------------------------------------------------------


def load_all_assets(memory_dir, statuses=None):
    """Load Gene/SOP/Pref assets from *memory_dir*.

    Each item gets an ``asset_type`` field set if not already present.
    If *statuses* is given (a set of strings), only items whose status
    is in that set are returned.
    """
    assets = []
    for asset_type, filename in ASSET_FILES.items():
        filepath = os.path.join(memory_dir, filename)
        if not os.path.exists(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("items", data.get("assets", []))
            for item in items:
                item.setdefault("asset_type", asset_type)
                if statuses is None or item.get("status") in statuses:
                    assets.append(item)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to read {filepath}: {e}", file=sys.stderr)
    return assets


def type_to_filename(asset_type):
    """Map an asset type string to its JSON filename."""
    return ASSET_FILES.get(asset_type, f"{asset_type}s.json")
