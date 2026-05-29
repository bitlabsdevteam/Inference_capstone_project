#!/usr/bin/env python3
"""Static repo hygiene checks for production-grade submission quality."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_PATH = ROOT / "starter_code" / "requirements.txt"
GENERATED_ARTIFACT_PATTERNS = (
    "starter_code/results_infertutor/",
    "starter_code/submission_bundle/",
    "starter_code/modal_infertutor_app_generated.py",
)
RAW_MODAL_URL_RE = re.compile(r"https://(?!\*\*\*\.modal\.run)[^/\s]+\.modal\.run")
REQUIRED_DOC_SUBSTRINGS = {
    "README.md": ("local proxy metric", "quality_pass_rate"),
    "InferTutor_Arena_Capstone.md": ("local proxy metric", "quality_pass_rate"),
}


def load_tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def check_requirements_are_pinned(lines: list[str]) -> None:
    invalid = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            invalid.append(line)
    if invalid:
        raise ValueError(
            "Unpinned requirements found: " + ", ".join(sorted(invalid))
        )


def check_for_tracked_generated_artifacts(tracked_files: list[str]) -> None:
    offenders = [
        path
        for path in tracked_files
        if any(path.startswith(pattern) or path == pattern for pattern in GENERATED_ARTIFACT_PATTERNS)
    ]
    if offenders:
        raise ValueError(
            "Tracked generated artifacts found: " + ", ".join(sorted(offenders))
        )


def check_for_raw_modal_urls(file_contents: dict[str, str]) -> None:
    offenders = []
    for rel_path, content in file_contents.items():
        if RAW_MODAL_URL_RE.search(content):
            offenders.append(rel_path)
    if offenders:
        raise ValueError(
            "Tracked source files contain raw modal.run URLs: "
            + ", ".join(sorted(offenders))
        )


def check_python_files_for_shell_true(file_contents: dict[str, str]) -> None:
    offenders: list[str] = []
    for rel_path, content in file_contents.items():
        if not rel_path.endswith(".py"):
            continue
        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_subprocess_call = (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            )
            if not is_subprocess_call:
                continue
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    offenders.append(rel_path)
                    break
    if offenders:
        raise ValueError(
            "Unsafe subprocess shell=True usage found in: "
            + ", ".join(sorted(set(offenders)))
        )


def check_required_doc_language(file_contents: dict[str, str]) -> None:
    missing: list[str] = []
    for rel_path, required_substrings in REQUIRED_DOC_SUBSTRINGS.items():
        content = file_contents.get(rel_path, "")
        if any(substring not in content for substring in required_substrings):
            missing.append(rel_path)
    if missing:
        raise ValueError(
            "Required score-scope language missing from: " + ", ".join(sorted(missing))
        )


def collect_source_texts(tracked_files: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for rel_path in tracked_files:
        path = ROOT / rel_path
        if not path.is_file():
            continue
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}:
            continue
        if rel_path.startswith("tests/"):
            continue
        try:
            texts[rel_path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return texts


def main() -> None:
    tracked_files = load_tracked_files()
    source_texts = collect_source_texts(tracked_files)
    check_requirements_are_pinned(REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines())
    check_for_tracked_generated_artifacts(tracked_files)
    check_for_raw_modal_urls(source_texts)
    check_python_files_for_shell_true(source_texts)
    check_required_doc_language(source_texts)
    print("Repo hygiene checks passed.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
