
#!/usr/bin/env python3

import argparse
import csv
import re
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = 11  # 1 warmup + 10 measured trials

OLD = "T"
NEW = "Ttt"

FILEDB_TIME_RE = re.compile(
    r"Execution took\s+([\d.]+)\s+seconds\s+"
    r"\(([\d.]+)\s+ms\)\."
)

DB_TIME_RE = re.compile(
    r"(?mi)^\s*(?:Time:|时间[:：]?)\s*([\d.]+)\s*"
    r"(milliseconds?|msecs?|ms|seconds?|secs?|s)"
    r"(?:\s*\([^)]*\))?\s*$"
)

UPDATE_SQL = """
UPDATE people
SET primary_name = replace(primary_name, 'T', 'Ttt')
WHERE primary_name LIKE '%T%';
""".strip()

REVERSE_UPDATE_SQL = """
UPDATE people
SET primary_name = replace(primary_name, 'Ttt', 'T')
WHERE primary_name LIKE '%Ttt%';
""".strip()


def run_just_input(recipe, commands):
    """Run a just recipe and feed commands to its stdin."""
    return subprocess.run(
        ["just", recipe],
        cwd=ROOT,
        input="\n".join(commands) + "\n",
        capture_output=True,
        text=True,
    )


def check_result(result, description):
    output = result.stdout + "\n" + result.stderr

    if result.returncode != 0:
        raise RuntimeError(
            f"{description} failed (exit code {result.returncode}):\n"
            f"{output[-4000:]}"
        )

    return output


# ------------------------------------------------------------
# FileDB
# ------------------------------------------------------------

def restore_tsv():
    """Rebuild the TSV dataset as a recovery fallback."""
    print("  Restoring TSV with just rebuild-tsv...", flush=True)

    result = subprocess.run(
        ["just", "rebuild-tsv"],
        cwd=ROOT,
    )

    if result.returncode != 0:
        raise RuntimeError("just rebuild-tsv failed")


def run_filedb_update(old, new):
    """Execute one FileDB update and return its stderr."""
    result = subprocess.run(
        [
            "just",
            "run-release",
            "dataset/tsv/name.basics.tsv",
            "update",
            "primaryName",
            old,
            new,
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"FileDB update {old!r} -> {new!r} failed:\n"
            f"{result.stderr[-4000:]}"
        )

    return result.stderr


def parse_filedb_timing(stderr):
    matches = list(FILEDB_TIME_RE.finditer(stderr))

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one FileDB timing line, found {len(matches)}.\n"
            f"stderr:\n{stderr[-2000:]}"
        )

    match = matches[0]

    return (
        float(match.group(1)),
        float(match.group(2)),
        match.group(0),
    )


def run_filedb_trial():
    """
    Measure the forward update, then reverse it outside the
    measured interval. Rebuild the TSV if anything goes wrong.
    """
    try:
        stderr = run_filedb_update(OLD, NEW)
        timing = parse_filedb_timing(stderr)

    except BaseException:
        print(
            "  Forward update failed or was interrupted; "
            "rebuilding TSV...",
            flush=True,
        )
        restore_tsv()
        raise

    print("  Reversing replacement...", flush=True)

    try:
        run_filedb_update(NEW, OLD)

    except BaseException:
        print(
            "  Reverse update failed; rebuilding TSV...",
            flush=True,
        )
        restore_tsv()
        raise

    return timing


# ------------------------------------------------------------
# PostgreSQL / openGauss
# ------------------------------------------------------------

def run_database_reverse(recipe):
    """Recover a completed forward update in a fresh session."""
    commands = [
        r"\set ON_ERROR_STOP on",
        r"\pset pager off",
        r"\timing off",
        REVERSE_UPDATE_SQL,
        r"\q",
    ]

    result = run_just_input(recipe, commands)
    check_result(result, f"Recovery using just {recipe}")


def run_database_trial(recipe):
    """
    Run one measured UPDATE followed by its inverse.

    Each trial uses a separate database session. Only the
    forward UPDATE is timed; the inverse is not timed.
    """
    commands = [
        r"\set ON_ERROR_STOP on",
        r"\pset pager off",
        r"\timing off",
        r"\timing on",
        UPDATE_SQL,
        r"\echo __BENCH_UPDATE_DONE__",
        r"\timing off",
        REVERSE_UPDATE_SQL,
        r"\echo __BENCH_RESTORE_DONE__",
        r"\q",
    ]

    result = run_just_input(recipe, commands)
    output = result.stdout + "\n" + result.stderr

    update_done = "__BENCH_UPDATE_DONE__" in output
    restore_done = "__BENCH_RESTORE_DONE__" in output

    # If the forward UPDATE committed but its inverse failed,
    # attempt recovery before reporting the error.
    if update_done and not restore_done:
        print(
            "  Restoration did not complete; attempting recovery...",
            flush=True,
        )

        try:
            run_database_reverse(recipe)

        except Exception as exc:
            raise RuntimeError(
                f"Automatic recovery failed for {recipe}. "
                "The database may still contain modified names."
            ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"'just {recipe}' failed (exit code {result.returncode}):\n"
            f"{output[-4000:]}"
        )

    if not update_done or not restore_done:
        raise RuntimeError(
            f"'just {recipe}' did not produce the expected completion "
            f"markers. Update completed: {update_done}; "
            f"restoration completed: {restore_done}.\n"
            f"Output:\n{output[-4000:]}"
        )

    matches = list(DB_TIME_RE.finditer(output))

    if len(matches) != 1:
        raise RuntimeError(
            f"'just {recipe}': expected exactly one timing line, "
            f"found {len(matches)}.\n"
            f"Output:\n{output[-4000:]}"
        )

    match = matches[0]
    value = float(match.group(1))
    unit = match.group(2).lower()

    if unit in {"s", "sec", "secs", "second", "seconds"}:
        milliseconds = value * 1000
    else:
        milliseconds = value

    return milliseconds / 1000, milliseconds, match.group(0)


# ------------------------------------------------------------
# Benchmark runner and CSV output
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark substring-replacement UPDATEs across "
            "FileDB, PostgreSQL, and openGauss."
        )
    )

    parser.add_argument(
        "-o",
        "--output",
        default="benchmark_update_results.csv",
        help="CSV output path (default: benchmark_update_results.csv)",
    )

    args = parser.parse_args()

    output_path = Path(args.output)

    if not output_path.is_absolute():
        output_path = ROOT / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    fields = [
        "backend",
        "iteration",
        "phase",
        "seconds",
        "milliseconds",
        "raw_timing",
    ]

    with output_path.open(
        "w", newline="", encoding="utf-8"
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        csv_file.flush()

        def record(backend, iteration, timing):
            seconds, milliseconds, raw = timing
            phase = "warmup" if iteration == 0 else "trial"

            row = {
                "backend": backend,
                "iteration": iteration,
                "phase": phase,
                "seconds": f"{seconds:.9f}",
                "milliseconds": f"{milliseconds:.3f}",
                "raw_timing": raw,
            }

            rows.append(row)
            writer.writerow(row)
            csv_file.flush()

            print(
                f"{backend:10s} | {phase:6s} | "
                f"run {iteration:02d} | "
                f"{milliseconds:10.3f} ms",
                flush=True,
            )

        # 1. FileDB
        print("\n=== FileDB ===", flush=True)

        restore_tsv()

        for iteration in range(RUNS):
            print(
                f"Starting FileDB run {iteration:02d}/{RUNS - 1}...",
                flush=True,
            )

            timing = run_filedb_trial()
            record("FileDB", iteration, timing)

        # 2. PostgreSQL
        # 3. openGauss
        for backend, recipe in [
            ("PostgreSQL", "connect-pg"),
            ("openGauss", "connect-gauss"),
        ]:
            print(f"\n=== {backend} ===", flush=True)

            for iteration in range(RUNS):
                print(
                    f"Starting {backend} run "
                    f"{iteration:02d}/{RUNS - 1}...",
                    flush=True,
                )

                timing = run_database_trial(recipe)
                record(backend, iteration, timing)

    print(f"\nResults saved to: {output_path}")

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
