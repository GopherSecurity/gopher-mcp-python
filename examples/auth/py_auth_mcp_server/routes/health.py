"""Health check endpoint.

Provides a simple health check endpoint for monitoring
and load balancer health checks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, Flask, jsonify

# Module-level start time
_start_time: float = time.time()


@dataclass
class HealthResponse:
    """Health check response structure."""

    status: str  # 'ok' or 'error'
    timestamp: str
    version: str | None = None
    uptime: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "status": self.status,
            "timestamp": self.timestamp,
        }
        if self.version is not None:
            result["version"] = self.version
        if self.uptime is not None:
            result["uptime"] = self.uptime
        return result


def create_health_blueprint(version: str | None = None) -> Blueprint:
    """Create health check blueprint.

    Args:
        version: Optional version string to include in response.

    Returns:
        Flask Blueprint with health endpoint.
    """
    bp = Blueprint("health", __name__)

    @bp.route("/health", methods=["GET"])
    def health() -> Any:
        """Health check endpoint."""
        response = HealthResponse(
            status="ok",
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=version,
            uptime=int(time.time() - _start_time),
        )
        return jsonify(response.to_dict()), 200

    return bp


def register_health_routes(app: Flask, version: str | None = None) -> None:
    """Register the health check endpoint.

    Args:
        app: Flask application instance.
        version: Optional version string to include in response.
    """
    bp = create_health_blueprint(version)
    app.register_blueprint(bp)
