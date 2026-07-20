#!/usr/bin/env python3
"""Build and validate the DriftMind AWS Lambda deployment ZIP."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPOSITORY_ROOT / "requirements.txt"
DIST_DIRECTORY = REPOSITORY_ROOT / "dist"
OUTPUT_ZIP = DIST_DIRECTORY / "deployment.zip"
HANDLER = "lambda.app.lambda_handler"
TARGET_PYTHON = "3.12"
ROOT_MODULES = ("config.py", "logger.py", "models.py", "storage.py")
PACKAGE_DIRECTORIES = ("lambda", "providers", "snapshot", "collectors")
EXCLUDED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "article",
    "evidence",
    "tests",
}
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def install_dependencies(staging: Path) -> None:
    """Install Python 3.12-compatible runtime dependencies into staging."""
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "--no-compile",
        "--only-binary=:all:",
        "--implementation",
        "cp",
        "--python-version",
        TARGET_PYTHON,
        "--target",
        str(staging),
        "--requirement",
        str(REQUIREMENTS),
    ]
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)


def copy_application(staging: Path) -> None:
    """Copy only runtime source modules while preserving repository paths."""
    for module_name in ROOT_MODULES:
        shutil.copy2(REPOSITORY_ROOT / module_name, staging / module_name)

    ignore = shutil.ignore_patterns(
        ".git", ".pytest_cache", "__pycache__", "*.pyc", "*.pyo"
    )
    for directory_name in PACKAGE_DIRECTORIES:
        shutil.copytree(
            REPOSITORY_ROOT / directory_name,
            staging / directory_name,
            ignore=ignore,
        )


def add_artifact_package_markers(staging: Path) -> None:
    """Make source directories importable directly from the generated ZIP."""
    for directory_name in PACKAGE_DIRECTORIES:
        package_root = staging / directory_name
        directories = [package_root, *(path for path in package_root.rglob("*") if path.is_dir())]
        for directory in directories:
            if directory.name in EXCLUDED_DIRECTORIES:
                continue
            if any(path.suffix == ".py" for path in directory.iterdir() if path.is_file()):
                (directory / "__init__.py").touch(exist_ok=True)


def remove_excluded_artifacts(staging: Path) -> None:
    """Remove caches and test-only artifacts introduced by dependencies."""
    directories = sorted(
        (path for path in staging.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        if directory.name in EXCLUDED_DIRECTORIES and directory.exists():
            shutil.rmtree(directory)

    for path in staging.rglob("*"):
        if path.is_file() and path.suffix in {".pyc", ".pyo"}:
            path.unlink()


def create_deterministic_zip(staging: Path) -> None:
    """Create a stable, sorted ZIP with normalized timestamps and permissions."""
    DIST_DIRECTORY.mkdir(parents=True, exist_ok=True)
    OUTPUT_ZIP.unlink(missing_ok=True)
    files = sorted(path for path in staging.rglob("*") if path.is_file())
    with zipfile.ZipFile(
        OUTPUT_ZIP,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in files:
            archive_name = path.relative_to(staging).as_posix()
            info = zipfile.ZipInfo(archive_name, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def validate_handler_import() -> str:
    """Import the configured handler directly from the ZIP in isolation."""
    validation = """
import importlib
import sys

archive = sys.argv[1]
sys.path.insert(0, archive)
module = importlib.import_module("lambda.app")
handler = getattr(module, "lambda_handler", None)
if not callable(handler):
    raise RuntimeError("lambda.app.lambda_handler is not callable")
if archive not in str(module.__file__):
    raise RuntimeError(f"handler loaded outside deployment ZIP: {module.__file__}")
print(module.__file__)
"""
    with tempfile.TemporaryDirectory(prefix="driftmind-lambda-validation-") as directory:
        result = subprocess.run(
            [sys.executable, "-I", "-c", validation, str(OUTPUT_ZIP.resolve())],
            cwd=directory,
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "unknown import error"
        raise RuntimeError(f"deployment ZIP handler validation failed: {details}")
    return result.stdout.strip()


def format_size(byte_count: int) -> str:
    """Format a byte count for build output."""
    return f"{byte_count:,} bytes ({byte_count / (1024 * 1024):.2f} MiB)"


def main() -> int:
    """Build the deployment package and fail if its handler cannot import."""
    if not REQUIREMENTS.is_file():
        raise FileNotFoundError(f"requirements file not found: {REQUIREMENTS}")

    with tempfile.TemporaryDirectory(prefix="driftmind-lambda-package-") as directory:
        staging = Path(directory)
        install_dependencies(staging)
        copy_application(staging)
        remove_excluded_artifacts(staging)
        add_artifact_package_markers(staging)
        create_deterministic_zip(staging)

    handler_origin = validate_handler_import()
    print(f"Package: {OUTPUT_ZIP.relative_to(REPOSITORY_ROOT)}")
    print(f"Package size: {format_size(OUTPUT_ZIP.stat().st_size)}")
    print(f"Handler: {HANDLER}")
    print(f"Validated import: {handler_origin}")
    print("SUCCESS: Lambda deployment package built and handler import validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
