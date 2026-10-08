"""Test useful graph behavior without asserting documentation wording."""
import tempfile
import unittest
from pathlib import Path
from context_map import build_graph, find_names, outline, outline_text, select

class ContextMapTests(unittest.TestCase):
    def test_imports_and_reverse_impact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = {"a.py": "from b import thing\n", "b.py": "thing = 1\n",
                      "a.ts": 'import {x} from "./b.js";\n', "b.ts": "export const x=1;\n",
                      "rule.md": "Implementation lives in b.py\n"}
            for p, c in source.items():
                (root/p).write_text(c)
            g = build_graph(root, list(source))
            result = select(g, ["b.py"], 1)
            self.assertEqual({n["path"] for n in result["nodes"]}, {"a.py", "b.py", "rule.md"})
            self.assertTrue(any(e["source"] == "a.ts" and e["target"] == "b.ts" for e in g["edges"]))

    def test_fingerprint_changes_with_working_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/"a.py").write_text("x=1\n")
            before = build_graph(root, ["a.py"])["workingTreeFingerprint"]
            (root/"a.py").write_text("x=2\n")
            self.assertNotEqual(before, build_graph(root, ["a.py"])["workingTreeFingerprint"])

    def test_excluded_and_missing_sources_are_not_silently_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/".env.json").write_text('{"key":"private"}')
            self.assertEqual(build_graph(root, [".env.json"])["nodes"], [])
            with self.assertRaises(ValueError):
                select(build_graph(root, []), ["absent.py"], 1)

ROOT = Path(__file__).resolve().parents[1]


def spans(result):
    return {e["qualname"]: (e["startLine"], e["endLine"], e["kind"]) for e in result["entries"]}


class OutlineTests(unittest.TestCase):
    """CM1-1: symbols and sections with line spans; expected lines counted by hand."""

    def test_python_functions_classes_methods_decorators_and_constants(self):
        text = ("LIMIT = 3\n"          # 1
                "\n"                   # 2
                "@decorate\n"          # 3
                "def top(a):\n"        # 4
                "    return a\n"       # 5
                "\n"                   # 6
                "class Box:\n"         # 7
                "    def open(self):\n"  # 8
                "        pass\n"       # 9
                "\n"                   # 10
                "    async def shut(self):\n"  # 11
                "        pass\n")      # 12
        self.assertEqual(spans(outline_text("m.py", text)), {
            "LIMIT": (1, 1, "constant"), "top": (3, 5, "function"), "Box": (7, 12, "class"),
            "Box.open": (8, 9, "method"), "Box.shut": (11, 12, "method")})

    def test_typescript_ignores_braces_in_strings_templates_and_comments(self):
        text = ("// a } brace in a comment\n"                       # 1
                "export interface Point {\n"                         # 2
                "  x: number;\n"                                     # 3
                "}\n"                                                # 4
                "export const LABEL = \"{ not a block\";\n"          # 5
                "export class Engine {\n"                            # 6
                "  private step(n: number): string {\n"              # 7
                "    const s = `value ${n} } done`;\n"               # 8
                "    /* } */ return s;\n"                            # 9
                "  }\n"                                              # 10
                "  run(): void {\n"                                  # 11
                "    if (true) { this.step(1); }\n"                  # 12
                "  }\n"                                              # 13
                "}\n"                                                # 14
                "export function helper(): number {\n"               # 15
                "  return 1;\n"                                      # 16
                "}\n")                                               # 17
        self.assertEqual(spans(outline_text("e.ts", text)), {
            "Point": (2, 4, "interface"), "LABEL": (5, 5, "constant"), "Engine": (6, 14, "class"),
            "Engine.step": (7, 10, "method"), "Engine.run": (11, 13, "method"), "helper": (15, 17, "function")})

    def test_markdown_sections_span_to_next_same_or_higher_heading_and_skip_fences(self):
        text = ("# Doc\n"        # 1
                "## 1. First\n"  # 2
                "text\n"         # 3
                "```\n"          # 4
                "# not a heading\n"  # 5
                "```\n"          # 6
                "### 1.1 Sub\n"  # 7
                "more\n"         # 8
                "## 2. Second\n"  # 9
                "end\n")         # 10
        result = spans(outline_text("d.md", text))
        self.assertEqual(result["Doc"], (1, 10, "h1"))
        self.assertEqual(result["Doc > 1. First"], (2, 8, "h2"))
        self.assertEqual(result["Doc > 1. First > 1.1 Sub"], (7, 8, "h3"))
        self.assertEqual(result["Doc > 2. Second"], (9, 10, "h2"))
        self.assertNotIn("Doc > not a heading", result)

    def test_json_top_level_keys_and_named_errors(self):
        text = '{\n  "a": 1,\n  "b": {\n    "c": "x, y"\n  },\n  "d": [1, 2]\n}\n'
        self.assertEqual(spans(outline_text("f.json", text)), {"a": (2, 2, "key"), "b": (3, 5, "key"), "d": (6, 6, "key")})
        self.assertEqual(outline_text("list.json", "[1, 2]")["entries"], [])
        self.assertTrue(outline_text("bad.json", "{")["error"].startswith("JSONDecodeError"))
        self.assertTrue(outline_text("bad.py", "def (:\n")["error"].startswith("SyntaxError"))

    def test_repository_spans_match_the_declared_expectations(self):
        result = outline(ROOT, ["executor/src/model.ts", "research/bot_research/classification.py",
                                "docs/STATE_TRANSITIONS_v1.2.0.md"])
        files = {f["path"]: f for f in result["files"]}
        model = {e["name"]: e for e in files["executor/src/model.ts"]["entries"]}
        self.assertEqual(model["evaluateRecovery"]["startLine"], 894)
        self.assertEqual(files["research/bot_research/classification.py"]["entries"][[
            e["name"] for e in files["research/bot_research/classification.py"]["entries"]].index("classify_class_on")]["startLine"], 145)
        section = next(e for e in files["docs/STATE_TRANSITIONS_v1.2.0.md"]["entries"] if e["name"].startswith("7."))
        self.assertEqual((section["startLine"], section["endLine"]), (150, 467))
        for file in result["files"]:
            self.assertNotIn("error", file)
            for entry in file["entries"]:
                self.assertTrue(1 <= entry["startLine"] <= entry["endLine"] <= file["lines"], entry)


class FindTests(unittest.TestCase):
    """CM1-2: definitions and whole-token references grouped by enclosing symbol."""

    def test_definitions_references_grouping_and_token_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "lib.py": "def claims(x):\n    return x\n",
                "use.py": "import lib\n\ndef run():\n    return lib.claims(1)\n\nclaims_total = 0\n",
                "rules.md": "# Params\n\n| `limit.ms` | 3 |\n\nUse `limit.ms` here.\n",
                ".env.json": '{"claims": "secret"}',
            }
            for name, content in files.items():
                (root / name).write_text(content)
            result = find_names(root, ["claims", "limit.ms"], list(files))
            claims, limit = result["results"]
            self.assertEqual([(d["path"], d["line"], d["kind"]) for d in claims["definitions"]], [("lib.py", 1, "function")])
            self.assertEqual([(g["path"], g["enclosing"], [l["line"] for l in g["lines"]]) for g in claims["references"]],
                             [("use.py", "run", [4])])
            self.assertEqual([(d["path"], d["line"], d["kind"]) for d in limit["definitions"]], [("rules.md", 3, "table-row")])
            self.assertEqual([(g["enclosing"], [l["line"] for l in g["lines"]]) for g in limit["references"]], [("Params", [5])])
            self.assertEqual(result["filesScanned"], 3)

    def test_repository_find_matches_the_declared_expectations(self):
        listed = [p.relative_to(ROOT).as_posix() for p in (ROOT / "tools").glob("*.py")] + \
                 ["docs/EXECUTION_ANNEX_v1.2.0.md", "docs/STATE_TRANSITIONS_v1.2.0.md"]
        claims, settle = find_names(ROOT, ["computed_claims", "recovery.settleMs"], listed)["results"]
        self.assertEqual({d["path"] for d in claims["definitions"]}, {"tools/check_stage1_gate.py"})
        self.assertTrue({"tools/test_stage1_gate.py", "tools/test_project_map.py"} <= {g["path"] for g in claims["references"]})
        self.assertIn(("docs/EXECUTION_ANNEX_v1.2.0.md", 787, "table-row"),
                      {(d["path"], d["line"], d["kind"]) for d in settle["definitions"]})
        section7 = [g for g in settle["references"] if g["path"] == "docs/STATE_TRANSITIONS_v1.2.0.md"]
        self.assertEqual(section7[0]["enclosing"], "State Transitions v1.2.0 > 7. Recovery reconciliation consistency")
        self.assertIn(183, [l["line"] for l in section7[0]["lines"]])


if __name__ == "__main__":
    unittest.main()
