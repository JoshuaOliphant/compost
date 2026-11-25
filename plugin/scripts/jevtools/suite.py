# ABOUTME: Finds a repo's tests as node ids with their source: Python (ast), JS/TS (test/it calls), Go, Rust, Java and
# ABOUTME: Kotlin, in the working tree or at a git revision. The Jev test tools choose among these; nothing calls Jev.
import ast
import re
import subprocess
from pathlib import Path

SKIPPED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build", "target", "vendor"}
SOURCE_CHARS = 700
PYTHON_FILE = re.compile(r"^(test_.*|.*_test)\.py$")
JS_FILE = re.compile(r"\.(test|spec)\.(js|mjs|cjs|ts|tsx|jsx)$")
JS_TEST = re.compile(r"""^\s*(?:test|it)\s*\(\s*(['"`])(.+?)\1""")
JS_LINES = 15
GO_FILE = re.compile(r"_test\.go$")
GO_TEST = re.compile(r"^func\s+(?:\([^)]*\)\s*)?((?:Test|Example|Fuzz)\w*)\s*\(")
RUST_FILE = re.compile(r"\.rs$")
RUST_MARK = re.compile(r"^\s*#\[(?:\w+::)*(?:test|rstest)\b")
RUST_NAME = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(\w+)")
JVM_FILE = re.compile(r"Tests?\.(java|kt)$")
JVM_MARK = re.compile(r"^\s*@(?:Test|ParameterizedTest|RepeatedTest|TestFactory)\b")
JVM_NAME = re.compile(r"(?:\bvoid\s+(\w+)|\bfun\s+(?:`([^`]+)`|(\w+)))\s*\(")
NAME_REACH = 6
BRACE_LINES = 80


def is_test_file(relative: str) -> bool:
    parts = Path(relative).parts
    if SKIPPED & set(parts):
        return False
    name = parts[-1]
    return any(pattern.search(name) for pattern in (PYTHON_FILE, JS_FILE, GO_FILE, RUST_FILE, JVM_FILE))


def test_files(repo: Path) -> list[Path]:
    return [path for path in sorted(repo.rglob("*")) if path.is_file() and is_test_file(str(path.relative_to(repo)))]


def dedent(line: str, indent: int) -> str:
    return line[indent:] if line[:indent].isspace() else line


def is_test_class(node: ast.ClassDef, test_classes: set[str]) -> bool:
    """pytest collects `Test*` classes; unittest any TestCase subclass whatever its name (`GreetTest(TestCase)`).
    A base counts when its name says Test (`TestCase`, `APITestCase`, `BaseTest`) or it is a test class above in
    this module; a base imported under a name without Test is not followed."""
    bases = [ast.unparse(base).rsplit(".", 1)[-1] for base in node.bases]
    return node.name.startswith("Test") or any("Test" in base or base in test_classes for base in bases)


def python_tests(source: str, relative: str, limit: int) -> dict[str, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    lines = source.splitlines()
    found = {}
    test_classes: set[str] = set()
    for node in tree.body:
        members = [(node, "")]
        if isinstance(node, ast.ClassDef) and is_test_class(node, test_classes):
            test_classes.add(node.name)
            members = [(child, f"{node.name}::") for child in node.body]
        for member, prefix in members:
            if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef) and member.name.startswith("test_"):
                start = min([member.lineno, *(decorator.lineno for decorator in member.decorator_list)])
                text = "\n".join(dedent(line, member.col_offset) for line in lines[start - 1 : member.end_lineno])
                found[f"{relative}::{prefix}{member.name}"] = text[:limit]
    return found


def js_tests(source: str, relative: str, limit: int) -> dict[str, str]:
    lines = source.splitlines()
    found = {}
    for number, line in enumerate(lines):
        if match := JS_TEST.match(line):
            found[f"{relative}::{match.group(2)}"] = "\n".join(lines[number : number + JS_LINES])[:limit]
    return found


def braced(lines: list[str], start: int, header: int) -> str:
    """Lines from `start` through the brace that closes the body opened at or after `header`."""
    depth, opened = 0, False
    end = min(len(lines), header + BRACE_LINES)
    for number in range(header, end):
        depth += lines[number].count("{") - lines[number].count("}")
        opened = opened or "{" in lines[number]
        if opened and depth <= 0:
            end = number + 1
            break
    return "\n".join(lines[start:end])


def go_tests(source: str, relative: str, limit: int) -> dict[str, str]:
    lines = source.splitlines()
    found = {}
    for number, line in enumerate(lines):
        if match := GO_TEST.match(line):
            found[f"{relative}::{match.group(1)}"] = braced(lines, number, number)[:limit]
    return found


def marked_tests(mark: re.Pattern, name: re.Pattern):
    """Rust's `#[test]` and JUnit's `@Test`: a marker line, then the function it marks within a few lines."""

    def reader(source: str, relative: str, limit: int) -> dict[str, str]:
        lines = source.splitlines()
        found = {}
        for number, line in enumerate(lines):
            if not mark.match(line):
                continue
            for header in range(number, min(len(lines), number + NAME_REACH)):
                if match := name.search(lines[header]):
                    test = next(group for group in match.groups() if group)
                    found[f"{relative}::{test}"] = braced(lines, number, header)[:limit]
                    break
        return found

    return reader


READERS = {
    ".py": python_tests,
    ".go": go_tests,
    ".rs": marked_tests(RUST_MARK, RUST_NAME),
    ".java": marked_tests(JVM_MARK, JVM_NAME),
    ".kt": marked_tests(JVM_MARK, JVM_NAME),
}


def tests_in(relative: str, source: str, limit: int = SOURCE_CHARS) -> dict[str, str]:
    reader = READERS.get(Path(relative).suffix, js_tests)
    return reader(source, relative, limit)


def collect(repo: Path, limit: int = SOURCE_CHARS) -> dict[str, str]:
    tests: dict[str, str] = {}
    for path in test_files(repo):
        tests.update(tests_in(str(path.relative_to(repo)), path.read_text(errors="replace"), limit))
    return tests


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def collect_at(repo: Path, ref: str, limit: int = SOURCE_CHARS) -> dict[str, str]:
    """The tests under `repo` as they were at `ref`; paths are relative to `repo`, as `collect` gives them."""
    if git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
        raise LookupError(f"{ref!r} is not a commit in {repo}")
    listed = git(repo, "ls-tree", "-r", "--name-only", ref).stdout.splitlines()
    tests: dict[str, str] = {}
    for relative in filter(is_test_file, listed):
        tests.update(tests_in(relative, git(repo, "show", f"{ref}:./{relative}").stdout, limit))
    return tests
