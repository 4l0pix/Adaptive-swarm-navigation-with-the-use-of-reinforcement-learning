"""Packaging and integration contracts for the public browser API."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from flask import Flask

from swarm_nav.web import create_assets_blueprint


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = REPOSITORY_ROOT / "simulation" / "static" / "js" / "main.js"
TEMPLATE = REPOSITORY_ROOT / "simulation" / "templates" / "index.html"


class EnvironmentViewApiTests(unittest.TestCase):
    def test_asset_blueprint_serves_module_and_css(self) -> None:
        app = Flask(__name__)
        app.register_blueprint(create_assets_blueprint(), url_prefix="/swarm-nav")
        client = app.test_client()

        module = client.get("/swarm-nav/assets/environment-view.js")
        styles = client.get("/swarm-nav/assets/environment-view.css")
        try:
            self.assertEqual(module.status_code, 200)
            self.assertIn(b"export class EnvironmentView", module.data)
            self.assertIn(b"validateEnvironmentWorld", module.data)
            self.assertEqual(styles.status_code, 200)
            self.assertIn(b".environment-view__controls", styles.data)
        finally:
            module.close()
            styles.close()

    def test_thesis_dashboard_uses_packaged_environment_view(self) -> None:
        source = MAIN_JS.read_text()
        template = TEMPLATE.read_text()

        self.assertIn("EnvironmentView", source)
        self.assertIn("new EnvironmentView", source)
        self.assertNotIn("new THREE.WebGLRenderer", source)
        self.assertNotIn("function init3D", source)
        self.assertNotIn("function updateAgents3D", source)
        self.assertIn("/swarm-nav/assets/environment-view.css", template)
        self.assertNotIn('id="btn-fog-toggle"', template)
        self.assertNotIn("\U0001f441", template)

    def test_wheel_contains_browser_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    directory,
                    str(REPOSITORY_ROOT),
                ],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            wheels = list(Path(directory).glob("swarm_nav-0.7.0-*.whl"))
            self.assertEqual(len(wheels), 1, result.stdout + result.stderr)
            with zipfile.ZipFile(wheels[0]) as wheel:
                names = set(wheel.namelist())
            self.assertIn("swarm_nav/web/static/environment-view.js", names)
            self.assertIn("swarm_nav/web/static/environment-view.css", names)


if __name__ == "__main__":
    unittest.main()
