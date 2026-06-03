#!/usr/bin/env python
"""Test runner for the single-cell ANN search system.

三种运行模式:
    python run_tests.py quick   – 快速模式（跳过 real_data / slow）
    python run_tests.py full    – 完整模式（含真实数据测试 + HTML 报告 + 覆盖率）
    python run_tests.py ci      – CI 模式（跳过 real_data，生成 JUnit XML）

用法:
    python run_tests.py [quick|full|ci] [--cov-fail-under=70]
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "tests" / "reports"


def venv_python() -> str:
    """Return the venv Python, falling back to sys.executable."""
    candidate = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    return str(candidate) if candidate.exists() else sys.executable


def run_pytest(args: list[str]) -> int:
    """Run pytest with the given arguments and return the exit code."""
    cmd = [venv_python(), "-m", "pytest"] + args
    print(f"[run] {' '.join(cmd)}")
    return subprocess.call(cmd)


def ensure_reports_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def mode_quick() -> int:
    """Fast mode: unit + integration tests only, no coverage."""
    return run_pytest([
        "-m", "not real_data and not slow",
        "--no-header",
    ])


def mode_full(cov_fail_under: int = 70) -> int:
    """Full mode: all tests + HTML report + coverage XML + terminal coverage."""
    ensure_reports_dir()
    return run_pytest([
        "-m", "real_data or not real_data",  # include all
        f"--html={REPORTS_DIR / 'test_report.html'}",
        "--self-contained-html",
        f"--cov=src",
        f"--cov-report=term",
        f"--cov-report=html:{REPORTS_DIR / 'coverage_html'}",
        f"--cov-report=xml:{REPORTS_DIR / 'coverage.xml'}",
        f"--cov-fail-under={cov_fail_under}",
    ])


def mode_ci() -> int:
    """CI mode: skip real_data, generate JUnit XML for CI integration."""
    ensure_reports_dir()
    return run_pytest([
        "-m", "not real_data",
        f"--junitxml={REPORTS_DIR / 'junit.xml'}",
        f"--html={REPORTS_DIR / 'test_report.html'}",
        "--self-contained-html",
        f"--cov=src",
        f"--cov-report=term",
        f"--cov-report=xml:{REPORTS_DIR / 'coverage.xml'}",
    ])


def parse_args() -> tuple[str, int]:
    """Parse CLI arguments."""
    mode = "quick"
    cov_fail_under = 70

    for arg in sys.argv[1:]:
        if arg in ("quick", "full", "ci"):
            mode = arg
        elif arg.startswith("--cov-fail-under="):
            cov_fail_under = int(arg.split("=")[1])

    return mode, cov_fail_under


def main() -> int:
    mode, cov_fail_under = parse_args()

    print(f"=== 单细胞 ANN 检索系统 · 测试运行器 ===")
    print(f"  Mode:      {mode}")
    print(f"  Reports:   {REPORTS_DIR}")
    print(f"  Python:    {venv_python()}")
    print()

    if mode == "quick":
        return mode_quick()
    elif mode == "full":
        return mode_full(cov_fail_under)
    else:
        return mode_ci()


if __name__ == "__main__":
    sys.exit(main())
