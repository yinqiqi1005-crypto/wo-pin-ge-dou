import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_FILES = {".DS_Store", ".env"}
FORBIDDEN_DIRECTORIES = {
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "media",
    "staticfiles",
}


def tracked_paths():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [Path(value) for value in result.stdout.decode().split("\0") if value]


def test_repository_does_not_track_runtime_or_secret_files():
    invalid = []
    for path in tracked_paths():
        if path.name in FORBIDDEN_FILES or path.suffix == ".sqlite3":
            invalid.append(str(path))
            continue
        if any(part in FORBIDDEN_DIRECTORIES for part in path.parts):
            invalid.append(str(path))

    assert invalid == []


def test_repository_does_not_contain_personal_absolute_paths():
    personal_roots = ("".join(("/", "Users", "/")), "".join(("/", "home", "/")))
    matches = []
    for relative_path in tracked_paths():
        path = PROJECT_ROOT / relative_path
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(root in content for root in personal_roots):
            matches.append(str(relative_path))

    assert matches == []
