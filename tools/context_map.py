"""Local advisory file graph and map-first reading aids. No model, network, or semantic-completeness claim.

Modes:
  --paths P... [--depth N]   bounded file graph of imports and literal references (discovery)
  --outline P...             symbols and sections with line spans, so only the needed span is read
  --find NAME...             definitions and every whole-token reference, grouped by enclosing symbol
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

SKIP_PARTS = {".git", ".venv", "node_modules", "dist", "__pycache__", ".codegraph", "graft"}
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".md", ".json", ".yml", ".yaml"}
TS_IMPORT = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*)["']([^"']+)["']""")
ROOTS = ("", "research/", "tools/")
EXCLUSIONS = ["SKIP_PARTS directories (" + ", ".join(sorted(SKIP_PARTS)) + ")", "research/data/raw/ and research/data/holdout/",
              ".env* paths", "lockfiles", "symlinks", "files over 1 MB", "suffixes other than " + ", ".join(sorted(SUFFIXES))]

def read_sources(root: Path, paths: list[str]) -> dict[str, str]:
    sources = {}
    for name in sorted(set(paths)):
        rel = PurePosixPath(name)
        if rel.is_absolute() or ".." in rel.parts or set(rel.parts) & SKIP_PARTS:
            continue
        if name.startswith(("research/data/raw/", "research/data/holdout/")):
            continue
        if any(part.startswith(".env") for part in rel.parts) or name.endswith(("-lock.json", ".lock")):
            continue
        file = root / name
        if file.suffix not in SUFFIXES or not file.is_file() or file.is_symlink():
            continue
        if any(p.is_symlink() for p in file.parents if p != root and root in p.parents):
            continue
        try:
            file.resolve().relative_to(root.resolve())
            if file.stat().st_size <= 1_000_000:
                sources[name] = file.read_text(encoding="utf-8")
        except (ValueError, UnicodeError, OSError):
            continue
    return sources

def build_graph(root: Path, paths: list[str]) -> dict:
    sources = read_sources(root, paths)
    edges = set()
    unresolved = []
    modules = {}
    for path in sources:
        if path.endswith(".py"):
            for prefix in ROOTS:
                if path.startswith(prefix):
                    module = path[len(prefix):-3].replace("/", ".")
                    if module.endswith(".__init__"):
                        module = module[:-9]
                    modules.setdefault(module, set()).add(path)
    def link_import(path: str, module: str):
        hits = modules.get(module, set())
        if hits:
            for hit in hits:
                if hit != path:
                    edges.add((path, hit, "python_import"))
        else:
            unresolved.append({"source": path, "reference": module, "kind": "external_or_unresolved_import"})
    for path, content in sources.items():
        if path.endswith(".py"):
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            link_import(path, alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.level:
                            parent = PurePosixPath(path).parent
                            for _ in range(node.level - 1):
                                parent = parent.parent
                            base = str(parent).replace("/", ".").strip(".")
                            module = ".".join(p for p in (base, node.module or "") if p)
                        else:
                            module = node.module or ""
                        link_import(path, module)
                        for alias in node.names:
                            candidate = module + "." + alias.name
                            if candidate in modules:
                                link_import(path, candidate)
            except SyntaxError as exc:
                unresolved.append({"source": path, "reference": str(exc), "kind": "python_parse_error"})
        elif path.endswith((".ts", ".tsx", ".js", ".mjs")):
            for spec in TS_IMPORT.findall(content):
                if spec.startswith("."):
                    candidate = (root / path).parent / spec
                    candidates = [candidate, candidate.with_suffix(".ts"), candidate.with_suffix(".tsx"),
                                  candidate.with_suffix(".js"), candidate / "index.ts"]
                    hits = []
                    for option in candidates:
                        try:
                            target = option.resolve().relative_to(root.resolve()).as_posix()
                        except ValueError:
                            continue
                        if target in sources:
                            hits.append(target)
                    if hits:
                        edges.add((path, hits[0], "literal_ts_import"))
                        continue
                unresolved.append({"source": path, "reference": spec, "kind": "external_or_unresolved_import"})
        # Literal mentions are discovery hints, not verified semantic dependencies.
        for target in sources:
            if target != path and target in content:
                edges.add((path, target, "literal_reference"))
            if target.startswith("fixtures/contracts/") and target.endswith("/expected.json"):
                fixture_id = target[len("fixtures/contracts/"):-len("/expected.json")]
                if fixture_id in content and target != path:
                    edges.add((path, target, "fixture_reference"))
    hashes = {p: hashlib.sha256(c.encode()).hexdigest() for p, c in sources.items()}
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"schemaVersion": 1, "workingTreeFingerprint": fingerprint,
            "limitations": ["file graph, not a call graph", "literal TypeScript import extraction is best effort",
                           "dynamic dispatch and semantic contract dependencies require review",
                           "external/unresolved imports are not proof of missing dependencies",
                           "large, binary, secret-path, generated and dataset files are excluded"],
            "nodes": [{"path": p, "sha256": h} for p, h in hashes.items()],
            "edges": [{"source": a, "target": b, "kind": k} for a, b, k in sorted(edges)],
            "unresolved": sorted(unresolved, key=lambda x: (x["source"], x["reference"]))}

def select(graph: dict, seeds: list[str], depth: int) -> dict:
    all_paths = {n["path"] for n in graph["nodes"]}
    missing = set(seeds) - all_paths
    if missing:
        raise ValueError("missing or excluded seed paths: " + ", ".join(sorted(missing)))
    selected = set(seeds)
    for _ in range(depth):
        selected |= {e["target"] for e in graph["edges"] if e["source"] in selected} | {
            e["source"] for e in graph["edges"] if e["target"] in selected}
    return {**graph, "seeds": seeds, "depth": depth,
            "nodes": [n for n in graph["nodes"] if n["path"] in selected],
            "edges": [e for e in graph["edges"] if e["source"] in selected and e["target"] in selected],
            "unresolved": [u for u in graph["unresolved"] if u["source"] in selected]}

# ---------------------------------------------------------------------------
# Map-first reading: outlines with line spans and grouped name search.

OUTLINE_LIMITATIONS = ["outline spans locate code and sections; they do not prove behavior or completeness",
                       "TypeScript/JavaScript use a lexical scanner: regex literals and object-typed return annotations can shift spans",
                       "find matches whole tokens textually; it does not resolve types, imports or dynamic dispatch"]

def _entry(kind: str, name: str, qualname: str, start: int, end: int, signature: str) -> dict:
    return {"kind": kind, "name": name, "qualname": qualname, "startLine": start, "endLine": end,
            "signature": signature.strip()[:160]}

def _outline_python(text: str) -> list[dict]:
    tree = ast.parse(text)
    lines = text.splitlines()
    entries = []

    def start_of(node) -> int:
        return min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entries.append(_entry("function", node.name, node.name, start_of(node), node.end_lineno, lines[node.lineno - 1]))
        elif isinstance(node, ast.ClassDef):
            entries.append(_entry("class", node.name, node.name, start_of(node), node.end_lineno, lines[node.lineno - 1]))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    entries.append(_entry("method", child.name, f"{node.name}.{child.name}", start_of(child),
                                          child.end_lineno, lines[child.lineno - 1]))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    entries.append(_entry("constant", target.id, target.id, node.lineno, node.end_lineno, lines[node.lineno - 1]))
    return entries

def _blank_ts(text: str) -> str:
    """Replace string, template and comment contents with spaces, keeping newlines and offsets."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if text[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "'\"`":
            j = i + 1
            while j < n and text[j] != c:
                if text[j] == "\\":
                    j += 1
                elif c != "`" and text[j] == "\n":
                    break
                j += 1
            for k in range(i + 1, min(j, n)):
                if text[k] != "\n":
                    out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)

TS_DECL = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?"
                     r"(function\*?|class|interface|type|enum|const|let)\s+([A-Za-z_$][\w$]*)")
TS_METHOD = re.compile(r"^(?:(?:public|private|protected|static|async|readonly|override|abstract|get|set)\s+)*"
                       r"([A-Za-z_$][\w$]*)\s*(?:<[^>()]*>)?\s*\(")
TS_NOT_METHODS = {"if", "for", "while", "switch", "return", "catch", "function", "super", "new", "typeof", "await", "throw"}
TS_KINDS = {"function": "function", "function*": "function", "class": "class", "interface": "interface",
            "type": "type", "enum": "enum", "const": "constant", "let": "variable"}

def _outline_typescript(text: str) -> list[dict]:
    code = _blank_ts(text)
    lines = text.splitlines()
    line_starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            line_starts.append(index + 1)

    def line_of(pos: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    match: dict[int, int] = {}
    depth_at: list[int] = [0] * (len(code) + 1)
    stack: list[int] = []
    for index, char in enumerate(code):
        depth_at[index] = len(stack)
        if char == "{":
            stack.append(index)
        elif char == "}" and stack:
            match[stack.pop()] = index
    depth_at[len(code)] = len(stack)

    code_lines = code.splitlines()
    entries = []
    for number, raw in enumerate(code_lines, start=1):
        stripped = raw.lstrip()
        pos = line_starts[number - 1] + (len(raw) - len(stripped))
        if depth_at[pos] != 0:
            continue
        decl = TS_DECL.match(stripped)
        if not decl:
            continue
        keyword, name = decl.group(1), decl.group(2)
        needs_brace = keyword in {"function", "function*", "class", "interface", "enum"}
        end = _ts_statement_end(code, match, pos, needs_brace)
        entries.append(_entry(TS_KINDS[keyword], name, name, number, line_of(end), lines[number - 1]))
        if keyword == "class":
            brace = code.find("{", pos)
            close = match.get(brace)
            if close is None:
                continue
            class_depth = depth_at[brace] + 1
            for inner_number in range(line_of(brace), line_of(close) + 1):
                inner_raw = code_lines[inner_number - 1]
                inner_stripped = inner_raw.lstrip()
                inner_pos = line_starts[inner_number - 1] + (len(inner_raw) - len(inner_stripped))
                if inner_pos <= brace or inner_pos >= close or depth_at[inner_pos] != class_depth:
                    continue
                method = TS_METHOD.match(inner_stripped)
                if not method or method.group(1) in TS_NOT_METHODS:
                    continue
                paren = code.find("(", inner_pos)
                body_open = _ts_body_open(code, match, paren)
                if body_open is None:
                    continue
                method_name = method.group(1)
                entries.append(_entry("method", method_name, f"{name}.{method_name}", inner_number,
                                      line_of(match[body_open]), lines[inner_number - 1]))
    return entries

def _ts_statement_end(code: str, match: dict[int, int], start: int, needs_brace: bool) -> int:
    """End offset of a top-level declaration: its body brace, or its terminating semicolon."""
    level = 0
    index = start
    while index < len(code):
        char = code[index]
        if char in "([":
            level += 1
        elif char in ")]":
            level -= 1
        elif char == "{" and index in match:
            if needs_brace and level == 0:
                return match[index]
            index = match[index]
        elif char == ";" and level <= 0:
            return index
        elif char == "\n" and not needs_brace and level <= 0:
            rest = code[index + 1:index + 200].lstrip()
            prev = code[start:index].rstrip()
            if prev and prev[-1] not in "=,([{+-*/|&?:<>" and (not rest or rest[0] not in ".?:=|&+-*/,)]}"):
                return index - 1
        index += 1
    return len(code) - 1

def _ts_body_open(code: str, match: dict[int, int], paren: int) -> int | None:
    """Offset of a method body's opening brace after its parameter list, or None for signatures."""
    level = 0
    index = paren
    while index < len(code):
        char = code[index]
        if char == "(":
            level += 1
        elif char == ")":
            level -= 1
            if level == 0:
                break
        index += 1
    index += 1
    while index < len(code):
        char = code[index]
        if char == "{" and index in match:
            # A return type annotated as an object literal is followed by the body brace.
            after = code[match[index] + 1:match[index] + 40].lstrip()
            if after.startswith("{") and code[index - 20:index].rstrip().endswith(":"):
                index = match[index] + 1
                continue
            return index
        if char in ";=":
            return None
        index += 1
    return None

MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
MD_FENCE = re.compile(r"^\s*(```|~~~)")

def _outline_markdown(text: str) -> list[dict]:
    lines = text.splitlines()
    headings = []
    fenced = False
    for number, line in enumerate(lines, start=1):
        if MD_FENCE.match(line):
            fenced = not fenced
            continue
        found = None if fenced else MD_HEADING.match(line)
        if found:
            headings.append((number, len(found.group(1)), found.group(2)))
    entries = []
    trail: list[str] = []
    for index, (number, level, title) in enumerate(headings):
        end = len(lines)
        for later_number, later_level, _ in headings[index + 1:]:
            if later_level <= level:
                end = later_number - 1
                break
        trail = (trail + [""] * level)[:level - 1] + [title]
        entries.append(_entry(f"h{level}", title, " > ".join(t for t in trail if t), number, end, lines[number - 1]))
    return entries

def _outline_json(text: str) -> list[dict]:
    json.loads(text)
    lines = text.splitlines()
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)

    def line_of(pos: int) -> int:
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    if not isinstance(json.loads(text), dict):
        return []
    keys: list[list] = []  # [name, key offset, value end offset]
    depth = 0
    in_string = False
    escape = False
    string_start = 0
    pending = None
    last_significant = 0
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
                if depth == 1:
                    pending = (text[string_start + 1:index], string_start)
                last_significant = index
            continue
        if char == '"':
            in_string = True
            string_start = index
            continue
        if char.isspace():
            continue
        if char == ":" and depth == 1 and pending:
            keys.append([pending[0], pending[1], None])
            pending = None
            continue
        pending = None
        if char == "," and depth == 1:
            if keys and keys[-1][2] is None:
                keys[-1][2] = last_significant
            continue
        if char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth == 0:
                if keys and keys[-1][2] is None:
                    keys[-1][2] = last_significant
                break
        last_significant = index
    return [_entry("key", name, name, line_of(start), line_of(end if end is not None else start),
                   lines[line_of(start) - 1]) for name, start, end in keys]

def outline_text(path: str, text: str) -> dict:
    """Outline one file's text. Returns entries, or a named error for unparseable input."""
    try:
        if path.endswith(".py"):
            entries = _outline_python(text)
        elif path.endswith((".ts", ".tsx", ".js", ".mjs")):
            entries = _outline_typescript(text)
        elif path.endswith(".md"):
            entries = _outline_markdown(text)
        elif path.endswith(".json"):
            entries = _outline_json(text)
        else:
            return {"path": path, "entries": [], "note": "no outline for this file type"}
    except (SyntaxError, ValueError) as exc:
        return {"path": path, "entries": [], "error": f"{type(exc).__name__}: {exc}"}
    entries.sort(key=lambda e: (e["startLine"], -e["endLine"]))
    return {"path": path, "entries": entries}

def _listed(root: Path) -> list[str]:
    listed = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                     cwd=root).decode().split("\0")
    return [p for p in listed if p]

def _fingerprint(sources: dict[str, str]) -> str:
    hashes = {p: hashlib.sha256(c.encode()).hexdigest() for p, c in sources.items()}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()

def outline(root: Path, paths: list[str]) -> dict:
    sources = read_sources(root, paths)
    missing = sorted(set(paths) - set(sources))
    if missing:
        raise ValueError("missing or excluded paths: " + ", ".join(missing))
    files = []
    for path in paths:
        text = sources[path]
        result = outline_text(path, text)
        result.update({"sha256": hashlib.sha256(text.encode()).hexdigest(), "lines": len(text.splitlines())})
        files.append(result)
    return {"schemaVersion": 1, "mode": "outline", "workingTreeFingerprint": _fingerprint(sources),
            "limitations": OUTLINE_LIMITATIONS, "files": files}

def _enclosing(entries: list[dict], line: int) -> dict | None:
    best = None
    for entry in entries:
        if entry["startLine"] <= line <= entry["endLine"]:
            if best is None or (entry["endLine"] - entry["startLine"]) <= (best["endLine"] - best["startLine"]):
                best = entry
    return best

def find_names(root: Path, names: list[str], paths: list[str]) -> dict:
    sources = read_sources(root, paths)
    results = []
    outlines = {path: outline_text(path, text) for path, text in sources.items()}
    for name in names:
        token = re.compile(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])")
        row = re.compile(r"^\|\s*`?" + re.escape(name) + r"`?\s*\|")
        definitions, references = [], {}
        for path, text in sources.items():
            entries = outlines[path]["entries"]
            definition_lines = set()
            for entry in entries:
                code_symbol = not entry["kind"].startswith("h") and entry["kind"] != "key"
                qualified = entry["qualname"] == name or entry["qualname"].endswith("." + name)
                if entry["name"] == name or (code_symbol and qualified):
                    definitions.append({"path": path, "line": entry["startLine"], "endLine": entry["endLine"],
                                        "kind": entry["kind"], "qualname": entry["qualname"], "signature": entry["signature"]})
                    definition_lines.add(entry["startLine"])
            for number, line in enumerate(text.splitlines(), start=1):
                if path.endswith(".md") and row.match(line):
                    around = _enclosing(entries, number)
                    definitions.append({"path": path, "line": number, "endLine": number, "kind": "table-row",
                                        "qualname": around["qualname"] if around else "", "signature": line.strip()[:160]})
                    definition_lines.add(number)
                    continue
                if number in definition_lines or not token.search(line):
                    continue
                around = _enclosing(entries, number)
                key = (path, around["qualname"] if around else "(top level)")
                group = references.setdefault(key, {"path": path, "enclosing": key[1],
                                                    "span": [around["startLine"], around["endLine"]] if around else None,
                                                    "lines": []})
                group["lines"].append({"line": number, "text": line.strip()[:160]})
        results.append({"name": name, "definitions": definitions,
                        "references": [references[k] for k in sorted(references)],
                        "referenceCount": sum(len(g["lines"]) for g in references.values())})
    return {"schemaVersion": 1, "mode": "find", "workingTreeFingerprint": _fingerprint(sources),
            "filesScanned": len(sources), "exclusions": EXCLUSIONS, "limitations": OUTLINE_LIMITATIONS,
            "results": results}

def render_text(result: dict) -> str:
    out = []
    if result["mode"] == "outline":
        for file in result["files"]:
            header = f"{file['path']} ({file['lines']} lines)"
            if file.get("error"):
                header += f" ERROR {file['error']}"
            elif file.get("note"):
                header += f" {file['note']}"
            out.append(header)
            for entry in file["entries"]:
                out.append(f"  L{entry['startLine']}-{entry['endLine']} {entry['kind']} {entry['qualname']}")
    else:
        out.append(f"scanned {result['filesScanned']} files")
        for item in result["results"]:
            out.append(f"{item['name']}: {len(item['definitions'])} definitions, {item['referenceCount']} references")
            for definition in item["definitions"]:
                out.append(f"  def {definition['path']}:L{definition['line']}-{definition['endLine']} "
                           f"{definition['kind']} {definition['qualname']} | {definition['signature']}")
            for group in item["references"]:
                span = f"L{group['span'][0]}-{group['span'][1]} " if group["span"] else ""
                out.append(f"  ref {group['path']} {span}{group['enclosing']}")
                for line in group["lines"]:
                    out.append(f"    L{line['line']}: {line['text']}")
    out.append("fingerprint " + result["workingTreeFingerprint"][:16] + " | discovery only, not proof")
    return "\n".join(out)

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--paths", nargs="+")
    mode.add_argument("--outline", nargs="+", metavar="PATH")
    mode.add_argument("--find", nargs="+", metavar="NAME")
    parser.add_argument("--depth", type=int, choices=range(4), default=1)
    parser.add_argument("--format", choices=("text", "json"), default="text",
                        help="output for --outline and --find (--paths always prints JSON)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        listed = _listed(root)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
        if args.paths:
            graph = build_graph(root, listed)
            graph["head"] = head.stdout.strip() if head.returncode == 0 else None
            print(json.dumps(select(graph, args.paths, args.depth), indent=2))
            return
        result = outline(root, args.outline) if args.outline else find_names(root, args.find, listed)
        result["head"] = head.stdout.strip() if head.returncode == 0 else None
        print(json.dumps(result, indent=2) if args.format == "json" else render_text(result))
    except (subprocess.CalledProcessError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")

if __name__ == "__main__":
    main()
