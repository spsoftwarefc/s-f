"""Portable tests for the advisory context mapper.

All fixtures are synthetic. No test depends on application files outside this repository.
"""
import tempfile
import unittest
from pathlib import Path

from context_map import build_graph, find_names, outline_text, select


def spans(result):
    return {
        entry["qualname"]: (entry["startLine"], entry["endLine"], entry["kind"])
        for entry in result["entries"]
    }


class ContextMapGraphTests(unittest.TestCase):
    def test_imports_literal_references_and_reverse_impact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = {
                "a.py": "from b import thing\n",
                "b.py": "thing = 1\n",
                "a.ts": 'import {x} from "./b.js";\n',
                "b.ts": "export const x = 1;\n",
                "rule.md": "Implementation lives in b.py\n",
            }
            for rel, content in source.items():
                (root / rel).write_text(content, encoding="utf-8")

            graph = build_graph(root, list(source))
            result = select(graph, ["b.py"], 1)

            self.assertEqual(
                {node["path"] for node in result["nodes"]},
                {"a.py", "b.py", "rule.md"},
            )
            self.assertTrue(
                any(
                    edge["source"] == "a.ts"
                    and edge["target"] == "b.ts"
                    and edge["kind"] == "literal_ts_import"
                    for edge in graph["edges"]
                )
            )

    def test_fingerprint_changes_with_working_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "a.py"
            path.write_text("x = 1\n", encoding="utf-8")
            before = build_graph(root, ["a.py"])["workingTreeFingerprint"]
            path.write_text("x = 2\n", encoding="utf-8")
            after = build_graph(root, ["a.py"])["workingTreeFingerprint"]
            self.assertNotEqual(before, after)

    def test_missing_and_secret_paths_are_not_silent_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.json").write_text('{"key":"private"}', encoding="utf-8")
            graph = build_graph(root, [".env.json"])
            self.assertEqual(graph["nodes"], [])
            with self.assertRaises(ValueError):
                select(graph, ["absent.py"], 1)


class ContextMapOutlineTests(unittest.TestCase):
    def test_python_functions_classes_methods_decorators_and_constants(self):
        text = (
            "LIMIT = 3\n"
            "\n"
            "@decorate\n"
            "def top(a):\n"
            "    return a\n"
            "\n"
            "class Box:\n"
            "    def open(self):\n"
            "        pass\n"
            "\n"
            "    async def shut(self):\n"
            "        pass\n"
        )
        self.assertEqual(
            spans(outline_text("m.py", text)),
            {
                "LIMIT": (1, 1, "constant"),
                "top": (3, 5, "function"),
                "Box": (7, 12, "class"),
                "Box.open": (8, 9, "method"),
                "Box.shut": (11, 12, "method"),
            },
        )

    def test_typescript_ignores_braces_in_strings_templates_and_comments(self):
        text = (
            "// a } brace in a comment\n"
            "export interface Point {\n"
            "  x: number;\n"
            "}\n"
            'export const LABEL = "{ not a block";\n'
            "export class Engine {\n"
            "  private step(n: number): string {\n"
            "    const s = `value ${n} } done`;\n"
            "    /* } */ return s;\n"
            "  }\n"
            "  run(): void {\n"
            "    if (true) { this.step(1); }\n"
            "  }\n"
            "}\n"
            "export function helper(): number {\n"
            "  return 1;\n"
            "}\n"
        )
        self.assertEqual(
            spans(outline_text("e.ts", text)),
            {
                "Point": (2, 4, "interface"),
                "LABEL": (5, 5, "constant"),
                "Engine": (6, 14, "class"),
                "Engine.step": (7, 10, "method"),
                "Engine.run": (11, 13, "method"),
                "helper": (15, 17, "function"),
            },
        )

    def test_markdown_sections_and_fenced_headings(self):
        text = (
            "# Doc\n"
            "## 1. First\n"
            "text\n"
            "```\n"
            "# not a heading\n"
            "```\n"
            "### 1.1 Sub\n"
            "more\n"
            "## 2. Second\n"
            "end\n"
        )
        result = spans(outline_text("d.md", text))
        self.assertEqual(result["Doc"], (1, 10, "h1"))
        self.assertEqual(result["Doc > 1. First"], (2, 8, "h2"))
        self.assertEqual(result["Doc > 1. First > 1.1 Sub"], (7, 8, "h3"))
        self.assertEqual(result["Doc > 2. Second"], (9, 10, "h2"))
        self.assertNotIn("Doc > not a heading", result)

    def test_json_top_level_keys_and_named_errors(self):
        text = '{\n  "a": 1,\n  "b": {\n    "c": "x, y"\n  },\n  "d": [1, 2]\n}\n'
        self.assertEqual(
            spans(outline_text("f.json", text)),
            {"a": (2, 2, "key"), "b": (3, 5, "key"), "d": (6, 6, "key")},
        )
        self.assertEqual(outline_text("list.json", "[1, 2]")["entries"], [])
        self.assertTrue(outline_text("bad.json", "{")["error"].startswith("JSONDecodeError"))
        self.assertTrue(outline_text("bad.py", "def (:\n")["error"].startswith("SyntaxError"))


class ContextMapFindTests(unittest.TestCase):
    def test_definitions_references_grouping_and_token_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "lib.py": "def claims(x):\n    return x\n",
                "use.py": "import lib\n\ndef run():\n    return lib.claims(1)\n\nclaims_total = 0\n",
                "rules.md": "# Params\n\n| `limit.ms` | 3 |\n\nUse `limit.ms` here.\n",
                ".env.json": '{"claims":"secret"}',
            }
            for rel, content in files.items():
                (root / rel).write_text(content, encoding="utf-8")

            claims, limit = find_names(
                root, ["claims", "limit.ms"], list(files)
            )["results"]

            self.assertEqual(
                [(d["path"], d["line"], d["kind"]) for d in claims["definitions"]],
                [("lib.py", 1, "function")],
            )
            self.assertEqual(
                [
                    (group["path"], group["enclosing"], [line["line"] for line in group["lines"]])
                    for group in claims["references"]
                ],
                [("use.py", "run", [4])],
            )
            self.assertEqual(
                [(d["path"], d["line"], d["kind"]) for d in limit["definitions"]],
                [("rules.md", 3, "table-row")],
            )
            self.assertEqual(
                [(group["enclosing"], [line["line"] for line in group["lines"]]) for group in limit["references"]],
                [("Params", [5])],
            )


if __name__ == "__main__":
    unittest.main()
