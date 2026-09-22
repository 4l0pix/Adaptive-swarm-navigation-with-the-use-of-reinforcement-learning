# Changelog

## 0.7 - Versioned environment viewer API (2026-09-22)

- Added the packaged `swarm_nav.web` browser API with a Flask asset blueprint.
- Added a validated `EnvironmentView` contract for world, nest, agent, and obstacle state.
- Moved Three.js lifecycle, mesh reconciliation, exploration veil, resize handling, and controls into the shared component.
- Refactored the thesis dashboard to consume `EnvironmentView` as its single renderer source of truth.
- Added wheel, blueprint, source-of-truth, and Chromium lifecycle regression tests.
- Documented the shared frontend API and included its JavaScript and CSS in built wheels.

## 0.6 - Python research API (2026-09-15)

- Added the installable `swarm_nav` library with environment, obstacle, swarm, and simulation builders.
- Added validated immutable configurations, explicit obstacle editing, and bounded deployment.
- Added independent random streams and synchronous stepping for reproducible studies.
- Added replaceable profile policies and dynamics, with profile-weight synchronization.
- Added planner adapters with isolated settings and separate waypoint-count/geometric-length metrics.
- Added run manifests, detached snapshots, runnable examples, and a Python API guide.
- Parameterized shared exploration maps for rectangular worlds while retaining the browser workflow.
- Expanded tests and CI to cover research contracts and installed-package examples.

## 0.5 - Thesis artifact edition (2026-07-31)

- Reorganized the upstream `0.5/` simulation as a focused research repository.
- Added the final thesis PDF, research overview, architecture notes, and reproducibility guide.
- Added explicit MIT and CC BY 4.0 licensing scopes, provenance, and citation metadata.
- Added deterministic application smoke tests and a Python 3.11/3.12 CI matrix.
- Added a health endpoint, safe runtime configuration, and browser-verified screenshots.
- Curated the 10-test aggregate pathfinding result snapshot under `data/`.
- Removed the decorative repository cover and rewrote the project descriptions in the author's research voice.
- Removed the bundled thesis PDF and directed readers to the University of Thessaly Institutional Repository.
