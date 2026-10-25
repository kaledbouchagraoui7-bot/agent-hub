#!/usr/bin/env python3
"""Tests for vault_indexer + vault_probe. Stdlib unittest only (no pytest needed)."""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import vault_indexer as vi  # noqa: E402
import vault_probe as vp  # noqa: E402


def write(vault, rel, text):
    p = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


class TmpVault(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="vault-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def index(self, **kw):
        return vi.VaultIndex(self.dir, **kw).scan()


class TestLinkParsing(TmpVault):
    def test_wikilink_alias_heading_block(self):
        write(self.dir, "a.md", "See [[b|the B note]], [[c#Section]], [[d#^blk]].")
        write(self.dir, "b.md", "# B\n")
        write(self.dir, "c.md", "# C\n")
        write(self.dir, "d.md", "# D\ntext ^blk\n")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].outlinks, ["b.md", "c.md", "d.md"])
        self.assertIn("a.md", idx.notes["b.md"].inlinks)

    def test_links_inside_code_are_ignored(self):
        write(self.dir, "a.md", "```\n[[b]]\n```\nand `[[c]]` inline.\nreal: [[d]]")
        write(self.dir, "b.md", "b")
        write(self.dir, "c.md", "c")
        write(self.dir, "d.md", "d")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].outlinks, ["d.md"])

    def test_fenced_block_with_tildes_and_language(self):
        write(self.dir, "a.md", "~~~python\n[[b]]\n~~~\n[[c]]")
        write(self.dir, "b.md", "b")
        write(self.dir, "c.md", "c")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].outlinks, ["c.md"])

    def test_markdown_link_relative_and_embed(self):
        write(self.dir, "notes/a.md", "[alias](../b.md) and ![[img.png]] and [ext](https://x.dev/y)")
        write(self.dir, "b.md", "b")
        idx = self.index()
        n = idx.notes["notes/a.md"]
        self.assertIn("b.md", n.outlinks)
        self.assertEqual(n.external_links, ["https://x.dev/y"])

    def test_unresolved_link_tracked(self):
        write(self.dir, "a.md", "[[does-not-exist]]")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].unresolved, ["does-not-exist"])
        self.assertIn("does-not-exist", idx.unresolved_targets)

    def test_self_link_not_counted_as_edge(self):
        write(self.dir, "a.md", "[[a]]")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].outlinks, [])
        self.assertIn("a.md", idx.orphans)


class TestResolution(TmpVault):
    def test_shortest_path_basename(self):
        write(self.dir, "deep/nested/target.md", "t")
        write(self.dir, "a.md", "[[target]]")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].outlinks, ["deep/nested/target.md"])

    def test_explicit_path_wins_over_basename(self):
        write(self.dir, "x/target.md", "x")
        write(self.dir, "y/target.md", "y")
        write(self.dir, "a.md", "[[y/target]]")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].outlinks, ["y/target.md"])
        self.assertTrue(any("duplicate basename" in w for w in idx.warnings))

    def test_ambiguous_link_prefers_longest_suffix_match(self):
        write(self.dir, "p1/target.md", "1")
        write(self.dir, "p2/target.md", "2")
        write(self.dir, "p2/a.md", "[[p2/target]]")
        idx = self.index()
        self.assertEqual(idx.notes["p2/a.md"].outlinks, ["p2/target.md"])

    def test_md_extension_optional(self):
        write(self.dir, "b.md", "b")
        write(self.dir, "a.md", "[[b.md]]")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].outlinks, ["b.md"])


class TestFrontmatterTags(TmpVault):
    def test_yaml_block_list_and_inline(self):
        write(self.dir, "a.md", "---\ntitle: My Note\ntags:\n  - alpha\n  - beta/nested\naliases: [x, y]\n---\nbody")
        idx = self.index()
        n = idx.notes["a.md"]
        self.assertEqual(n.title, "My Note")
        self.assertEqual(n.frontmatter["aliases"], ["x", "y"])
        self.assertIn("alpha", n.tags)
        self.assertIn("beta/nested", n.tags)

    def test_inline_tags_and_heading_title_fallback(self):
        write(self.dir, "a.md", "# Real Title\n\nsome #tag and #another-tag text\n")
        idx = self.index()
        n = idx.notes["a.md"]
        self.assertEqual(n.title, "Real Title")
        self.assertIn("tag", n.tags)
        self.assertIn("another-tag", n.tags)
        self.assertEqual(n.headings[0], (1, "Real Title"))

    def test_hashtag_not_a_tag(self):
        # Obsidian: a tag must start with a letter/underscore and contain a non-numeric char.
        write(self.dir, "a.md", "issue #1234 and C# and #1st and #1984 are not tags")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].tags, set())

    def test_tags_are_case_insensitive_and_nested(self):
        write(self.dir, "a.md", "#Project/X #project/x #PROJECT/y #y1984")
        write(self.dir, "b.md", "---\ntags: [Project/X]\n---\n")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].tags, {"project/x", "project/y", "y1984"})
        self.assertEqual(idx.notes["b.md"].tags, {"project/x"})
        self.assertEqual(idx.tag_counts["project/x"], 2)

    def test_no_frontmatter_is_safe(self):
        write(self.dir, "a.md", "just text")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].frontmatter, {})


class TestStructure(TmpVault):
    def test_dot_folders_and_excludes_skipped(self):
        write(self.dir, ".obsidian/app.json", "{}")
        write(self.dir, ".trash/old.md", "[[a]]")
        write(self.dir, "node_modules/x.md", "[[a]]")
        write(self.dir, ".hidden/y.md", "[[a]]")
        write(self.dir, "a.md", "a")
        idx = self.index()
        self.assertEqual(sorted(idx.notes), ["a.md"])

    def test_custom_exclude(self):
        write(self.dir, "build/x.md", "[[a]]")
        write(self.dir, "a.md", "a")
        idx = self.index(excludes=vi.DEFAULT_EXCLUDES + ("build",))
        self.assertEqual(sorted(idx.notes), ["a.md"])

    def test_attachments_counted_separately(self):
        write(self.dir, "a.md", "![[p.png]]")
        with open(os.path.join(self.dir, "p.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n")
        idx = self.index()
        self.assertEqual(idx.attachments, ["p.png"])
        self.assertEqual(len(idx.notes), 1)

    def test_orphans_and_stats(self):
        write(self.dir, "hub.md", "[[s1]] [[s2]]")
        write(self.dir, "s1.md", "[[hub]]")
        write(self.dir, "s2.md", "[[hub]]")
        write(self.dir, "lonely.md", "nothing here")
        idx = self.index()
        st = idx.stats()
        self.assertEqual(st["notes"], 4)
        self.assertEqual(st["internal_edges"], 4)
        self.assertEqual(st["orphans"], 1)
        self.assertEqual(st["max_degree"], 4)  # hub: 2 in + 2 out
        self.assertEqual(idx.orphans, ["lonely.md"])

    def test_non_utf8_file_does_not_crash(self):
        with open(os.path.join(self.dir, "bin.md"), "wb") as fh:
            fh.write(b"[[a]]\xff\xfe bad bytes")
        write(self.dir, "a.md", "a")
        idx = self.index()
        self.assertEqual(idx.notes["bin.md"].outlinks, ["a.md"])

    def test_empty_vault(self):
        idx = self.index()
        self.assertEqual(idx.stats()["notes"], 0)
        self.assertEqual(idx.layout(), {})
        html_out = vi.render_html(idx, {}, "empty", 100)
        self.assertIn("<svg", html_out)


class TestLayout(TmpVault):
    def test_deterministic_and_finite(self):
        for i in range(6):
            write(self.dir, f"n{i}.md", f"[[n{(i + 1) % 6}]]")
        idx = self.index()
        p1 = idx.layout(iterations=40)
        p2 = vi.VaultIndex(self.dir).scan().layout(iterations=40)
        self.assertEqual(p1, p2)
        for _, (x, y) in p1.items():
            self.assertTrue(all(abs(v) < 1e6 for v in (x, y)))
            self.assertEqual(x, x)  # not NaN

    def test_disconnected_components_do_not_diverge(self):
        write(self.dir, "a.md", "[[b]]")
        write(self.dir, "b.md", "")
        write(self.dir, "c.md", "[[d]]")
        write(self.dir, "d.md", "")
        idx = self.index()
        pos = idx.layout(iterations=60)
        vals = [v for xy in pos.values() for v in xy]
        self.assertLess(max(abs(v) for v in vals), 1e4)


class TestExports(TmpVault):
    def test_graph_json_shape_and_render_cap(self):
        write(self.dir, "hub.md", "[[a]] [[b]]")
        write(self.dir, "a.md", "# A\n[[hub]]")
        write(self.dir, "b.md", "# B\n[[hub]]")
        idx = self.index()
        pos = idx.layout(iterations=20)
        g = idx.to_graph_json(pos)
        self.assertEqual(g["meta"]["note_count"], 3)
        self.assertEqual(g["meta"]["edge_count"], 4)
        self.assertTrue(g["meta"]["directed"])
        html_out = vi.render_html(idx, pos, "T", 2)
        data = json.loads(html_out.split('type="application/json">')[1].split("</script>")[0].replace("<\\/", "</"))
        self.assertEqual(len(data["nodes"]), 2)          # capped by --max-render
        self.assertEqual(data["meta"]["note_count"], 3)  # meta keeps the true count
        self.assertTrue(all(e["source"] in {n["id"] for n in data["nodes"]} for e in data["edges"]))

    def test_html_escapes_script_breakout(self):
        write(self.dir, "evil.md", "</script><script>alert(1)</script>")
        idx = self.index()
        pos = idx.layout(iterations=1)
        html_out = vi.render_html(idx, pos, "T</script><b>", 10)
        self.assertNotIn("</script><script>alert", html_out.split("<script id=\"graph-data\"")[1].split("</script>")[0])
        self.assertNotIn("T</script>", html_out)

    def test_cli_end_to_end(self):
        write(self.dir, "hub.md", "[[a]]")
        write(self.dir, "a.md", "a")
        out = os.path.join(self.dir, "out")
        rc = vi.main([self.dir, "--out", out, "--layout-iterations", "10"])
        self.assertEqual(rc, 0)
        for f in ("graph.json", "graph.html", "stats.json"):
            self.assertTrue(os.path.isfile(os.path.join(out, f)), f)
        self.assertEqual(vi.main(["/nonexistent/path", "--out", out]), 2)


class TestProbe(TmpVault):
    def test_probe_missing_path(self):
        rep = vp.probe(os.path.join(self.dir, "nope"), 10, False)
        self.assertFalse(rep["ok"])
        self.assertTrue(any("PATH_MISSING" in w for w in rep["warnings"]))

    def test_probe_real_vault(self):
        write(self.dir, ".obsidian/community-plugins.json", '["dataview","obsidian-git"]')
        write(self.dir, "a.md", "---\ntags: [x]\n---\n[[b]] #tag")
        write(self.dir, "b.md", "b")
        rep = vp.probe(self.dir, 10, False)
        self.assertTrue(rep["ok"])
        self.assertTrue(rep["checks"]["is_obsidian_vault"])
        self.assertEqual(rep["checks"]["notes_md"], 2)
        self.assertEqual(rep["community_plugins"], ["dataview", "obsidian-git"])

    def test_probe_detects_secrets_but_never_echoes_them(self):
        # Built from parts on purpose: no credential-shaped literal should sit in a
        # repository, even a fake one, or push-protection scanners reject the commit.
        fake_key = "AKIA" + "IOSFODNN7" + "EXAMPLE" + "1234"
        fake_pem = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"
        write(self.dir, "leak.md", "my api_key = '%s' and %s" % (fake_key, fake_pem))
        rep = vp.probe(self.dir, 10, False)
        kinds = {s["kind"] for s in rep["secrets"]}
        self.assertTrue(kinds)
        blob = json.dumps(rep)
        self.assertNotIn(fake_key, blob)          # the full value must never be echoed
        self.assertNotIn(fake_pem, blob)
        self.assertIn("REDACTED", blob)

    def test_probe_write_test(self):
        write(self.dir, "a.md", "a")
        self.assertTrue(vp.probe(self.dir, 5, True)["checks"]["writable"])
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".datafarm-write-probe.tmp")))

    def test_probe_file_not_dir(self):
        write(self.dir, "a.md", "a")
        rep = vp.probe(os.path.join(self.dir, "a.md"), 5, False)
        self.assertFalse(rep["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestSymlinkSafety(TmpVault):
    def test_symlink_escape_is_not_followed(self):
        outside = tempfile.mkdtemp(prefix="outside-")
        self.addCleanup(shutil.rmtree, outside, True)
        write(outside, "secret.md", "top secret [[a]]")
        write(self.dir, "a.md", "a")
        os.symlink(outside, os.path.join(self.dir, "escape"))
        os.symlink(os.path.join(outside, "secret.md"), os.path.join(self.dir, "link.md"))
        idx = self.index()
        self.assertEqual(sorted(idx.notes), ["a.md"])          # neither dir nor file symlink followed
        rep = vp.probe(self.dir, 10, False)
        self.assertEqual(rep["checks"]["notes_md"], 1)

    def test_symlink_loop_does_not_hang(self):
        write(self.dir, "a.md", "a")
        os.symlink(self.dir, os.path.join(self.dir, "loop"))
        idx = self.index()
        self.assertEqual(sorted(idx.notes), ["a.md"])

    def test_template_placeholders_are_not_links(self):
        write(self.dir, "_templates/t.md", "[[CLM-{{NNN}} {{claim}}]]")
        write(self.dir, "a.md", "[[b]]")
        write(self.dir, "b.md", "b")
        idx = self.index()
        self.assertEqual(idx.unresolved_targets, {})
        self.assertNotIn("_templates/t.md", idx.notes)  # excluded by default


class TestEncodingAndUnicode(TmpVault):
    def test_bom_does_not_break_frontmatter(self):
        p = os.path.join(self.dir, "a.md")
        with open(p, "w", encoding="utf-8-sig", newline="\r\n") as fh:
            fh.write("---\r\ntitle: Tïtle ✓\r\ntags: [日本語, a/b]\r\n---\r\n\r\n# H1\r\n[[b]]\r\n")
        write(self.dir, "b.md", "b")
        idx = self.index()
        n = idx.notes["a.md"]
        self.assertEqual(n.title, "Tïtle ✓")
        self.assertIn("日本語", n.tags)
        self.assertEqual(n.outlinks, ["b.md"])
        self.assertEqual(n.headings, [(1, "H1")])

    def test_unicode_tags_and_numeric_rejection(self):
        write(self.dir, "a.md", "#日本語 #café-x #1984 #1 #a1 _#not")
        idx = self.index()
        self.assertEqual(idx.notes["a.md"].tags, {"日本語", "café-x", "a1"})

    def test_probe_counts_unicode_tags(self):
        write(self.dir, "a.md", "#日本語 and #1984")
        rep = vp.probe(self.dir, 5, False)
        self.assertEqual(rep["checks"]["unique_inline_tags"], 1)
