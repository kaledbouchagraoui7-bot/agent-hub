#!/usr/bin/env python3
"""
vault_indexer.py -- zero-dependency Obsidian vault graph indexer (v0).

Reads a vault directory (plain markdown files, no Obsidian runtime needed),
extracts nodes (notes), edges (wikilinks / markdown links / embeds), tags and
frontmatter, computes graph metrics, and emits:

    <out>/graph.json   machine-readable graph (for the later "data farm" pipeline)
    <out>/graph.html   self-contained interactive graph view (no CDN, no network)
    <out>/stats.json   vault statistics / health report

Design constraints:
  * Python 3.8+ stdlib only. No network. No writes inside the vault (read-only).
  * Deterministic output for identical input (stable sort + seeded layout).
  * Skips .obsidian/, .trash/, .git/, and anything in --exclude.

Usage:
    python3 vault_indexer.py <vault_dir> [--out DIR] [--layout-iterations N]
                             [--exclude GLOB]... [--max-render N]
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import random
import re
import sys
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

__version__ = "0.1.0"

DEFAULT_EXCLUDES = (".obsidian", ".trash", ".git", ".stfolder", ".sync", ".datafarm",
                    ".datafarm-tools", "_templates", "templates", "node_modules", "__pycache__")

# --- Markdown / Obsidian link syntax -------------------------------------------------

_FENCED = re.compile(r"^\s{0,3}(```|~~~)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")

# [[target|alias]]  [[target#heading|alias]]  [[target#^block|alias]]  ![[embed]]
_WIKILINK = re.compile(r"(?P<embed>!)?\[\[(?P<target>[^\[\]\|\n]+?)(?:\|(?P<alias>[^\[\]\n]*))?\]\]")
# [text](target "title")  -- excludes bare urls handled separately
_MDLINK = re.compile(r"(?P<embed>!)?\[(?P<text>[^\]\n]*)\]\(\s*(?P<target><[^>\n]*>|[^\s)]+)(?:\s+\"[^\"]*\")?\s*\)")
# Obsidian tag rules: letters/numbers/underscore/dash/slash, must start with a letter or
# underscore and must contain at least one non-numeric character (#1984 is NOT a tag).
_TAG = re.compile(r"(?<![\w/#])#(?P<tag>[^\W\d][\w\-/]{0,99})", re.UNICODE)
_TAG_NONDIGIT = re.compile(r"\D")
_HEADING = re.compile(r"^\s{0,3}(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_FRONTMATTER_LIST = re.compile(r"^\s*-\s+(?P<val>.+?)\s*$")
_FRONTMATTER_KEY = re.compile(r"^(?P<key>[A-Za-z0-9_\-./]+)\s*:\s*(?P<val>.*?)\s*$")

EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "ftp://", "obsidian://", "file://", "//")


def is_external(target: str) -> bool:
    t = target.strip().lower()
    return t.startswith(EXTERNAL_SCHEMES) or t.startswith("www.")


def strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans so links inside code are not counted."""
    out: List[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.split("\n"):
        m = _FENCED.match(line)
        if m:
            marker = m.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker
                out.append("")
                continue
            if marker == fence_marker:
                in_fence, fence_marker = False, ""
                out.append("")
                continue
        if in_fence:
            out.append("")
        else:
            out.append(_INLINE_CODE.sub("", line))
    return "\n".join(out)


def split_frontmatter(text: str) -> Tuple[Dict[str, object], str]:
    """Very small YAML-frontmatter reader: scalars, inline lists and block lists.

    Deliberately not a full YAML parser (no dependency); unknown constructs are
    kept as raw strings rather than dropped.
    """
    props: Dict[str, object] = {}
    if text.startswith("\ufeff"):          # tolerate a UTF-8 BOM
        text = text[1:]
    if not text.startswith("---"):
        return props, text
    lines = text.split("\n")
    if len(lines) < 2:
        return props, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return props, text

    current_key: Optional[str] = None
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        m_list = _FRONTMATTER_LIST.match(raw)
        if m_list and current_key is not None and raw.startswith((" ", "\t", "-")):
            cur = props.get(current_key)
            if not isinstance(cur, list):
                cur = []
            cur.append(m_list.group("val").strip().strip("\"'"))
            props[current_key] = cur
            continue
        m = _FRONTMATTER_KEY.match(raw)
        if m:
            key, val = m.group("key"), m.group("val")
            current_key = key
            if val == "":
                props[key] = []  # block list follows (or truly empty)
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                props[key] = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()] if inner else []
            else:
                props[key] = val.strip().strip("\"'")
    return props, "\n".join(lines[end + 1 :])


class Note:
    __slots__ = ("path", "basename", "title", "frontmatter", "tags", "headings",
                 "outlinks", "inlinks", "words", "size", "mtime", "external_links", "unresolved")

    def __init__(self, path: str) -> None:
        self.path = path
        self.basename = os.path.splitext(os.path.basename(path))[0]
        self.title = self.basename
        self.frontmatter: Dict[str, object] = {}
        self.tags: Set[str] = set()
        self.headings: List[Tuple[int, str]] = []
        self.outlinks: List[str] = []
        self.inlinks: List[str] = []
        self.words = 0
        self.size = 0
        self.mtime = 0.0
        self.external_links: List[str] = []
        self.unresolved: List[str] = []


class VaultIndex:
    def __init__(self, root: str, excludes: Iterable[str] = DEFAULT_EXCLUDES) -> None:
        self.root = os.path.abspath(root)
        self.excludes = set(excludes)
        self.notes: Dict[str, Note] = {}
        self.by_basename: Dict[str, List[str]] = defaultdict(list)
        self.unresolved_targets: Dict[str, List[str]] = defaultdict(list)
        self.orphans: List[str] = []
        self.attachments: List[str] = []
        self.tag_counts: Dict[str, int] = defaultdict(int)
        self.warnings: List[str] = []

    # ------------------------------------------------------------------ scanning
    def _walk(self) -> Iterable[str]:
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if d not in self.excludes and not d.startswith("."))
            for name in sorted(filenames):
                if name.startswith("."):
                    continue
                if os.path.islink(os.path.join(dirpath, name)):
                    continue
                yield os.path.join(dirpath, name)

    def rel(self, abspath: str) -> str:
        return os.path.relpath(abspath, self.root).replace(os.sep, "/")

    def scan(self) -> "VaultIndex":
        for abspath in self._walk():
            rel = self.rel(abspath)
            if not rel.lower().endswith(".md"):
                self.attachments.append(rel)
                continue
            try:
                with open(abspath, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError as exc:
                self.warnings.append(f"unreadable: {rel} ({exc})")
                continue
            note = self._parse(rel, text)
            try:
                st = os.stat(abspath)
                note.size, note.mtime = st.st_size, st.st_mtime
            except OSError:
                pass
            self.notes[rel] = note
            self.by_basename[note.basename].append(rel)

        for rel in sorted(self.notes):
            self._resolve(self.notes[rel])

        for name, paths in self.by_basename.items():
            if len(paths) > 1:
                self.warnings.append(f"duplicate basename '{name}': {', '.join(sorted(paths))} (link resolution is ambiguous)")

        self.tag_counts = dict(self.tag_counts)
        self.orphans = sorted(r for r, n in self.notes.items() if not n.inlinks and not n.outlinks)
        return self

    def _parse(self, rel: str, text: str) -> Note:
        note = Note(rel)
        props, body = split_frontmatter(text)
        note.frontmatter = props

        fm_title = props.get("title")
        if isinstance(fm_title, str) and fm_title.strip():
            note.title = fm_title.strip()

        # frontmatter tags (Obsidian supports a `tags` property)
        fm_tags = props.get("tags")
        if isinstance(fm_tags, str):
            fm_tags = [t for t in re.split(r"[,\s]+", fm_tags) if t]
        for t in fm_tags or []:
            tag = str(t).strip().lstrip("#").lower()
            if tag and _TAG_NONDIGIT.search(tag):
                note.tags.add(tag)

        clean = strip_code(body)
        note.words = len(clean.split())

        for line in clean.split("\n"):
            hm = _HEADING.match(line)
            if hm:
                note.headings.append((len(hm.group("hashes")), hm.group("title").strip()))
                if not fm_title and len(hm.group("hashes")) == 1 and note.title == note.basename:
                    note.title = hm.group("title").strip()

        raw_targets: List[str] = []
        for m in _WIKILINK.finditer(clean):
            raw_targets.append(m.group("target"))
        for m in _MDLINK.finditer(clean):
            raw_targets.append(m.group("target").strip("<>"))

        seen_inline: Set[str] = set()
        for target in raw_targets:
            t = target.strip()
            if not t:
                continue
            if is_external(t):
                note.external_links.append(t)
                continue
            base = re.split(r"[#^]", t, maxsplit=1)[0].strip()
            if not base:
                continue  # pure heading/block reference to self
            if "{{" in base:
                continue  # Templater/core-template placeholder, not a real link
            if base in seen_inline:
                continue
            seen_inline.add(base)
            note.outlinks.append(base)

        for m in _TAG.finditer(clean):
            tag = m.group("tag").lower()          # Obsidian tags are case-insensitive
            if _TAG_NONDIGIT.search(tag):         # Obsidian: tag must contain a non-numeric char (#1984 is not a tag)
                note.tags.add(tag)

        for tag in note.tags:
            self.tag_counts[tag] += 1
        return note

    # ----------------------------------------------------------------- resolving
    def _resolve(self, note: Note) -> None:
        resolved: List[str] = []
        for target in note.outlinks:
            hit = self.resolve_target(target)
            if hit is None:
                note.unresolved.append(target)
                self.unresolved_targets[target].append(note.path)
            elif hit != note.path:
                resolved.append(hit)
                self.notes[hit].inlinks.append(note.path)
        note.outlinks = sorted(set(resolved))
        note.inlinks = sorted(set(note.inlinks))

    def resolve_target(self, target: str) -> Optional[str]:
        """Mimic Obsidian's shortest-path link resolution, with path fallbacks."""
        t = target.strip().strip("/")
        if not t:
            return None
        t_noext = t[:-3] if t.lower().endswith(".md") else t
        if t in self.notes:
            return t
        if t_noext in self.notes:
            return t_noext
        if t_noext + ".md" in self.notes:
            return t_noext + ".md"
        base = os.path.basename(t_noext)
        cands = self.by_basename.get(base) or []
        if len(cands) == 1:
            return cands[0]
        if len(cands) > 1:
            # ambiguous: prefer a candidate that shares the longest path suffix
            parts = t_noext.split("/")
            best, best_score = None, -1
            for c in cands:
                cp = c.split("/")
                score = 0
                for a, b in zip(reversed(parts), reversed(cp)):
                    if a != b:
                        break
                    score += 1
                if score > best_score:
                    best, best_score = c, score
            return best
        return None

    # -------------------------------------------------------------------- layout
    def _seed_positions(self, nodes: List[str], rng: random.Random,
                        prior: Optional[Dict[str, Tuple[float, float]]] = None) -> List[List[float]]:
        """Seed: reuse cached coords when available, else BFS radial rings from the
        highest-degree nodes. Radial seeding converges in a handful of iterations,
        unlike a uniform random start."""
        n = len(nodes)
        idx = {p: i for i, p in enumerate(nodes)}
        adj: Dict[int, List[int]] = defaultdict(list)
        for a in nodes:
            for b in self.notes[a].outlinks:
                if b in idx:
                    adj[idx[a]].append(idx[b])
                    adj[idx[b]].append(idx[a])
        pos: List[List[float]] = [[0.0, 0.0] for _ in range(n)]
        dist = [-1] * n
        order = sorted(range(n), key=lambda i: (-len(adj[i]), nodes[i]))
        ring_r = math.sqrt(max(1.0, n)) * 3.0
        placed = 0
        for seed in order:
            if dist[seed] != -1:
                continue
            stack = [seed]
            dist[seed] = 0
            counts = defaultdict(int)
            while stack:
                cur = stack.pop()
                d = dist[cur]
                ring = max(1, d)
                slot = counts[d]
                counts[d] += 1
                per_ring = max(6, int(2 * math.pi * ring * 1.6))
                ang = 2 * math.pi * (slot % per_ring) / per_ring + d * 0.7
                rad = ring * ring_r * 0.35
                if prior and nodes[cur] in prior:
                    px, py = prior[nodes[cur]]
                    pos[cur] = [px, py]
                else:
                    pos[cur] = [rad * math.cos(ang), rad * math.sin(ang)]
                pos[cur][0] += rng.uniform(-0.5, 0.5)
                pos[cur][1] += rng.uniform(-0.5, 0.5)
                placed += 1
                for nb in adj[cur]:
                    if dist[nb] == -1:
                        dist[nb] = d + 1
                        stack.append(nb)
        return pos

    def layout(self, iterations: Optional[int] = None, seed: int = 1337, theta: float = 0.9,
               prior: Optional[Dict[str, Tuple[float, float]]] = None) -> Dict[str, Tuple[float, float]]:
        """Deterministic force-directed layout with Barnes-Hut (O(n log n)) repulsion.

        `prior` warm-starts from a previous layout so incremental rebuilds are cheap.
        """
        nodes = sorted(self.notes)
        n = len(nodes)
        if n == 0:
            return {}
        if n == 1:
            return {nodes[0]: (0.0, 0.0)}
        if iterations is None:
            iterations = 150 if n <= 2000 else 90
        rng = random.Random(seed)
        idx = {p: i for i, p in enumerate(nodes)}
        edges = [(idx[a], idx[b]) for a in nodes for b in self.notes[a].outlinks if b in idx]
        degree = [0] * n
        for a, b in edges:
            degree[a] += 1
            degree[b] += 1

        pos = self._seed_positions(nodes, rng, prior)
        area = max(1.0, float(n)) * 80.0
        k = math.sqrt(area / n) * 2.2
        k2 = k * k
        temp0 = math.sqrt(area) * 0.12
        theta2 = theta * theta

        for it in range(iterations):
            # ---- build Barnes-Hut quadtree over current positions ----
            minx = min(p[0] for p in pos); maxx = max(p[0] for p in pos)
            miny = min(p[1] for p in pos); maxy = max(p[1] for p in pos)
            span = max(maxx - minx, maxy - miny, 1e-6) * 1.02
            cx = (minx + maxx) / 2.0; cy = (miny + maxy) / 2.0
            cap = 8 * n + 16
            ch = [[-1, -1, -1, -1] for _ in range(cap)]
            cnt = [0] * cap
            comx = [0.0] * cap
            comy = [0.0] * cap
            half = [span / 2.0] * cap
            node_cx = [cx] * cap
            node_cy = [cy] * cap
            nnodes = 1
            max_depth = 32
            for i in range(n):
                px, py = pos[i]
                cur = 0
                depth = 0
                while True:
                    cnt[cur] += 1
                    comx[cur] += (px - comx[cur]) / cnt[cur]
                    comy[cur] += (py - comy[cur]) / cnt[cur]
                    # stop subdividing on depth cap, degenerate cell, or pool exhaustion
                    if depth >= max_depth or half[cur] < 1e-9 or nnodes >= cap - 4:
                        break
                    qx = 0 if px < node_cx[cur] else 1
                    qy = 0 if py < node_cy[cur] else 1
                    slot = qy * 2 + qx
                    child = ch[cur][slot]
                    if child == -1:
                        child = nnodes
                        nnodes += 1
                        ch[cur][slot] = child
                        half[child] = half[cur] / 2.0
                        node_cx[child] = node_cx[cur] + (half[cur] / 2.0 if qx else -half[cur] / 2.0)
                        node_cy[child] = node_cy[cur] + (half[cur] / 2.0 if qy else -half[cur] / 2.0)
                    cur = child
                    depth += 1

            # ---- repulsion via quadtree traversal ----
            disp = [[0.0, 0.0] for _ in range(n)]
            stack = [0] * 64
            for i in range(n):
                xi = pos[i][0]; yi = pos[i][1]
                dxs = 0.0; dys = 0.0
                sp = 1
                stack[0] = 0
                while sp:
                    sp -= 1
                    cur = stack[sp]
                    c = cnt[cur]
                    if c == 0:
                        continue
                    ddx = xi - comx[cur]; ddy = yi - comy[cur]
                    d2 = ddx * ddx + ddy * ddy
                    w = half[cur] * 2.0
                    if c > 1 and (w * w) > theta2 * d2:
                        ch_cur = ch[cur]
                        if sp + 4 > len(stack):
                            stack.extend([0] * (sp + 8))
                        for slot in range(4):
                            kid = ch_cur[slot]
                            if kid != -1 and cnt[kid]:
                                stack[sp] = kid
                                sp += 1
                        continue
                    if d2 < 1e-6:
                        # leaf cell containing this same point: jitter, then clamp below
                        ddx = rng.uniform(-1e-3, 1e-3); ddy = rng.uniform(-1e-3, 1e-3)
                        d2 = max(ddx * ddx + ddy * ddy, 1e-6)
                    d = math.sqrt(d2)
                    f = (k2 * c) / d2      # repulsive force magnitude / d  -> unit*f
                    dxs += ddx * f; dys += ddy * f
                disp[i][0] = dxs; disp[i][1] = dys

            # ---- attraction along edges ----
            for a, b in edges:
                ddx = pos[a][0] - pos[b][0]; ddy = pos[a][1] - pos[b][1]
                d = math.sqrt(ddx * ddx + ddy * ddy) or 1e-6
                f = (d * d) / k
                ux = ddx / d * f; uy = ddy / d * f
                disp[a][0] -= ux; disp[a][1] -= uy
                disp[b][0] += ux; disp[b][1] += uy

            # ---- mild gravity keeps components from drifting apart ----
            grav = 0.015 * k
            for i in range(n):
                xi = pos[i][0]; yi = pos[i][1]
                d = math.sqrt(xi * xi + yi * yi) or 1e-6
                g = grav * (1 + degree[i] * 0.15)
                disp[i][0] -= xi / d * g
                disp[i][1] -= yi / d * g

            # ---- integrate with linear cooling ----
            temp = temp0 * (1.0 - it / float(iterations))
            if temp < 1e-4:
                temp = 1e-4
            for i in range(n):
                dx = disp[i][0]; dy = disp[i][1]
                d = math.sqrt(dx * dx + dy * dy) or 1e-6
                sc = temp / d if d > temp else 1.0
                pos[i][0] += dx * sc
                pos[i][1] += dy * sc

        self._resolve_overlaps(pos, k * 0.45, passes=3)
        return {nodes[i]: (round(pos[i][0], 3), round(pos[i][1], 3)) for i in range(n)}

    @staticmethod
    def _resolve_overlaps(pos: List[List[float]], min_sep: float, passes: int = 3) -> None:
        """Grid-bucketed post-pass that pushes overlapping nodes apart.

        Force-directed layouts happily let unrelated nodes sit on top of each
        other; this makes labels readable. O(n) per pass in practice.
        """
        n = len(pos)
        if n < 2 or min_sep <= 0:
            return
        cell = max(min_sep, 1e-6)
        for _ in range(passes):
            buckets: Dict[Tuple[int, int], List[int]] = defaultdict(list)
            for i, (x, y) in enumerate(pos):
                buckets[(int(x // cell), int(y // cell))].append(i)
            for i in range(n):
                xi, yi = pos[i]
                gx, gy = int(xi // cell), int(yi // cell)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for j in buckets.get((gx + dx, gy + dy), ()):
                            if j <= i:
                                continue
                            ddx = xi - pos[j][0]
                            ddy = yi - pos[j][1]
                            d2 = ddx * ddx + ddy * ddy
                            if d2 >= min_sep * min_sep:
                                continue
                            d = math.sqrt(d2)
                            if d < 1e-9:
                                ddx, ddy, d = 1.0, 0.0, 1.0
                            push = (min_sep - d) * 0.5
                            ux, uy = ddx / d * push, ddy / d * push
                            pos[i][0] += ux; pos[i][1] += uy
                            pos[j][0] -= ux; pos[j][1] -= uy
                            xi, yi = pos[i]

    # ------------------------------------------------------------------- exports
    def to_graph_json(self, positions: Dict[str, Tuple[float, float]]) -> dict:
        nodes, edges = [], []
        for rel in sorted(self.notes):
            n = self.notes[rel]
            x, y = positions.get(rel, (0.0, 0.0))
            nodes.append({
                "id": rel,
                "title": n.title,
                "folder": os.path.dirname(rel),
                "tags": sorted(n.tags),
                "degree": len(n.inlinks) + len(n.outlinks),
                "in": len(n.inlinks),
                "out": len(n.outlinks),
                "words": n.words,
                "x": x, "y": y,
            })
            for tgt in n.outlinks:
                edges.append({"source": rel, "target": tgt})
        return {
            "meta": {"version": __version__, "root": self.root, "directed": True,
                     "note_count": len(nodes), "edge_count": len(edges)},
            "nodes": nodes,
            "edges": edges,
            "unresolved": {t: sorted(set(srcs)) for t, srcs in sorted(self.unresolved_targets.items())},
        }

    def stats(self) -> dict:
        notes = list(self.notes.values())
        deg = sorted((len(n.inlinks) + len(n.outlinks)) for n in notes)
        n = len(deg)
        hubs = sorted(notes, key=lambda x: (len(x.inlinks) + len(x.outlinks)), reverse=True)[:10]
        density = 0.0
        if n > 1:
            density = sum(len(x.outlinks) for x in notes) / float(n * (n - 1))
        return {
            "notes": n,
            "attachments": len(self.attachments),
            "internal_edges": sum(len(x.outlinks) for x in notes),
            "external_links": sum(len(x.external_links) for x in notes),
            "unresolved_links": sum(len(v) for v in self.unresolved_targets.values()),
            "unresolved_unique_targets": len(self.unresolved_targets),
            "orphans": len(self.orphans),
            "orphan_ratio": round(len(self.orphans) / n, 4) if n else 0.0,
            "tags": len(self.tag_counts),
            "avg_degree": round(sum(deg) / n, 3) if n else 0.0,
            "median_degree": deg[n // 2] if n else 0,
            "max_degree": deg[-1] if n else 0,
            "density": round(density, 5),
            "words": sum(x.words for x in notes),
            "bytes": sum(x.size for x in notes),
            "top_hubs": [{"id": h.path, "degree": len(h.inlinks) + len(h.outlinks)} for h in hubs],
            "duplicate_basenames": sorted(k for k, v in self.by_basename.items() if len(v) > 1),
            "warnings": self.warnings[:50],
        }


# --------------------------------------------------------------------- rendering

_HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:dark;--bg:#12141a;--fg:#e6e8ee;--mut:#98a0b3;--acc:#7aa2f7;--edge:#3a4256}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{display:flex;gap:16px;align-items:center;flex-wrap:wrap;padding:10px 14px;border-bottom:1px solid #232838;background:#151922}
h1{font-size:14px;margin:0;font-weight:600;letter-spacing:.02em}
.stats{color:var(--mut);font-size:12px}
input,select{background:#0e1119;border:1px solid #2a3145;color:var(--fg);border-radius:6px;padding:5px 8px;font:inherit}
input{width:220px}
.wrap{display:flex;height:calc(100vh - 46px)}
#cv{flex:1;cursor:grab;touch-action:none}
#cv.drag{cursor:grabbing}
aside{width:300px;border-left:1px solid #232838;padding:12px;overflow:auto;background:#151922}
aside h2{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:14px 0 6px}
aside h2:first-child{margin-top:0}
.pill{display:inline-block;background:#0e1119;border:1px solid #2a3145;border-radius:999px;padding:2px 8px;margin:0 4px 4px 0;cursor:pointer}
.pill:hover{border-color:var(--acc)}
.legend span{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}
#detail{word-break:break-word}
#detail a{color:var(--acc);text-decoration:none}
.mut{color:var(--mut)}
button{background:#0e1119;border:1px solid #2a3145;color:var(--fg);border-radius:6px;padding:5px 9px;cursor:pointer;font:inherit}
button:hover{border-color:var(--acc)}
svg text{font:10px ui-sans-serif,system-ui,sans-serif;fill:#c7cede;pointer-events:none}
</style></head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="stats">__SUBTITLE__</div>
  <input id="q" type="search" placeholder="filter nodes (substring or #tag)" autocomplete="off">
  <select id="folder"><option value="">all folders</option></select>
  <button id="reset">reset view</button>
</header>
<div class="wrap">
  <svg id="cv" xmlns="http://www.w3.org/2000/svg"></svg>
  <aside>
    <h2>Selection</h2><div id="detail" class="mut">Click a node.</div>
    <h2>Folders</h2><div id="folders" class="legend"></div>
    <h2>Top tags</h2><div id="tags"></div>
  </aside>
</div>
<script id="graph-data" type="application/json">__DATA__</script>
<script>
(function(){
"use strict";
var DATA=JSON.parse(document.getElementById('graph-data').textContent);
var svg=document.getElementById('cv'),NS='http://www.w3.org/2000/svg';
var nodes=DATA.nodes,edges=DATA.edges;
var byId={};nodes.forEach(function(n){byId[n.id]=n;});
var folders=[],fidx={},palette=['#7aa2f7','#9ece6a','#e0af68','#f7768e','#bb9af7','#7dcfff','#ff9e64','#73daca','#c0caf5','#a9b1d6'];
nodes.forEach(function(n){var f=n.folder||'(root)';if(!(f in fidx)){fidx[f]=folders.length;folders.push(f);}});
function color(n){return palette[fidx[n.folder||'(root)']%palette.length];}

// viewport bounds
var minX=1e9,minY=1e9,maxX=-1e9,maxY=-1e9;
nodes.forEach(function(n){minX=Math.min(minX,n.x);maxX=Math.max(maxX,n.x);minY=Math.min(minY,n.y);maxY=Math.max(maxY,n.y);});
if(!isFinite(minX)){minX=-1;maxX=1;minY=-1;maxY=1;}
var W=Math.max(1,maxX-minX),H=Math.max(1,maxY-minY);
var view={k:1,x:0,y:0};
var g=document.createElementNS(NS,'g');svg.appendChild(g);
var gE=document.createElementNS(NS,'g'),gN=document.createElementNS(NS,'g'),gT=document.createElementNS(NS,'g');
g.appendChild(gE);g.appendChild(gN);g.appendChild(gT);

var maxDeg=Math.max(1,Math.max.apply(null,nodes.map(function(n){return n.degree;})));
var el={},nel={},tel={},lineEls=[];
edges.forEach(function(e){
  var a=byId[e.source],b=byId[e.target];if(!a||!b)return;
  var l=document.createElementNS(NS,'line');
  l.setAttribute('x1',a.x);l.setAttribute('y1',a.y);l.setAttribute('x2',b.x);l.setAttribute('y2',b.y);
  l.setAttribute('stroke','#3a4256');l.setAttribute('stroke-width',0.7);l.setAttribute('opacity',0.75);
  gE.appendChild(l);lineEls.push([l,e.source,e.target]);
});
nodes.forEach(function(n){
  var r=2.2+7*Math.sqrt(n.degree/maxDeg);n.r=r;
  var c=document.createElementNS(NS,'circle');
  c.setAttribute('cx',n.x);c.setAttribute('cy',n.y);c.setAttribute('r',r);
  c.setAttribute('fill',color(n));c.setAttribute('stroke','#12141a');c.setAttribute('stroke-width',0.5);
  c.style.cursor='pointer';gN.appendChild(c);nel[n.id]=c;
  if(n.degree>=maxDeg*0.55||n.degree>8){
    var t=document.createElementNS(NS,'text');
    t.setAttribute('x',n.x+r+1.6);t.setAttribute('y',n.y+3);
    t.textContent=n.title.length>28?n.title.slice(0,27)+'…':n.title;
    gT.appendChild(t);tel[n.id]=t;
  }
  c.addEventListener('click',function(ev){ev.stopPropagation();select(n.id);});
});

function apply(){g.setAttribute('transform','translate('+view.x+','+view.y+') scale('+view.k+')');}
function fit(){
  var w=svg.clientWidth||900,h=svg.clientHeight||600;
  var k=Math.min(w/(W*1.15),h/(H*1.15));if(!isFinite(k)||k<=0)k=1;
  view.k=k;view.x=w/2-k*(minX+maxX)/2;view.y=h/2-k*(minY+maxY)/2;apply();
}
var drag=null;
svg.addEventListener('pointerdown',function(e){drag={x:e.clientX,y:e.clientY,vx:view.x,vy:view.y};svg.classList.add('drag');svg.setPointerCapture(e.pointerId);});
svg.addEventListener('pointermove',function(e){if(!drag)return;view.x=drag.vx+(e.clientX-drag.x);view.y=drag.vy+(e.clientY-drag.y);apply();});
svg.addEventListener('pointerup',function(e){drag=null;svg.classList.remove('drag');});
svg.addEventListener('wheel',function(e){
  e.preventDefault();
  var rect=svg.getBoundingClientRect(),mx=e.clientX-rect.left,my=e.clientY-rect.top;
  var f=Math.exp(-e.deltaY*0.0016),nk=Math.min(40,Math.max(0.05,view.k*f));
  view.x=mx-(mx-view.x)*(nk/view.k);view.y=my-(my-view.y)*(nk/view.k);view.k=nk;apply();
},{passive:false});
svg.addEventListener('click',function(){select(null);});

var selected=null;
function select(id){
  selected=id;
  var nb={};
  if(id){edges.forEach(function(e){if(e.source===id)nb[e.target]=1;if(e.target===id)nb[e.source]=1;});nb[id]=1;}
  nodes.forEach(function(n){
    var c=nel[n.id];if(!c)return;
    var on=!id||nb[n.id]||pass(n);
    c.setAttribute('opacity',on?1:0.09);
    c.setAttribute('stroke',n.id===id?'#ffffff':'#12141a');
    c.setAttribute('stroke-width',n.id===id?1.6:0.5);
    if(tel[n.id])tel[n.id].setAttribute('opacity',on?1:0.05);
  });
  lineEls.forEach(function(L){
    var l=L[0],s=L[1],t=L[2];
    var on=!id?(pass(byId[s])&&pass(byId[t])):(s===id||t===id);
    l.setAttribute('opacity',on?0.85:0.04);
    l.setAttribute('stroke',(s===id||t===id)?'#7aa2f7':'#3a4256');
  });
  var d=document.getElementById('detail');
  if(!id){d.className='mut';d.textContent='Click a node.';return;}
  var n=byId[id];d.className='';
  var outs=DATA.edges.filter(function(e){return e.source===id;}).map(function(e){return e.target;});
  var ins=DATA.edges.filter(function(e){return e.target===id;}).map(function(e){return e.source;});
  d.innerHTML='<strong>'+esc(n.title)+'</strong><div class="mut">'+esc(n.id)+'</div>'+
    '<div>'+n.degree+' links · '+n.in+' in / '+n.out+' out · '+n.words+' words</div>'+
    (n.tags.length?'<div>'+n.tags.map(function(t){return '<span class="pill">#'+esc(t)+'</span>';}).join('')+'</div>':'')+
    '<h2>Links out ('+outs.length+')</h2>'+list(outs)+'<h2>Backlinks ('+ins.length+')</h2>'+list(ins);
  d.querySelectorAll('a[data-id]').forEach(function(a){a.addEventListener('click',function(){select(a.getAttribute('data-id'));});});
}
function list(arr){if(!arr.length)return '<div class="mut">none</div>';
  return '<div>'+arr.map(function(p){return '<a href="#" data-id="'+esc(p)+'">'+esc(byId[p]?byId[p].title:p)+'</a>';}).join('<br>')+'</div>';}
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c];});}

var q='',qf='';
function pass(n){
  if(!n)return false;
  if(qf&&(n.folder||'(root)')!==qf)return false;
  if(!q)return true;
  if(q[0]==='#')return n.tags.indexOf(q.slice(1))>=0;
  return (n.title+' '+n.id).toLowerCase().indexOf(q)>=0;
}
document.getElementById('q').addEventListener('input',function(e){q=e.target.value.trim().toLowerCase();select(selected);});
var fsel=document.getElementById('folder');
folders.slice().sort().forEach(function(f){var o=document.createElement('option');o.value=(f==='(root)'?'':f);o.textContent=f;fsel.appendChild(o);});
fsel.addEventListener('change',function(){qf=fsel.value;select(selected);});
document.getElementById('reset').addEventListener('click',function(){q='';qf='';document.getElementById('q').value='';fsel.value='';selected=null;select(null);fit();});

var fd=document.getElementById('folders');
folders.slice().sort().forEach(function(f){
  var cnt=nodes.filter(function(n){return (n.folder||'(root)')===f;}).length;
  var s=document.createElement('span');s.className='pill';
  s.innerHTML='<span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:'+palette[fidx[f]%palette.length]+';margin-right:6px"></span>'+esc(f)+' <span class="mut">'+cnt+'</span>';
  s.addEventListener('click',function(){fsel.value=(f==='(root)'?'':f);qf=fsel.value;select(selected);});
  fd.appendChild(s);
});
var td=document.getElementById('tags');
Object.keys(DATA.tag_counts||{}).sort(function(a,b){return DATA.tag_counts[b]-DATA.tag_counts[a];}).slice(0,24).forEach(function(t){
  var s=document.createElement('span');s.className='pill';s.textContent='#'+t+' '+DATA.tag_counts[t];
  s.addEventListener('click',function(){document.getElementById('q').value='#'+t;q='#'+t.toLowerCase();select(selected);});
  td.appendChild(s);
});
if(!td.children.length)td.innerHTML='<span class="mut">no tags</span>';
fit();select(null);
})();
</script>
</body></html>
"""


def render_html(index: VaultIndex, positions: Dict[str, Tuple[float, float]], title: str, max_render: int) -> str:
    graph = index.to_graph_json(positions)
    note_count = graph["meta"]["note_count"]
    truncated = ""
    if note_count > max_render:
        keep = sorted(graph["nodes"], key=lambda n: (-n["degree"], n["id"]))[:max_render]
        keep_ids = {n["id"] for n in keep}
        graph["nodes"] = sorted(keep, key=lambda n: n["id"])
        graph["edges"] = [e for e in graph["edges"] if e["source"] in keep_ids and e["target"] in keep_ids]
        truncated = f" (showing top {max_render} of {note_count} by degree)"
    graph["tag_counts"] = dict(sorted(index.tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:60])
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    sub = (f"{graph['meta']['note_count']} notes · {len(graph['edges'])} edges · "
           f"{index.stats()['orphans']} orphans · {index.stats()['unresolved_links']} unresolved{truncated}")
    return (_HTML_TEMPLATE
            .replace("__TITLE__", html.escape(title))
            .replace("__SUBTITLE__", html.escape(sub))
            .replace("__DATA__", payload))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Index an Obsidian vault into a graph (zero dependencies).")
    ap.add_argument("vault", help="path to the vault root (the folder containing your notes)")
    ap.add_argument("--out", default=".datafarm", help="output directory (default: ./.datafarm)")
    ap.add_argument("--layout-iterations", type=int, default=None,
                    help="force-directed iterations (default: auto, 150 for <=2000 notes)")
    ap.add_argument("--reuse-layout", action="store_true",
                    help="warm-start from an existing graph.json in --out (fast incremental rebuilds)")
    ap.add_argument("--json-only", "--no-html", dest="json_only_flag", action="store_true",
                    help="skip HTML rendering")
    ap.add_argument("--max-render", type=int, default=4000, help="cap nodes drawn in graph.html")
    ap.add_argument("--exclude", action="append", default=[], help="extra folder name to skip (repeatable)")
    ap.add_argument("--title", default=None)
    args = ap.parse_args(argv)

    if not os.path.isdir(args.vault):
        print(f"error: not a directory: {args.vault}", file=sys.stderr)
        return 2

    excludes = set(DEFAULT_EXCLUDES) | set(args.exclude)
    index = VaultIndex(args.vault, excludes).scan()

    prior = None
    prev = os.path.join(args.out, "graph.json")
    if args.reuse_layout and os.path.isfile(prev):
        try:
            with open(prev, "r", encoding="utf-8") as fh:
                old = json.load(fh)
            prior = {nd["id"]: (float(nd["x"]), float(nd["y"])) for nd in old.get("nodes", [])}
            print(f"warm-start: reusing {len(prior)} cached positions from {prev}", file=sys.stderr)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"warning: could not reuse layout ({exc}); computing from scratch", file=sys.stderr)
    positions = index.layout(iterations=args.layout_iterations, prior=prior)

    os.makedirs(args.out, exist_ok=True)
    graph = index.to_graph_json(positions)
    stats = index.stats()

    with open(os.path.join(args.out, "graph.json"), "w", encoding="utf-8") as fh:
        json.dump(graph, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)
    if not args.json_only_flag:
        title = args.title or f"{os.path.basename(os.path.abspath(args.vault))} · data farm graph"
        with open(os.path.join(args.out, "graph.html"), "w", encoding="utf-8") as fh:
            fh.write(render_html(index, positions, title, args.max_render))

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"\nwrote: {os.path.abspath(args.out)}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
