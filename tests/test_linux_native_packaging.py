"""Regression tests for Linux native package dependency policy."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _linux_builder_script() -> str:
    return (ROOT / "scripts" / "docker" / "build-linux-x64-ubuntu20.sh").read_text()


def test_linux_x64_builder_does_not_bundle_openssl() -> None:
    script = _linux_builder_script()
    dep_skip_block = re.search(r"case \"\$dep_name\" in(?P<body>.*?)esac", script, re.S)

    assert dep_skip_block is not None
    assert "libssl.so*" in dep_skip_block.group("body")
    assert "libcrypto.so*" in dep_skip_block.group("body")


def test_linux_x64_builder_fails_on_patchelf_errors() -> None:
    script = _linux_builder_script()

    assert "patchelf --set-rpath '$ORIGIN' \"$sofile\"" in script
    assert "patchelf --set-rpath '$ORIGIN' \"$sofile\" 2>/dev/null || true" not in script


def test_publish_workflow_checks_linux_x64_dependencies() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish-packages.yml").read_text()

    assert "Verify Linux native dependencies" in workflow
    assert "matrix.platform == 'linux-x64'" in workflow
    assert "set -euo pipefail" in workflow
    assert "readelf -d \"$sofile\"" in workflow
    assert "ldd \"$sofile\"" in workflow
    assert "grep -Ev '^(libssl\\.so|libcrypto\\.so)'" in workflow
    assert "OpenSSL libraries must remain system-provided" in workflow
