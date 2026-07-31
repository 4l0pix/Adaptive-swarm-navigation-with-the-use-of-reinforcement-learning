# Reproducibility and provenance

## Source snapshot

I brought the simulator into this repository from the `0.5/` directory of [`4l0pix/Optimal-Swarm-Formation-For-Problem-Solving`](https://github.com/4l0pix/Optimal-Swarm-Formation-For-Problem-Solving) at commit:

```text
bbc670182b026a29de66c0a7f418e1085a9d6748
```

The earlier repository does not have a `v0.5` tag or branch; version 0.5 is identified by the directory name. I kept that source under `simulation/` and recorded the changes made for this thesis repository in `CHANGELOG.md`.

## Software environment

- Python 3.11 or 3.12
- Flask 3.1.x
- NumPy 2.2.x
- A current browser with WebGL support
- Network access for the Three.js, Chart.js, and Google Fonts CDN resources used by the interface

Set up and verify the local environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m compileall -q simulation tests
python -m unittest discover -s tests -v
```

## Run a fresh simulation

```bash
python simulation/app.py
```

Open `http://127.0.0.1:5000`. Each reset creates a new nest position, initial velocities, obstacle layout, and set of experiment tasks. The variation is deliberate because the swarm is meant to be tested under changing conditions. If you need to reproduce one exact run, keep its random seed together with the exported CSV or JSON file.

## Archived result snapshot

`data/pathfinding-experiments.csv` contains the curated aggregate used by this repository overview:

- 10 randomized tests;
- 100 start-goal tasks per test;
- 4 formation profiles per task;
- 4 pathfinding algorithms per row;
- 4,000 profile-level rows and 16,000 algorithm observations.

Recreate the summary table with:

```bash
python scripts/summarize_results.py data/pathfinding-experiments.csv
```

I kept this CSV as a record of one complete experiment batch. A new simulator run should not overwrite it. Give any new dataset a descriptive filename and add its setup to `data/README.md`.

## Determinism boundaries

The smoke tests seed NumPy and turn off the asynchronous background loop, which keeps the short checks repeatable. Long browser-driven experiments are not guaranteed to be identical down to every value: thread timing, floating-point libraries, random world generation, and browser timing can all influence a run.

## Refresh the screenshots

With the Flask server running locally, install the optional browser tooling and capture the two repository images:

```bash
npm install
npm run screenshots
```

Set `SWARM_SCREENSHOT_URL` if the application is not running at `http://127.0.0.1:5000`. The capture fails when the page reports a browser or asset-loading error.

## Interpretation

The simulator is a practical companion to the thesis, but the interface alone does not explain the full method. Chapter 6 describes the experiment assumptions, while Chapter 7 discusses what is still missing. In particular, the model uses static obstacles, simplified sensing, ideal localization, and reliable communication - conditions that would not hold on physical robots.
