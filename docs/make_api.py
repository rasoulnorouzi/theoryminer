"""make_api — write the API pages of the book from the docstrings of the public functions.

Run it from the repository root, before mdbook:

    python docs/make_api.py
    mdbook build docs

The script reads the source code with the ast module. It does not import theoryminer, so it needs
no model, no torch and no network. The docstrings stay the only source of the reference: the
script writes docs/src/reference/ again on each run, and git ignores that folder.

The script stops with an error when a public function (in theoryminer.__all__) has no stage in
STAGES or no line in docs/src/SUMMARY.md. So a new public function cannot miss the book.
"""

import ast
import os
import re
import shutil
import sys

PACKAGE_INIT = "theoryminer/__init__.py"
OUT_DIR = "docs/src/reference"
SUMMARY = "docs/src/SUMMARY.md"
SOURCE_URL = "https://github.com/rasoulnorouzi/theoryminer/blob/main/{path}#L{line}"

# The stages of the pipeline, in order. Every public function is in one stage.
STAGES = [
    ("Read PDFs", ["harvest", "extract_dois", "extract_references"]),
    ("Download papers", ["download_papers"]),
    ("Find causal claims", ["causenet"]),
    ("Group and name constructs", ["pairwise_grouping", "clusterer", "label_groups",
                                   "standardize_constructs", "standardize_groups"]),
    ("Draw the causal map", ["causal_map", "draw_map", "save_map"]),
]
SECTION_TITLES = {"Args": "Arguments", "Returns": "Returns", "Raises": "Raises",
                  "Example": "Example", "Examples": "Example"}

# A section header of a docstring. Matches "Args:"; not "    Args: x".
SECTION_HEADER = re.compile(r"^(Args|Returns|Raises|Examples?):\s*$")
# The first line of one argument: 4 spaces, the name, a colon.
# Matches "    pages: The pages to read."; not "        Values: one page".
ARGUMENT_LINE = re.compile(r"^ {4}(\w+):\s?(.*)$")
# One key (or several keys, joined by ", ") of a result and its meaning, apart by 2 or more spaces.
# Matches '    doc_id    the file name' and '    sent_id, doc_id, page   from the row';
# not '    A dict with two lists:'.
KEY_LINE = re.compile(r"^(\s+)([\w\"'.-]+(?:, [\w\"'.-]+)*)\s{2,}(\S.*)$")
# A doctest directive at the end of an example line. Matches "   # doctest: +SKIP"; not "# a note".
DOCTEST_DIRECTIVE = re.compile(r"\s*#\s*doctest:.*$")
# A default with its value, then a colon. Matches 'Default None: read every page.' (value "None");
# not 'Default: none. Give a path.' (no value: the argument is required).
DEFAULT_WITH_VALUE = re.compile(r"^Default\s+(.+?):\s+(.*)$")


# ---------------------------------------------------------------------------
# 1. Find the public functions in the source code.
# ---------------------------------------------------------------------------

def public_names():
    """Return the names in __all__ of theoryminer/__init__.py."""
    with open(PACKAGE_INIT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "__all__":     # not sys.modules[...] = ...
            return ast.literal_eval(node.value)
    raise ValueError(f"no __all__ in {PACKAGE_INIT}")


def module_file(from_file, level, module):
    """Return the file of a relative import, such as "from .download import x" in from_file."""
    folder = os.path.dirname(from_file)
    for _ in range(level - 1):
        folder = os.path.dirname(folder)
    base = os.path.join(folder, *module.split(".")) if module else folder
    if os.path.isdir(base):
        return os.path.join(base, "__init__.py")
    return base + ".py"


def find_function(path, name):
    """Return (function node, file) for a name, following the imports. None when it is not a function."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node, path
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level == 0:
            continue
        if name in [alias.name for alias in node.names]:
            return find_function(module_file(path, node.level, node.module), name)
    return None


# ---------------------------------------------------------------------------
# 2. Turn one docstring into Markdown.
# ---------------------------------------------------------------------------

def escape(text):
    """Return text that Markdown shows as it is: "<pdf>" is not an HTML tag, "|" is not a cell edge."""
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")


def signature_text(node):
    """Return the signature of a function, one argument on each line."""
    arguments = node.args.args
    defaults = [None] * (len(arguments) - len(node.args.defaults)) + list(node.args.defaults)
    lines = []
    for argument, default in zip(arguments, defaults):
        line = argument.arg
        if argument.annotation is not None:
            line += ": " + ast.unparse(argument.annotation)
        if default is not None:
            line += " = " + ast.unparse(default)
        lines.append("    " + line + ",")
    result = ""
    if node.returns is not None:
        result = " -> " + ast.unparse(node.returns)
    return f"{node.name}(\n" + "\n".join(lines) + f"\n){result}"


def split_sections(doc):
    """Return (the text before the first section, {section name: its lines})."""
    intro = []
    sections = {}
    current = None
    for line in doc.splitlines():
        header = SECTION_HEADER.match(line)
        if header:
            current = header.group(1)
            sections[current] = []
        elif current is None:
            intro.append(line)
        else:
            sections[current].append(line)
    return intro, sections


def render_intro(lines):
    """Return the text of the docstring before its sections. An indented block stays a code block."""
    result = []
    for line in lines:
        if line.startswith("    "):
            result.append(line)                # Markdown shows a 4-space block as code
        else:
            result.append(escape(line))
    return "\n".join(result).strip()


def argument_parts(lines):
    """Return [(name, [lines of its text])] from the lines of an Args section."""
    arguments = []
    for line in lines:
        start = ARGUMENT_LINE.match(line)
        if start:
            arguments.append((start.group(1), [start.group(2)]))
        elif arguments and line.strip():
            arguments[-1][1].append(line.strip())
    return arguments


def render_argument(name, lines):
    """Return the Markdown of one argument: its meaning, then its values and its default."""
    meaning = []
    items = []
    for line in lines:
        if line.startswith("Values:") or line.startswith("Default"):
            items.append(line)
        elif items:
            items[-1] += " " + line
        else:
            meaning.append(line)
    text = [f"### `{name}`", "", escape(" ".join(meaning))]
    if items:
        text.append("")
    for item in items:
        text.append("- " + render_item(item))
    return "\n".join(text)


def render_item(item):
    """Return one "Values:" or "Default" line of an argument in Markdown."""
    if item.startswith("Values:"):
        return "**Values:** " + escape(item[len("Values:"):].strip())
    with_value = DEFAULT_WITH_VALUE.match(item)
    if with_value:
        return f"**Default** `{with_value.group(1)}`: {escape(with_value.group(2))}"
    return "**" + escape(item.split(" ", 1)[0]) + "** " + escape(item.split(" ", 1)[1] if " " in item else "")


def render_args(lines):
    """Return the Markdown of an Args section."""
    parts = []
    for name, text in argument_parts(lines):
        parts.append(render_argument(name, text))
    return "\n\n".join(parts)


def render_returns(lines):
    """Return the Markdown of a Returns section. Aligned key lines become a table."""
    output = []
    rows = []
    key_indent = None
    for line in lines:
        key = KEY_LINE.match(line)
        if key and len(key.group(1)) >= 8:
            rows.append([key.group(2), key.group(3)])
            key_indent = len(key.group(1))
            continue
        if rows and line.strip() and len(line) - len(line.lstrip()) > key_indent:
            rows[-1][1] += " " + line.strip()        # the next line of the same key
            continue
        output.extend(table(rows))
        rows = []
        output.append(escape(line.strip()))
    output.extend(table(rows))
    return "\n".join(output).strip()


def table(rows):
    """Return the lines of a Markdown table of (key, meaning) rows, or [] for no row."""
    if not rows:
        return []
    lines = ["", "| key | meaning |", "|---|---|"]
    for key, meaning in rows:
        lines.append(f"| `{key}` | {escape(meaning)} |")
    lines.append("")
    return lines


def render_raises(lines):
    """Return the Markdown of a Raises section: one bullet for each error."""
    items = []
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("    ") and not line.startswith("        "):
            items.append(line.strip())
        elif items:
            items[-1] += " " + line.strip()
    bullets = []
    for item in items:
        error, _, cause = item.partition(":")
        bullets.append(f"- `{error.strip()}`: {escape(cause.strip())}")
    return "\n".join(bullets)


def render_example(lines):
    """Return the example as a Python console block, without the doctest directives."""
    code = []
    for line in lines:
        code.append(DOCTEST_DIRECTIVE.sub("", line[4:] if line.startswith("    ") else line).rstrip())
    return "```python\n" + "\n".join(code).strip() + "\n```"


RENDERERS = {"Args": render_args, "Returns": render_returns, "Raises": render_raises,
             "Example": render_example, "Examples": render_example}


def page_text(name, node, path):
    """Return the Markdown page of one public function."""
    doc = ast.get_docstring(node)
    intro, sections = split_sections(doc)
    summary = escape(intro[0].strip())
    source = SOURCE_URL.format(path=path, line=node.lineno)
    parts = [f"# {name}()", "", summary, "", "```python", signature_text(node), "```", "",
             f"Source: [`{path}`]({source})", "", render_intro(intro[1:])]
    for section, lines in sections.items():
        parts += ["", f"## {SECTION_TITLES[section]}", "", RENDERERS[section](lines)]
    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------------
# 3. Write the pages and check the book.
# ---------------------------------------------------------------------------

def check_book(functions):
    """Raise a ValueError when a public function has no stage or no line in SUMMARY.md."""
    staged = []
    for _, names in STAGES:
        staged.extend(names)
    missing = sorted(set(functions) - set(staged))
    if missing:
        raise ValueError(f"public functions without a stage in STAGES: {missing}")
    with open(SUMMARY, encoding="utf-8") as fh:
        summary = fh.read()
    missing = [name for name in functions if f"(reference/{name}.md)" not in summary]
    if missing:
        raise ValueError(f"public functions without a line in {SUMMARY}: {missing}")


def index_text(summaries):
    """Return the index page of the reference: one table per stage."""
    lines = ["# Reference", "",
             "One page for each public function. The text comes from the docstring in the code.", ""]
    for stage, names in STAGES:
        lines += [f"## {stage}", "", "| function | what it does |", "|---|---|"]
        for name in names:
            lines.append(f"| [`{name}()`]({name}.md) | {summaries[name]} |")
        lines.append("")
    return "\n".join(lines)


def main():
    """Write one page for each public function, and the index page."""
    functions = {}
    for name in public_names():
        found = find_function(PACKAGE_INIT, name)
        if found is not None:
            functions[name] = found
    check_book(list(functions))
    shutil.rmtree(OUT_DIR, ignore_errors=True)         # no page of a removed function stays
    os.makedirs(OUT_DIR)
    summaries = {}
    for name, (node, path) in functions.items():
        with open(os.path.join(OUT_DIR, f"{name}.md"), "w", encoding="utf-8") as fh:
            fh.write(page_text(name, node, path))
        summaries[name] = escape(ast.get_docstring(node).splitlines()[0].strip())
    with open(os.path.join(OUT_DIR, "index.md"), "w", encoding="utf-8") as fh:
        fh.write(index_text(summaries))
    print(f"make_api: {len(functions)} function pages and index.md -> {OUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(f"make_api: {error}")
