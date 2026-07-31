#!/usr/bin/env python3
"""Print the aggregate algorithm metrics used in the repository overview."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path


ALGORITHMS = ("Dijkstra", "AStar", "Safety", "Balanced")


def summarize(path: Path) -> list[dict[str, float | str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    if not rows:
        raise ValueError(f"No experiment rows found in {path}")

    summary: list[dict[str, float | str]] = []
    for algorithm in ALGORITHMS:
        costs = [float(row[f"{algorithm}_Cost"]) for row in rows]
        finite_costs = [cost for cost in costs if math.isfinite(cost)]
        lengths = [float(row[f"{algorithm}_Path_Length"]) for row in rows]
        successes = [int(row[f"{algorithm}_Success"]) for row in rows]
        summary.append(
            {
                "algorithm": algorithm,
                "success_rate": 100 * statistics.mean(successes),
                "mean_cost": statistics.mean(finite_costs),
                "mean_length": statistics.mean(lengths),
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()

    print("Algorithm         Success    Mean cost    Mean length")
    print("----------------  ---------  -----------  -----------")
    for item in summarize(args.csv_path):
        print(
            f"{item['algorithm']:<16}"
            f"{item['success_rate']:>8.1f}%"
            f"{item['mean_cost']:>13.3f}"
            f"{item['mean_length']:>13.2f}"
        )


if __name__ == "__main__":
    main()
