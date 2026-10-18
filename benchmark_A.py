
#!/usr/bin/env python3

import argparse
import csv
import re
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = 11  # 1 warmup + 10 measured trials

FILEDB_TIME_RE = re.compile(
    r"Execution took\s+([\d.]+)\s+seconds\s+"
    r"\(([\d.]+)\s+ms\)\."
)



DB_TIME_RE = re.compile(
    r"(?mi)^\s*(?:Time:|时间[:：]?)\s*([\d.]+)\s*"
    r"(milliseconds?|msecs?|ms|seconds?|secs?|s)"
    r"(?:\s*\([^)]*\))?\s*$"
)



def run_filedb(pattern):
    result = subprocess.run(
        [
            "just",
            "run-release",
            "dataset/tsv/title.basics.tsv",
            "find",
            "primaryTitle",
            pattern,
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"FileDB failed (exit code {result.returncode}):\n"
            f"{result.stderr[-4000:]}"
        )

    matches = list(FILEDB_TIME_RE.finditer(result.stderr))

    if len(matches) != 1:
        raise RuntimeError(
            "Could not find exactly one FileDB timing line.\n"
            f"stderr:\n{result.stderr[-2000:]}"
        )

    match = matches[0]
    seconds = float(match.group(1))
    milliseconds = float(match.group(2))

    return seconds, milliseconds, match.group(0)


def run_database(recipe, pattern):
    # Escape SQL string-literal quotes.
    escaped_pattern = pattern.replace("'", "''")

    query = (
        "SELECT * FROM titles "
        f"WHERE primary_title LIKE '%{escaped_pattern}%';"
    )

    # All 11 queries run in the same database session.
    commands = [
        r"\set ON_ERROR_STOP on",
        r"\timing on",
        r"\pset pager off",
        *([query] * RUNS),
        r"\q",
    ]

    result = subprocess.run(
        ["just", recipe],
        cwd=ROOT,
        input="\n".join(commands) + "\n",
        capture_output=True,
        text=True,
    )

    output = result.stdout + "\n" + result.stderr

    if result.returncode != 0:
        raise RuntimeError(
            f"Database command 'just {recipe}' failed "
            f"(exit code {result.returncode}):\n"
            f"{output[-4000:]}"
        )

    matches = list(DB_TIME_RE.finditer(output))

    if len(matches) != RUNS:
        raise RuntimeError(
            f"'just {recipe}': expected {RUNS} timing lines, "
            f"but found {len(matches)}.\n"
            "Check the connection recipe and timing output.\n"
            f"Output tail:\n{output[-4000:]}"
        )

    timings = []

    for match in matches:
        value = float(match.group(1))
        unit = match.group(2).lower()

        if unit in {"s", "sec", "secs", "second", "seconds"}:
            milliseconds = value * 1000
        else:
            milliseconds = value

        timings.append(
            (milliseconds / 1000, milliseconds, match.group(0))
        )

    return timings


def record(rows, backend, iteration, seconds, milliseconds, raw):
    phase = "warmup" if iteration == 0 else "trial"

    rows.append({
        "backend": backend,
        "iteration": iteration,
        "phase": phase,
        "seconds": f"{seconds:.9f}",
        "milliseconds": f"{milliseconds:.3f}",
        "raw_timing": raw,
    })

    print(
        f"{backend:10s} | {phase:6s} | "
        f"run {iteration:02d} | {milliseconds:10.3f} ms"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark substring searches across three backends."
    )
    parser.add_argument(
        "pattern",
        nargs="?",
        default="XXX",
        help="Substring to search for (default: XXX)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="benchmark_results.csv",
        help="Output CSV path (default: benchmark_results.csv)",
    )
    args = parser.parse_args()

    rows = []

    # 1. FileDB: 11 separate command invocations.
    print("\n=== FileDB ===")

    for iteration in range(RUNS):
        seconds, milliseconds, raw = run_filedb(args.pattern)
        record(
            rows, "FileDB", iteration,
            seconds, milliseconds, raw,
        )

    # 2. PostgreSQL and 3. openGauss.
    # Each database uses one connection for all 11 queries.
    for backend, recipe in [
        ("PostgreSQL", "connect-pg"),
        ("openGauss", "connect-gauss"),
    ]:
        print(f"\n=== {backend} ===")

        timings = run_database(recipe, args.pattern)

        for iteration, (seconds, milliseconds, raw) in enumerate(timings):
            record(
                rows, backend, iteration,
                seconds, milliseconds, raw,
            )

    # Save every measurement, including warmups.
    output_path = Path(args.output)

    if not output_path.is_absolute():
        output_path = ROOT / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "backend",
        "iteration",
        "phase",
        "seconds",
        "milliseconds",
        "raw_timing",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults saved to: {output_path}")

    # Summarize measured trials only; exclude iteration 0.
    print("\n=== Summary (10 trials; warmup excluded) ===")

    for backend in ["FileDB", "PostgreSQL", "openGauss"]:
        values = [
            float(row["milliseconds"])
            for row in rows
            if row["backend"] == backend
            and row["phase"] == "trial"
        ]

        print(
            f"{backend:10s} | "
            f"mean: {statistics.mean(values):10.3f} ms | "
            f"median: {statistics.median(values):10.3f} ms"
        )


if __name__ == "__main__":
    main()
