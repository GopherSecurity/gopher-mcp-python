#!/usr/bin/env python3
"""
Update gopher-security-mcp version across all files.

Usage:
    python scripts/update_version.py <gopher_security_mcp_version>

Example:
    python scripts/update_version.py v0.1.0-20260225-132506

This updates:
    - pyproject.toml version
    - gopher_security_mcp/__init__.py version
    - packages/*/pyproject.toml versions
    - packages/*/__init__.py versions
    - .github/workflows/publish-packages.yml versions
"""

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent

# Platform packages
PLATFORMS = [
    "darwin-arm64",
    "darwin-x64",
    "linux-arm64",
    "linux-x64",
    "win32-arm64",
    "win32-x64",
]


def parse_version(gopher_security_mcp_version: str) -> tuple[str, str]:
    """
    Convert gopher-security-mcp version tag to Python PEP 440 version.

    Args:
        gopher_security_mcp_version: e.g., "v0.1.0-20260225-132506" or "0.1.0-20260225-132506"

    Returns:
        tuple of (gopher_security_mcp_tag, python_version)
        e.g., ("v0.1.0-20260225-132506", "0.1.0.dev20260225132506")
    """
    # Remove 'v' prefix if present
    version = gopher_security_mcp_version.lstrip('v')

    # Parse version parts: 0.1.0-20260225-132506
    match = re.match(r'^(\d+\.\d+\.\d+)-(\d{8})-(\d{6})$', version)
    if match:
        base_version = match.group(1)
        date = match.group(2)
        time = match.group(3)
        # Python PEP 440 format: 0.1.0.dev20260225132506
        python_version = f"{base_version}.dev{date}{time}"
    else:
        # Fallback: just use the version as-is
        python_version = version.replace('-', '.')

    # Always include 'v' prefix for the tag
    gopher_security_mcp_tag = f"v{version}" if not gopher_security_mcp_version.startswith('v') else gopher_security_mcp_version

    return gopher_security_mcp_tag, python_version


def update_pyproject_toml(file_path: Path, version: str) -> None:
    """Update version in pyproject.toml."""
    content = file_path.read_text()
    updated = re.sub(
        r'version\s*=\s*"[^"]*"',
        f'version = "{version}"',
        content,
        count=1
    )
    file_path.write_text(updated)
    print(f"✓ Updated {file_path}")


def update_init_py(file_path: Path, version: str) -> None:
    """Update __version__ in __init__.py."""
    if not file_path.exists():
        print(f"⚠ Skipping {file_path} (not found)")
        return

    content = file_path.read_text()
    updated = re.sub(
        r'__version__\s*=\s*"[^"]*"',
        f'__version__ = "{version}"',
        content
    )
    file_path.write_text(updated)
    print(f"✓ Updated {file_path}")


def update_workflow(file_path: Path, gopher_security_mcp_tag: str, python_version: str) -> None:
    """Update versions in workflow file."""
    if not file_path.exists():
        print(f"⚠ Skipping {file_path} (not found)")
        return

    content = file_path.read_text()

    # Update GOPHER_SECURITY_MCP_VERSION
    content = re.sub(
        r'GOPHER_SECURITY_MCP_VERSION:\s*[^\n]+',
        f'GOPHER_SECURITY_MCP_VERSION: {gopher_security_mcp_tag}',
        content
    )

    # Update PACKAGE_VERSION
    content = re.sub(
        r'PACKAGE_VERSION:\s*[^\n]+',
        f'PACKAGE_VERSION: {python_version}',
        content
    )

    file_path.write_text(content)
    print(f"✓ Updated {file_path}")


def update_main_package(python_version: str) -> None:
    """Update main package version."""
    # pyproject.toml
    update_pyproject_toml(ROOT_DIR / "pyproject.toml", python_version)

    # gopher_security_mcp/__init__.py
    update_init_py(ROOT_DIR / "gopher_security_mcp" / "__init__.py", python_version)


def update_platform_packages(python_version: str) -> None:
    """Update all platform package versions."""
    for platform in PLATFORMS:
        pkg_dir = ROOT_DIR / "packages" / platform
        if not pkg_dir.exists():
            print(f"⚠ Skipping {platform} (directory not found)")
            continue

        # pyproject.toml
        update_pyproject_toml(pkg_dir / "pyproject.toml", python_version)

        # Find __init__.py (package name varies)
        pkg_name = f"gopher_security_mcp_native_{platform.replace('-', '_')}"
        init_py = pkg_dir / pkg_name / "__init__.py"
        update_init_py(init_py, python_version)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_version.py <gopher_security_mcp_version>")
        print("Example: python scripts/update_version.py v0.1.0-20260225-132506")
        sys.exit(1)

    gopher_security_mcp_version = sys.argv[1]
    gopher_security_mcp_tag, python_version = parse_version(gopher_security_mcp_version)

    print(f"\nUpdating versions:")
    print(f"  gopher-security-mcp tag: {gopher_security_mcp_tag}")
    print(f"  Python version:  {python_version}")
    print()

    # Update main package
    update_main_package(python_version)

    # Update platform packages
    update_platform_packages(python_version)

    # Update workflow
    workflow_path = ROOT_DIR / ".github" / "workflows" / "publish-packages.yml"
    update_workflow(workflow_path, gopher_security_mcp_tag, python_version)

    print("\n✅ Version update complete!")
    print()
    print("Next steps:")
    print("  1. Review changes: git diff")
    print(f"  2. Commit: git add -A && git commit -m 'Bump version to {python_version}'")
    print("  3. Push to trigger release: git push origin py_release")


if __name__ == "__main__":
    main()
