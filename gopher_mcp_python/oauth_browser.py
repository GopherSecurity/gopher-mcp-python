"""Browser opener for SDK-side OAuth authorization URLs."""

import sys
import webbrowser
from typing import Any, Dict, Optional


def open_authorization_url(
    url: str,
    open_browser: Optional[bool] = None,
    opener: Any = None,
) -> Dict[str, Any]:
    """Open an OAuth authorization URL, unless explicitly disabled."""
    if open_browser is False:
        return {"opened": False, "url": url}

    open_fn = opener if opener is not None else webbrowser.open
    try:
        opened = bool(open_fn(url))
    except Exception as exc:
        raise RuntimeError(f"Failed to open OAuth authorization URL {url}: {exc}") from exc
    result: Dict[str, Any] = {"opened": opened, "url": url}
    if opened:
        result["command"] = _command_for_platform(sys.platform)
    return result


def _command_for_platform(platform: str) -> str:
    if platform == "darwin":
        return "open"
    if platform == "win32":
        return "cmd"
    return "xdg-open"
