"""Local-only browser fixture for EnvironmentView lifecycle verification."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, send_from_directory
from werkzeug.serving import make_server

from swarm_nav.web import create_assets_blueprint


ROOT = Path(__file__).resolve().parents[2]
app = Flask(__name__)
app.register_blueprint(create_assets_blueprint(), url_prefix="/swarm-nav")


@app.get("/")
def fixture():
    return Response(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="/swarm-nav/assets/environment-view.css">
  <script type="importmap">
    {"imports": {
      "three": "/node_modules/three/build/three.module.js",
      "three/addons/": "/node_modules/three/examples/jsm/"
    }}
  </script>
  <style>html,body{margin:0;background:#0c0d0c}#viewer{width:640px;height:420px}</style>
</head>
<body>
  <div id="viewer"></div>
  <script type="module">
    import { EnvironmentView } from '/swarm-nav/assets/environment-view.js';
    const world = {
      size: 500,
      nest: { x: 10, y: 250, z: 250 },
      agents: [
        { id: 0, x: 10, y: 250, z: 250, profile: 'Neutral' },
        { id: 1, x: 18, y: 252, z: 248, profile: 'Offensive' },
        { id: 2, x: 16, y: 246, z: 251, profile: 'Defensive' }
      ],
      obstacles: [{ id: 'tower', x: 150, y: 180, z: 0, w: 16, h: 120 }]
    };
    window.environmentView = new EnvironmentView(document.getElementById('viewer'), world);
    window.initialWorld = world;
    window.fixtureReady = true;
  </script>
</body>
</html>""",
        mimetype="text/html",
    )


@app.get("/node_modules/three/<path:filename>")
def three_asset(filename: str):
    return send_from_directory(ROOT / "node_modules" / "three", filename)


if __name__ == "__main__":
    server = make_server("127.0.0.1", 0, app)
    print(server.server_port, flush=True)
    server.serve_forever()
