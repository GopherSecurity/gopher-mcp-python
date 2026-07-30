"""Regression tests for Linux native package dependency policy."""

import re
from pathlib import Path


def test_linux_x64_builder_does_not_bundle_openssl() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "docker"
        / "build-linux-x64-ubuntu20.sh"
    ).read_text()
    dep_skip_block = re.search(r"case \"\$dep_name\" in(?P<body>.*?)esac", script, re.S)

    assert dep_skip_block is not None
    assert "libssl.so*" in dep_skip_block.group("body")
    assert "libcrypto.so*" in dep_skip_block.group("body")
