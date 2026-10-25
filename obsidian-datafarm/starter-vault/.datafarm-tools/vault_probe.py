#!/usr/bin/env python3
"""
vault_probe.py -- read-only "is my vault connected?" diagnostic (zero dependencies).

Run this from the agent workspace (or locally) against a vault path. It prints a
connection report + a redaction scan so we both know exactly what state the
integration is in before any writing happens.

Checks:
  1. path exists / is a directory / readable
  2. .obsidian config present -> confirms it is a real Obsidian vault
  3. community plugins installed (compatibility / risk surface)
  4. note & attachment counts, vault size
  5. link/tag/frontmatter density (is it graph-ready?)
  6. SECRET SCAN: possible API keys, tokens, passwords, private keys in notes
  7. git status if the vault is version controlled
  8. write-access test (creates + deletes a temp file ONLY with --test-write)

Usage:
    python3 vault_probe.py <vault_dir> [--json] [--test-write] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, List

SECRET_PATTERNS = [
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("generic_api_key_assign", re.compile(r"(?i)\b(api[_-]?key|apikey|secret|token|password|passwd|pwd)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{12,}")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.=]{16,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("connection_string", re.compile(r"(?i)\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis|amqp)://[^\s'\"<>]+:[^\s'\"<>]+@")),
]
MAX_REPORT_PER_KIND = 10


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}GB"


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def probe(vault: str, limit: int, test_write: bool) -> Dict[str, object]:
    rep: Dict[str, object] = {"vault": os.path.abspath(vault), "ok": False, "checks": {}, "secrets": [], "warnings": []}
    if not os.path.exists(vault):
        rep["warnings"].append("PATH_MISSING: nothing at that path. Attach/copy/clone the vault into the workspace first.")
        return rep
    if not os.path.isdir(vault):
        rep["warnings"].append("NOT_A_DIRECTORY: give the vault ROOT folder, not a single note.")
        return rep

    rep["checks"]["readable"] = os.access(vault, os.R_OK)
    obs_dir = os.path.join(vault, ".obsidian")
    rep["checks"]["is_obsidian_vault"] = os.path.isdir(obs_dir)
    if not rep["checks"]["is_obsidian_vault"]:
        rep["warnings"].append("No .obsidian/ folder: usable as a vault, but it has never been opened in Obsidian (or config was excluded from the copy).")

    plugins: List[str] = []
    if os.path.isdir(obs_dir):
        pj = os.path.join(obs_dir, "community-plugins.json")
        if os.path.isfile(pj):
            try:
                plugins = [str(x) for x in json.loads(read_text(pj) or "[]")]
            except json.JSONDecodeError:
                rep["warnings"].append("community-plugins.json is not valid JSON.")
    rep["community_plugins"] = plugins
    rep["app_json"] = {}
    aj = os.path.join(obs_dir, "app.json")
    if os.path.isfile(aj):
        try:
            rep["app_json"] = json.loads(read_text(aj) or "{}")
        except json.JSONDecodeError:
            pass

    md = 0
    att = 0
    total_bytes = 0
    words = 0
    with_links = 0
    with_fm = 0
    tags: set = set()
    secrets: List[Dict[str, str]] = []
    scanned = 0
    link_re = re.compile(r"!?\[\[[^\]\n]+\]\]|\[[^\]\n]*\]\([^\s)]+\)")
    tag_re = re.compile(r"(?<![\w/])#[^\W\d][\w/\-]*")

    SKIP_DIRS = {".git", ".trash", "node_modules", "__pycache__", ".datafarm", ".datafarm-tools"}
    for dirpath, dirnames, filenames in os.walk(vault, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = os.path.join(dirpath, name)
            try:
                total_bytes += os.path.getsize(p)
            except OSError:
                pass
            if os.path.islink(p):
                continue
            if not name.lower().endswith(".md"):
                att += 1
                continue
            md += 1
            text = read_text(p)
            words += len(text.split())
            if link_re.search(text):
                with_links += 1
            if text.startswith("---"):
                with_fm += 1
            tags.update(tag_re.findall(text))
            if scanned < limit:
                scanned += 1
                for kind, rx in SECRET_PATTERNS:
                    for m in rx.finditer(text):
                        secrets.append({"kind": kind, "file": os.path.relpath(p, vault),
                                        "preview": (m.group(0)[:12] + "…REDACTED")})
                        break
    rep["checks"].update({
        "notes_md": md, "attachments_other": att, "vault_size": human(total_bytes),
        "vault_size_bytes": total_bytes, "words": words,
        "notes_with_links": with_links, "notes_with_frontmatter": with_fm,
        "unique_inline_tags": len(tags), "notes_scanned_for_secrets": scanned,
    })
    rep["secrets"] = secrets[:MAX_REPORT_PER_KIND * len(SECRET_PATTERNS)]
    if secrets:
        rep["warnings"].append(f"SECRET_SCAN: {len(secrets)} possible credential(s) found in notes. Do not share this vault verbatim.")

    if os.path.isdir(os.path.join(vault, ".git")):
        try:
            out = subprocess.run(["git", "-C", vault, "status", "--porcelain", "-b"],
                                 capture_output=True, text=True, timeout=20)
            lines = [l for l in out.stdout.splitlines() if l.strip()]
            rep["git"] = {"branch_line": lines[0] if lines else "", "dirty_files": max(0, len(lines) - 1),
                          "remote": subprocess.run(["git", "-C", vault, "remote", "-v"], capture_output=True, text=True, timeout=20).stdout.strip()}
        except (OSError, subprocess.SubprocessError) as exc:
            rep["warnings"].append(f"git probe failed: {exc}")

    if test_write:
        probe_path = os.path.join(vault, ".datafarm-write-probe.tmp")
        try:
            with open(probe_path, "w", encoding="utf-8") as fh:
                fh.write("probe")
            os.remove(probe_path)
            rep["checks"]["writable"] = True
        except OSError as exc:
            rep["checks"]["writable"] = False
            rep["warnings"].append(f"WRITE_TEST_FAILED: {exc} -- I can read this vault but not modify it.")
    else:
        rep["checks"]["writable"] = "not tested (pass --test-write)"

    rep["ok"] = bool(md) and rep["checks"]["readable"]
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Diagnose an Obsidian vault connection (read-only).")
    ap.add_argument("vault")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=500, help="max notes to secret-scan (default 500)")
    ap.add_argument("--test-write", action="store_true", help="create+delete a temp file to prove write access")
    args = ap.parse_args(argv)

    rep = probe(args.vault, args.limit, args.test_write)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("=== OBSIDIAN CONNECTION REPORT ===")
        print(f"vault: {rep['vault']}")
        print(f"status: {'CONNECTED (readable markdown vault)' if rep['ok'] else 'NOT CONNECTED'}")
        for k, v in rep.get("checks", {}).items():
            print(f"  {k}: {v}")
        if rep.get("community_plugins"):
            print(f"community plugins: {', '.join(rep['community_plugins'])}")
        if rep.get("git"):
            print(f"git: {rep['git']['branch_line']} | dirty={rep['git']['dirty_files']} | remote={rep['git']['remote'] or '(none)'}")
        if rep.get("secrets"):
            print("POSSIBLE SECRETS (redacted previews):")
            for s in rep["secrets"][:12]:
                print(f"  [{s['kind']}] {s['file']} -> {s['preview']}")
        for w in rep.get("warnings", []):
            print(f"! {w}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
