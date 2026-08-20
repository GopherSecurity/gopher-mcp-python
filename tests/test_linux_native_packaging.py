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


def _oauth_verify_workflow() -> str:
    return (ROOT / ".github" / "workflows" / "oauth-verify.yml").read_text()


def _verify_examples_script() -> str:
    return (ROOT / "scripts" / "verify-examples.sh").read_text()


def _api_example(path: str) -> str:
    return (ROOT / "examples" / "api" / path).read_text()


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


def test_oauth_verify_prs_install_checked_out_sdk() -> None:
    workflow = _oauth_verify_workflow()

    assert "pull_request:" in workflow
    assert "branches: [main]" in workflow
    assert 'python -m pip install -e ".[dev]"' in workflow
    assert "scripts/test-oauth-custom-idp.sh" in workflow


def test_verify_examples_workflow_stays_optional_for_live_smoke() -> None:
    workflow = _verify_examples_workflow()

    assert (
        "VERIFY_EXAMPLES_MODE: ${{ github.event_name == 'workflow_dispatch' "
        "&& inputs.mode || 'auto' }}"
    ) in workflow
    assert "pull_request:" not in workflow
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "branches: [iml_verify_auto]" in workflow
    assert 'if [ "${{ github.event_name }}" = "pull_request" ]; then' not in workflow
    assert "SDK_INSTALL_SPEC:" not in workflow


def test_verify_examples_workflow_bounds_pr_cost_and_runtime() -> None:
    workflow = _verify_examples_workflow()

    assert "concurrency:" in workflow
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "timeout-minutes: 30" in workflow


def test_verify_examples_workflow_checks_linux_native_dependencies() -> None:
    workflow = _verify_examples_workflow()

    assert "Verify Linux native package" in workflow
    assert "=== Linux Native Dependencies ===" in workflow
    assert "readelf -d \"$sofile\"" in workflow
    assert "No RPATH/RUNPATH declared for $sofile" in workflow
    assert "RPATH/RUNPATH without \\$ORIGIN" in workflow
    assert "ldd \"$sofile\"" in workflow
    assert "grep -Ev '^(libssl\\.so|libcrypto\\.so)'" in workflow
    assert "exit 1" in workflow
    assert "WARNING: OpenSSL libraries should remain system-provided" in workflow
    assert "OpenSSL libraries must remain system-provided in PR-built packages." not in workflow
    assert "No Linux shared libraries found" in workflow


def test_verify_examples_live_checks_only_agent_response_body() -> None:
    script = _verify_examples_script()
    workflow = _verify_examples_workflow()

    assert "answer_body=\"$(awk '/Agent Response/{capture=1; next} capture {print}'" in script
    assert 'grep -qi -- "$VERIFY_EXPECTED_ANSWER" <<<"$answer_body"' in script
    assert 'grep -qi -- "$VERIFY_EXPECTED_ANSWER" <<<"$output"' not in script
    assert "VERIFY_EXPECTED_ANSWER_TERMS" in script
    assert 'validate_expected_answer_terms "$answer_body"' in script
    assert "agent response contains an error" in script
    assert "unset GOPHER_SDK_TEST" in workflow
    assert 'VERIFY_LIVE_PROMPT="Get my mail profile"' in workflow
    assert 'VERIFY_EXPECTED_ANSWER="james.lu@gopher.security"' in workflow
    assert "Draft ID,Message ID,Thread ID" not in workflow


def test_verify_examples_live_logs_redact_agent_output() -> None:
    script = _verify_examples_script()

    assert "log_live_failure_diagnostics" in script
    assert "live output redacted:" in script
    assert "answer redacted" in script
    assert "answer_excerpt" not in script
    assert "${name}: ${answer_excerpt}" not in script
    assert "printf '%s\\n' \"$output\"\n      fail \"${name} live:" not in script


def test_verify_examples_cleanup_trap_covers_project_creation() -> None:
    script = _verify_examples_script()
    main_body = script[script.index("main() {") :]

    assert main_body.index("trap cleanup EXIT") < main_body.index("create_project")


def test_verify_examples_offline_checks_stable_missing_env_markers() -> None:
    script = _verify_examples_script()

    assert "missing_required_env_marker" in script
    assert "expected missing-env exit status 1" in script
    assert 'grep -Fxq "$expected_marker"' in script
    assert "must (both |all )?be set" not in script

    expected_markers = {
        "create_by_url.py": "ERROR: missing-required-env: GOPHER_MCP_URL,LLM_MODEL",
        "create_by_api_key.py": "ERROR: missing-required-env: GOPHER_API_KEY,LLM_MODEL",
        "create_by_json.py": "ERROR: missing-required-env: LLM_MODEL",
        "create_by_server_id.py": (
            "ERROR: missing-required-env: "
            "GOPHER_API_KEY,GOPHER_MCP_SERVER_ID,LLM_MODEL"
        ),
        "create_by_server_name.py": (
            "ERROR: missing-required-env: "
            "GOPHER_API_KEY,GOPHER_MCP_SERVER_NAME,LLM_MODEL"
        ),
        "create_by_gateway_id.py": (
            "ERROR: missing-required-env: "
            "GOPHER_API_KEY,GOPHER_MCP_GATEWAY_ID,LLM_MODEL"
        ),
        "create_by_gateway_name.py": (
            "ERROR: missing-required-env: "
            "GOPHER_API_KEY,GOPHER_MCP_GATEWAY_NAME,LLM_MODEL"
        ),
    }

    for filename, marker in expected_markers.items():
        assert marker in _api_example(filename)


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


def test_publish_workflow_removes_bundled_linux_openssl_after_copy() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish-packages.yml").read_text()
    copy_step = workflow[workflow.index("- name: Copy binaries to package") :]

    assert 'if [[ "${{ matrix.platform }}" == linux-* ]]; then' in copy_step
    assert "-name 'libssl.so*'" in copy_step
    assert "-name 'libcrypto.so*'" in copy_step
    assert "-delete" in copy_step


def test_publish_workflow_extracts_release_notes_from_versioned_changelog() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish-packages.yml").read_text()
    release_notes_step = workflow[workflow.index("- name: Generate release notes") :]

    assert 'awk -v version="$VERSION"' in release_notes_step
    assert '"^## \\\\[\" version "\\\\]"' in release_notes_step
    assert "sed '/^$/d' > changes.tmp" in release_notes_step
    assert "cat changes.tmp >> RELEASE_NOTES.md" in release_notes_step
    assert "No CHANGELOG.md entry found for ${VERSION}" in release_notes_step
    assert "## \\[Unreleased\\]" not in release_notes_step
    assert "wc -l < RELEASE_NOTES.md" not in release_notes_step
