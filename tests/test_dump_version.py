"""Regression tests for release version dumping behavior."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dump_version_prefers_highest_version_tag_on_head() -> None:
    script = (ROOT / "dump-version.sh").read_text()

    points_at = "PREV_TAG=$(git tag --points-at HEAD --list 'v*' --sort=-v:refname | head -1)"
    describe = (
        "PREV_TAG=$(git describe --tags --abbrev=0 --match 'v*' HEAD "
        "2>/dev/null || true)"
    )

    assert points_at in script
    assert describe in script
    assert script.index(points_at) < script.index(describe)
