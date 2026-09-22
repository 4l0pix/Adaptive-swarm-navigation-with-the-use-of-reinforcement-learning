"""Browser assets for the public swarm environment viewer."""

from pathlib import Path


def create_assets_blueprint():
    """Create the Flask blueprint that serves the versioned browser API."""
    from flask import Blueprint

    return Blueprint(
        "swarm_nav_assets",
        __name__,
        static_folder=str(Path(__file__).parent / "static"),
        static_url_path="/assets",
    )


__all__ = ["create_assets_blueprint"]
