"""Regression tests for Linux native package dependency policy."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _linux_builder_script() -> str:
    return (ROOT / "scripts" / "docker" / "build-linux-x64-ubuntu20.sh").read_text()


def _linux_builder_dockerfile() -> str:
    return (ROOT / "scripts" / "docker" / "Dockerfile.linux-x64-ubuntu20").read_text()


def _root_build_script() -> str:
    return (ROOT / "build.sh").read_text()


def _verify_examples_workflow() -> str:
    return (ROOT / ".github" / "workflows" / "verify-examples.yml").read_text()


def _verify_examples_script() -> str:
    return (ROOT / "scripts" / "verify-examples.sh").read_text()


def test_linux_x64_uses_digest_pinned_ubuntu_builder_image() -> None:
    dockerfile = _linux_builder_dockerfile()
    build_script = _root_build_script()
    pinned_image_pattern = r"ubuntu:20\.04@sha256:[0-9a-f]{64}"

    assert re.search(pinned_image_pattern, dockerfile)
    assert "FROM ubuntu:20.04\n" not in dockerfile
    assert "ARG UBUNTU_20_04_IMAGE=" in dockerfile
    assert "FROM ${UBUNTU_20_04_IMAGE}" in dockerfile

    assert re.search(pinned_image_pattern, build_script)
    assert "--build-arg \"UBUNTU_20_04_IMAGE=${UBUNTU_20_04_IMAGE}\"" in build_script
    assert re.search(r"\subuntu:20\.04\s", build_script) is None


def test_verify_examples_prs_install_checked_out_sdk() -> None:
    workflow = _verify_examples_workflow()

    assert (
        "VERIFY_EXAMPLES_MODE: ${{ github.event_name == 'workflow_dispatch' "
        "&& inputs.mode || 'auto' }}"
    ) in workflow
    assert 'if [ "${{ github.event_name }}" = "pull_request" ]; then' in workflow
    assert (
        'python -m pip install -e . "gopher-mcp-python-native-${{ matrix.platform }}"'
        in workflow
    )
    assert (
        "SDK_INSTALL_SPEC: ${{ github.event_name == 'pull_request' && "
        "github.workspace || '' }}"
    ) in workflow


def test_verify_examples_workflow_bounds_pr_cost_and_runtime() -> None:
    workflow = _verify_examples_workflow()

    assert "concurrency:" in workflow
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "timeout-minutes: 30" in workflow


def test_verify_examples_live_checks_only_agent_response_body() -> None:
    script = _verify_examples_script()
    workflow = _verify_examples_workflow()

    assert "answer_body=\"$(awk '/Agent Response/{capture=1; next} capture {print}'" in script
    assert 'grep -qi -- "$VERIFY_EXPECTED_ANSWER" <<<"$answer_body"' in script
    assert 'grep -qi -- "$VERIFY_EXPECTED_ANSWER" <<<"$output"' not in script
    assert "VERIFY_EXPECTED_ANSWER_TERMS" in script
    assert 'validate_expected_answer_terms "$answer_body"' in script
    assert "agent response contains an error" in script
    assert "Draft ID,Message ID,Thread ID" in workflow
    assert "table using columns Draft ID, Message ID, and Thread ID" in workflow


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
