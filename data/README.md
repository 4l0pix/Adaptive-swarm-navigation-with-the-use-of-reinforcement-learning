# Experiment data

I kept `pathfinding-experiments.csv` as a complete result snapshot from the v0.5 simulator. It contains 10 randomized tests, 100 start-goal tasks per test, and one row for each of the four formation profiles, for 4,000 rows in total.

Each row records:

- test, task, formation profile, start/goal coordinates, and Euclidean distance;
- success, path length, and traversal cost for Dijkstra;
- success, path length, and traversal cost for A*;
- success, path length, and traversal cost for Safety First;
- success, path length, and traversal cost for Balanced Navigation.

Generate the concise summary shown in the root README:

```bash
python scripts/summarize_results.py data/pathfinding-experiments.csv
```

The simulator can create new CSV and JSON files, but they are ignored by default. Before adding a run here, record the simulator and dependency versions, random seed when one was fixed, number of tests, and number of paths per test. That context matters because the environments and tasks are generated stochastically.

The dataset is licensed as repository content under CC BY 4.0. Cite the thesis when using it in academic work.
