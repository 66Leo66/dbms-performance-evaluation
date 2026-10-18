# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "psycopg[binary]>=3.3.6",
# ]
# ///

import argparse
import os
from pathlib import Path

import psycopg
from psycopg import sql


# Source TSV columns -> destination PostgreSQL columns.
TABLES = [
    {
        "file": "title.basics.tsv",
        "table": "titles",
        "columns": [
            ("tconst", "tconst"),
            ("titleType", "title_type"),
            ("primaryTitle", "primary_title"),
            ("originalTitle", "original_title"),
            ("isAdult", "is_adult"),
            ("startYear", "start_year"),
            ("endYear", "end_year"),
            ("runtimeMinutes", "runtime_minutes"),
            ("genres", "genres"),
        ],
    },
    {
        "file": "name.basics.tsv",
        "table": "people",
        "columns": [
            ("nconst", "nconst"),
            ("primaryName", "primary_name"),
            ("birthYear", "birth_year"),
            ("deathYear", "death_year"),
            ("primaryProfession", "primary_profession"),
            ("knownForTitles", "known_for_titles"),
        ],
    },
    {
        "file": "title.principals.tsv",
        "table": "credits",
        "columns": [
            ("tconst", "tconst"),
            ("ordering", "ordering"),
            ("nconst", "nconst"),
            ("category", "category"),
            ("job", "job"),
            ("characters", "characters"),
        ],
    },
]


DDL = {
    "titles": """
              CREATE TABLE titles (
                                      tconst TEXT NOT NULL,
                                      title_type TEXT,
                                      primary_title TEXT,
                                      original_title TEXT,
                                      is_adult BOOLEAN,
                                      start_year INTEGER,
                                      end_year INTEGER,
                                      runtime_minutes INTEGER,
                                      genres TEXT
              )
              """,
    "people": """
              CREATE TABLE people (
                                      nconst TEXT NOT NULL,
                                      primary_name TEXT,
                                      birth_year INTEGER,
                                      death_year INTEGER,
                                      primary_profession TEXT,
                                      known_for_titles TEXT
              )
              """,
    "credits": """
               CREATE TABLE credits (
                                        tconst TEXT NOT NULL,
                                        ordering INTEGER NOT NULL,
                                        nconst TEXT NOT NULL,
                                        category TEXT,
                                        job TEXT,
                                        characters TEXT
               )
               """,
}


INTEGER_COLUMNS = {
    "birthYear",
    "deathYear",
    "startYear",
    "endYear",
    "runtimeMinutes",
    "ordering",
}


def parse_value(column: str, value: str, path: Path, line: int):
    """Convert TSV values to Python values for COPY."""
    if value == r"\N":
        return None

    if column in INTEGER_COLUMNS:
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(
                f"{path}:{line}: invalid integer "
                f"in column {column}: {value!r}"
            ) from exc

    if column == "isAdult":
        if value == "0":
            return False
        if value == "1":
            return True
        raise ValueError(
            f"{path}:{line}: invalid isAdult value: {value!r}"
        )

    return value


def load_table(conn, path: Path, spec: dict) -> int:
    """Load one TSV using PostgreSQL COPY FROM STDIN."""
    columns = spec["columns"]
    table = spec["table"]

    with path.open("r", encoding="utf-8", newline="") as f:
        # Do not interpret quotes in IMDb fields such as ["Self"].
        import csv

        reader = csv.reader(
            f,
            delimiter="\t",
            quoting=csv.QUOTE_NONE,
        )

        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"Empty TSV file: {path}")

        indices = {name: i for i, name in enumerate(header)}
        source_columns = [src for src, _ in columns]

        missing = [
            name for name in source_columns
            if name not in indices
        ]
        if missing:
            raise ValueError(
                f"{path}: missing expected columns {missing}"
            )

        copy_stmt = sql.SQL(
            "COPY {} ({}) FROM STDIN"
        ).format(
            sql.Identifier(table),
            sql.SQL(", ").join(
                sql.Identifier(dst) for _, dst in columns
            ),
        )

        count = 0

        with conn.cursor() as cur:
            with cur.copy(copy_stmt) as copy:
                for row in reader:
                    if len(row) != len(header):
                        raise ValueError(
                            f"{path}:{reader.line_num}: expected "
                            f"{len(header)} fields, got {len(row)}"
                        )

                    values = [
                        parse_value(
                            src,
                            row[indices[src]],
                            path,
                            reader.line_num,
                        )
                        for src, _ in columns
                    ]

                    copy.write_row(values)
                    count += 1

                    if count % 1_000_000 == 0:
                        print(
                            f"  {table}: {count:,} rows loaded",
                            flush=True,
                        )

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild IMDb tables from TSV files"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("."),
        help="Directory containing the three TSV files",
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection string; "
             "defaults to DATABASE_URL",
    )
    args = parser.parse_args()

    if not args.dsn:
        parser.error("Provide --dsn or set DATABASE_URL")

    # Validate every file before touching the database.
    sources = []
    for spec in TABLES:
        path = args.data_dir / spec["file"]
        if not path.is_file():
            raise FileNotFoundError(f"TSV file not found: {path}")
        sources.append((spec, path))

    # Successful exit commits; an exception rolls back the rebuild.
    with psycopg.connect(args.dsn) as conn:

        with conn.cursor() as cur:
            # Drop dependent tables first.
            for table in ("credits", "titles", "people"):
                cur.execute(
                    sql.SQL("DROP TABLE IF EXISTS {}").format(
                        sql.Identifier(table)
                    )
                )

            # Recreate empty tables.
            for spec in TABLES:
                cur.execute(DDL[spec["table"]])

        # Bulk load all source data.
        for spec, path in sources:
            print(f"Loading {path} -> {spec['table']} ...")
            count = load_table(conn, path, spec)
            print(f"  Loaded {count:,} rows")

        # Add constraints and indexes after bulk loading.
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE titles "
                "ADD PRIMARY KEY (tconst)"
            )
            cur.execute(
                "ALTER TABLE people "
                "ADD PRIMARY KEY (nconst)"
            )
            cur.execute(
                "ALTER TABLE credits "
                "ADD PRIMARY KEY (tconst, ordering)"
            )
            # cur.execute(
            #     "CREATE INDEX credits_nconst_idx "
            #     "ON credits (nconst)"
            # )
            #
            # for table in ("titles", "people", "credits"):
            #     cur.execute(
            #         sql.SQL("ANALYZE {}").format(
            #             sql.Identifier(table)
            #         )
            #     )

    print("Database rebuild completed successfully.")


if __name__ == "__main__":
    main()