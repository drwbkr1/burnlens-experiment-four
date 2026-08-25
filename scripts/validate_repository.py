"""Validate the public-safe Experiment Four repository control plane.

This checker intentionally uses only the Python standard library. It verifies
the structural and claim-safety properties that must hold before scientific
work is admitted; it does not treat structure as scientific evidence.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    ".gitattributes",
    ".github/workflows/ci.yml",
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "VERSION",
    "docs/devlog/2026-08-25-empty-bootstrap.md",
    "docs/governance/CHECKPOINT-POLICY.md",
    "docs/governance/EXPERIMENT-FOUR-EXECUTION-GOAL.md",
    "docs/roadmap/ROADMAP.md",
    "docs/status/STATUS.md",
    "docs/status/VERSION-HISTORY.md",
    "pyproject.toml",
    "records/decisions/DECISION-REGISTER.md",
    "records/evidence/EVIDENCE-LEDGER.md",
    "records/evidence/E4-EV-0004-M0-LIVE-CHECKPOINT-2026-001.json",
    "records/governance/ACTIVE-PROJECT-CONTROL-PROFILE",
    "records/governance/EXPERIMENT-FOUR-AUTHORITY-2026-001.md",
    "records/governance/EXPERIMENT-FOUR-PROJECT-CONTROL-PROFILE-2026-002.json",
    "records/milestones/EXPERIMENT-FOUR-MILESTONE-001-METADATA-FEASIBILITY-2026-001.json",
    "records/reconciliations/EXPERIMENT-FOUR-STATE-2026-001.json",
    "records/reconciliations/EXPERIMENT-FOUR-STATE-2026-002.json",
    "scripts/validate_repository.py",
    "tests/test_repository_controls.py",
)

ALLOWED_TOP_LEVEL = {
    ".gitattributes",
    ".github",
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "VERSION",
    "docs",
    "pyproject.toml",
    "records",
    "scripts",
    "tests",
}

PROHIBITED_SUFFIXES = {
    ".7z",
    ".ckpt",
    ".geojson",
    ".gpkg",
    ".h5",
    ".hdf",
    ".hdf5",
    ".img",
    ".joblib",
    ".jp2",
    ".npy",
    ".npz",
    ".onnx",
    ".parquet",
    ".pkl",
    ".pt",
    ".pth",
    ".safetensors",
    ".shp",
    ".tar",
    ".tif",
    ".tiff",
    ".zip",
}

PROHIBITED_DIRECTORY_NAMES = {
    "artifacts",
    "checkpoints",
    "custody",
    "data",
    "datasets",
    "imagery",
    "labels",
    "models",
    "outputs",
    "private",
    "runs",
    "runtime",
}

MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def repository_files() -> list[Path]:
    """Return candidate repository files while excluding Git/runtime caches."""
    excluded = {".git", ".pytest_cache", "__pycache__"}
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.parts)
    )


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON {relative(path)}: {exc}")
        return None


def check_required_paths(errors: list[str]) -> None:
    for item in REQUIRED_PATHS:
        if not (ROOT / item).is_file():
            errors.append(f"missing required file: {item}")


def check_allowed_public_shape(files: list[Path], errors: list[str]) -> None:
    for path in files:
        rel = path.relative_to(ROOT)
        if rel.parts[0] not in ALLOWED_TOP_LEVEL:
            errors.append(f"unexpected top-level content: {rel.as_posix()}")
        if path.suffix.lower() in PROHIBITED_SUFFIXES:
            errors.append(f"prohibited scientific/archive artifact: {rel.as_posix()}")
        if any(part.lower() in PROHIBITED_DIRECTORY_NAMES for part in rel.parts[:-1]):
            errors.append(f"prohibited custody/output directory: {rel.as_posix()}")
        if path.stat().st_size > 1_000_000:
            errors.append(f"unexpected file larger than 1 MB: {rel.as_posix()}")


def check_json(files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix.lower() == ".json":
            load_json(path, errors)


def check_markdown_links(files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            local_part = unquote(target.split("#", 1)[0])
            resolved = (path.parent / local_part).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                errors.append(f"link leaves repository in {relative(path)}: {target}")
                continue
            if not resolved.exists():
                errors.append(f"broken local link in {relative(path)}: {target}")


def check_secret_indicators(files: list[Path], errors: list[str]) -> None:
    private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"
    token_patterns = (
        re.compile("gh" + r"[pousr]_[A-Za-z0-9]{30,}"),
        re.compile("sk-" + r"[A-Za-z0-9]{20,}"),
        re.compile("AKIA" + r"[A-Z0-9]{16}"),
    )
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"unexpected non-text public file: {relative(path)}")
            continue
        if private_key_marker in text:
            errors.append(f"private-key marker found: {relative(path)}")
        if any(pattern.search(text) for pattern in token_patterns):
            errors.append(f"credential-like token found: {relative(path)}")


def check_control_alignment(errors: list[str]) -> None:
    pointer_path = ROOT / "records/governance/ACTIVE-PROJECT-CONTROL-PROFILE"
    try:
        pointer = pointer_path.read_text(encoding="utf-8").strip()
        profile_path = (ROOT / pointer).resolve()
        profile_path.relative_to(ROOT)
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"invalid active-profile pointer: {exc}")
        return
    profile = load_json(profile_path, errors)
    if not isinstance(profile, dict):
        return

    active_contract = profile.get("control_surfaces", {}).get("active_contract")
    if not isinstance(active_contract, str) or not active_contract:
        errors.append("active project profile has no active_contract")
        return
    contract_path = (ROOT / active_contract).resolve()
    try:
        contract_path.relative_to(ROOT)
    except ValueError:
        errors.append("active contract path leaves repository")
        return
    contract = load_json(contract_path, errors)
    if not isinstance(contract, dict):
        return

    expected_remote = "https://github.com/drwbkr1/burnlens-experiment-four.git"
    if profile.get("project", {}).get("repository_identity", {}).get("expected_remote") != expected_remote:
        errors.append("project profile expected_remote does not match canonical repository")
    contract_ref = relative(contract_path)
    if profile.get("control_surfaces", {}).get("active_contract") != contract_ref:
        errors.append("project profile active_contract does not match the resolved contract")
    if contract.get("project_profile_ref") != relative(profile_path):
        errors.append("active milestone does not reference the active project profile")
    if contract.get("status") != "active":
        errors.append("the pointer-selected milestone contract must be active")

    profile_actions = set(profile.get("authority", {}).get("authorized_action_classes", []))
    contract_actions = set(contract.get("authority", {}).get("authorized_action_classes", []))
    if not contract_actions or contract_actions != profile_actions:
        errors.append("profile and milestone authority classes are not identical")


def check_claim_boundaries(errors: list[str]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    goal = (ROOT / "docs/governance/EXPERIMENT-FOUR-EXECUTION-GOAL.md").read_text(encoding="utf-8")
    status = (ROOT / "docs/status/STATUS.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.lower().split())
    normalized_goal = " ".join(goal.lower().split())
    required_readme = (
        "there is no admitted external source, scientific dataset",
        "not official fire information",
        "dataset_readiness",
        "comparative_status",
        "release_status",
    )
    required_goal = (
        "six development-only pilot events",
        "permanently excluded",
        "16 train",
        "6 validation",
        "8 sealed test",
        "one opening",
        "after opening: no tuning",
    )
    for phrase in required_readme:
        if phrase.lower() not in normalized_readme:
            errors.append(f"README claim boundary missing phrase: {phrase}")
    for phrase in required_goal:
        if phrase.lower() not in normalized_goal:
            errors.append(f"execution goal missing frozen-design phrase: {phrase}")
    if "Milestone 0" not in status or "bootstrap" not in status.lower():
        errors.append("status does not identify the Milestone 0 bootstrap state")


def check_git_identity(errors: list[str]) -> None:
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"unable to verify Git identity: {exc}")
        return

    accepted_remotes = {
        "https://github.com/drwbkr1/burnlens-experiment-four",
        "https://github.com/drwbkr1/burnlens-experiment-four.git",
        "git@github.com:drwbkr1/burnlens-experiment-four.git",
    }
    if remote not in accepted_remotes:
        errors.append(f"unexpected origin remote: {remote}")
    effective_branch = branch or os.environ.get("GITHUB_HEAD_REF", "")
    if effective_branch != "main" and not effective_branch.startswith("codex/"):
        errors.append(
            "validation requires main or a codex/ review branch, found: "
            f"{effective_branch or '<detached>'}"
        )


def validate() -> list[str]:
    errors: list[str] = []
    files = repository_files()
    check_required_paths(errors)
    check_allowed_public_shape(files, errors)
    check_json(files, errors)
    check_markdown_links(files, errors)
    check_secret_indicators(files, errors)
    check_control_alignment(errors)
    check_claim_boundaries(errors)
    check_git_identity(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Repository controls: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Repository controls: PASS ({len(repository_files())} public-safe files checked)")
    print("Scientific evidence status: NOT STARTED (structural validation only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
