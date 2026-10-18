#import "@preview/ilm:2.1.1": *
#import "@preview/pillar:0.3.3"
#import "@preview/lilaq:0.6.0" as lq
#import "@preview/codly:2.0.0" as codly
#import "@preview/codly-languages:0.1.8": codly-languages
#show: codly.lang-set_(languages: codly-languages)
#show raw.where(block: true): codly.new

#set text(lang: "en")

#show: ilm.with(
  title: [A Comparative Evaluation of PostgreSQL, openGauss, and File-Based Data Processing],
  authors: "LI Yuanrui (12511921)",
  date: datetime.today(),
  abstract: [
    This project compares C++ file-based processing, PostgreSQL, and openGauss using IMDb data. Two workloads are evaluated: title retrieval by substring and person-name replacement. Each system is measured over ten trials after a warm-up. PostgreSQL is fastest for repeated title retrieval, with a median of 0.235 s, compared with 1.537 s for file-based processing and 1.208 s for openGauss. File-based processing is fastest for the update, at 3.178 s, compared with 14.983 s for PostgreSQL and 23.973 s for openGauss. The results show that relative performance depends on the workload, execution conditions, and storage guarantees of each implementation.
  ],
  // preface: [
  //   #align(center + horizon)[
  //     Thank you for using this template #emoji.heart \
  //     I hope you like it #emoji.face.smile
  //   ]
  // ],
  bibliography: bibliography("refs.bib"),
  figure-index: (enabled: true),
  table-index: (enabled: true),
  listing-index: (enabled: true),
  raw-text: (
    font: "JetBrains Mono",
  ),
)

#set text(
  font: (
    (name: "libertinus serif", covers: "latin-in-cjk"),
    "Noto Serif CJK SC",
  ),
)
#show smartquote: set text(font: "libertinus serif")

= Introduction
As datasets grew in size and complexity, efficiently storing, retrieving, and modifying data becomes increasingly important. While data can be stored in ordinary files and processed using general-purpose programming languages, such operations may require substantial manual work. Database management systems (DBMSs) provides an alternative by offering structured data storage, query languages, and advanced processing capabilities like indexing and transaction managing.

However, the advantages of a DBMS do not essentially mean better performance for every operation. A simple file-based program may be sufficient for simple queries, while a database benefits from mechanisms like indexing and query optimizing in complex scenarios. Furthermore, different DBMS implementations may have different performance under the same workload. Therefore, evaluating these systems requires experiments that consider both the operation kinds and the execution conditions.

In this project, we evaluate the performance of file-based data processing, PostgreSQL and, openGauss using the IMDb dataset. A C++ program is implemented to perform query and update operations directly on tab-separated value (TSV) files, serving as a baseline. By measuring execution times, we can investigate the performance differences between the three approaches and discuss the advantages and limitations of using a DBMS for data management.


= Dataset and Experimental Environment
== Dataset
We selected three datasets from IMDb Non-Commercial Datasets@imdb_noncommercial_datasets#footnote[Information courtesy of IMDb (https://www.imdb.com). Used with permission.]:

#pillar.table(
  cols: "llrr",
  [File],
  [Purpose],
  [Rows],
  [Size],
  [`title.basics.tsv`],
  [Film and title information],
  [12,870,866],
  [1.1G],
  [`name.basics.tsv`],
  [Person information],
  [15,741,193],
  [928M],
  [`title.principals.tsv`],
  [Relationships between titles and people],
  [102,341,841],
  [4.3G],
)

== System environment
The experiment is performed in the Windows Subsystem for Linux (WSL) environment running Arch Linux x86_64 with kernel `Linux 6.18.40.1-microsoft-standard-WSL2`. The CPU is Intel(R) Core(TM) Ultra 9 275HX (24) @ 3.07 GHz and plenty of memory (the host has 64 GB RAM installed, and the WSL environment is assigned more than 32 GB).

== DBMS versions
The evaluated DBMSs are run inside Docker, with the following versions:

#pillar.table(
  cols: "ll",
  [DBMS],
  [Version],
  [PostgreSQL],
  [`PostgreSQL 19rc1 (Debian 19~rc1-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit`],
  [openGauss],
  [`(openGauss 7.0.0 build 2397a86f) compiled at 2026-09-23 00:09:53 commit 1003 last mr 9774 release on x86_64-pc-linux-gnu, compiled by g++ (GCC) 10.3.0, 64-bit`],
)


== Database schema
The database schemas are defined as follows:
```sql
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
);
ALTER TABLE titles ADD PRIMARY KEY (tconst);
```

```sql
CREATE TABLE people (
  nconst TEXT NOT NULL,
  primary_name TEXT,
  birth_year INTEGER,
  death_year INTEGER,
  primary_profession TEXT,
  known_for_titles TEXT
);
ALTER TABLE people ADD PRIMARY KEY (nconst);
```

```sql
CREATE TABLE credits (
  tconst TEXT NOT NULL,
  ordering INTEGER NOT NULL,
  nconst TEXT NOT NULL,
  category TEXT,
  job TEXT,
  characters TEXT
);
ALTER TABLE credits ADD PRIMARY KEY (tconst, ordering);
```
= Experimental Design and Implementation
The implementation and benchmark scripts are available in the project repository: #link("https://github.com/66Leo66/dbms-performance-evaluation").

== Methodology
The file-based processing program operates on the TSV files directly. For DBMS, a script inserts into the database according to the TSV files.

For the file-based program, C++'s `std::chrono::steady_clock` is used to measure the execution time. For DBMS, we used the built-in `\timing on` command to let psql client output execution time of queries.

For each system and workload, first a warm-up trial is run, which is excluded from the summary; Then 10 consecutive measured trials are run. The median execution time and interquartile range were used to summarize performance, and the results are reviewed to ensure correctness of the systems.

== Experiment A: Title retrieval
This experiment retrieves title records whose `primaryTitle` contains a specified substring `XXX`. The implementation of the file-based program is to scan the TSV file line by line and test each title; The query used on DBMSs is:
```sql
SELECT * FROM titles WHERE primary_title LIKE '%XXX%';
```


== Experiment B: Person-name update
This experiment replaces every upper-case `T` in `primaryName` of people dataset with `Ttt`. The implementation of the file-based program is to scan the entire TSV file, modify the relevant fields while writing the result to a temporary file and finally replace the original file. The update command used on DBMSs is:
```sql
UPDATE people
SET primary_name = replace(primary_name, 'T', 'Ttt')
WHERE primary_name LIKE '%T%';
```

After every update, including the warm-up, the following reverse update restores the names:
```sql
UPDATE people
SET primary_name = replace(primary_name, 'Ttt', 'T')
WHERE primary_name LIKE '%Ttt%';
```
Only the forward update is timed, and the reverse update runs immediately afterward with timing disabled, in the same database session. In addition, the next trial opens a new session.

= Experimental Results
== Result of Experiment A: Title retrieval
#let retrieval-data = csv("benchmark_A_results.csv", row-type: dictionary)
#let backends = ("FileDB", "PostgreSQL", "openGauss")
#let median(values) = {
  let values = values.sorted()
  let middle = calc.quo(values.len(), 2)
  if calc.rem(values.len(), 2) == 0 {
    (values.at(middle - 1) + values.at(middle)) / 2
  } else {
    values.at(middle)
  }
}
#let summarize-trials(data) = backends.map(backend => {
  let values = data.filter(row => row.backend == backend and row.phase == "trial")
    .map(row => float(row.seconds)).sorted()
  let middle = calc.quo(values.len(), 2)
  let q1 = median(values.slice(0, middle))
  let q3 = median(values.slice(middle))
  (
    backend: backend,
    median: median(values),
    q1: q1,
    q3: q3,
    iqr: q3 - q1,
    minimum: values.first(),
    maximum: values.last(),
  )
})
#let retrieval-summary = summarize-trials(retrieval-data)

@tab-retrieval summarizes the ten measured trials, excluding the warm-up. Quartiles are calculated as the medians of the lower and upper halves of the sorted measurements.

#figure(
  pillar.table(
    cols: "lrr",
    [System], [Median (s)], [IQR (s)],
    ..retrieval-summary.map(result => (
      [#result.backend],
      [#calc.round(result.median, digits: 3)],
      [#calc.round(result.iqr, digits: 3)],
    )).flatten(),
  ),
  kind: table,
  caption: [Execution times of Experiment A.],
) <tab-retrieval>

#let timing-boxplot(summary, ymax) = lq.diagram(
    width: 100%,
    height: 6cm,
    ylabel: [Execution time (s)],
    xlim: (0.5, 3.5),
    ylim: (0, ymax),
    xaxis: (
      ticks: backends.enumerate().map(((i, backend)) => (i + 1, [#backend])),
      subticks: none,
    ),
    yaxis: (subticks: none),
    ..summary.enumerate().map(((i, result)) => {
      lq.boxplot(
        (
          median: result.median,
          q1: result.q1,
          q3: result.q3,
          whisker-low: result.minimum,
          whisker-high: result.maximum,
        ),
        x: i + 1,
        width: 0.4,
        fill: rgb("dce8f3"),
        stroke: 0.7pt + black,
        median: 1.2pt + black,
      )
    }),
  )

#figure(
  timing-boxplot(retrieval-summary, 1.7),
  caption: [Execution times of Experiment A],
) <fig-retrieval>

PostgreSQL has the shortest median execution time at 0.235 s, about 6.55 times as fast as FileDB and 5.15 times as fast as openGauss. openGauss takes 1.208 s, about 21.4% less time than FileDB.

The warm-up takes 1.757 s for FileDB, 7.214 s for PostgreSQL, and 23.431 s for openGauss. Both DBMSs are slower than FileDB on this first run, which may indicate that DBMS has its own overhead at first run, or that DBMS have a cache mechanic of some sort which would speed up later runs.

#pagebreak(weak: true)
== Result of Experiment B: Person-name update
#let update-data = csv("benchmark_B_results.csv", row-type: dictionary)
#let update-summary = summarize-trials(update-data)

@tab-update summarizes the ten measured trials using the same quartile calculation as Experiment A.

#figure(
  pillar.table(
    cols: "lrr",
    [System], [Median (s)], [IQR (s)],
    ..update-summary.map(result => (
      [#result.backend],
      [#calc.round(result.median, digits: 3)],
      [#calc.round(result.iqr, digits: 3)],
    )).flatten(),
  ),
  kind: table,
  caption: [Execution times of Experiment B.],
) <tab-update>

#figure(
  timing-boxplot(update-summary, 60),
  caption: [Execution times of Experiment B],
) <fig-update>

FileDB has the shortest median execution time at 3.178 s. PostgreSQL takes 14.983 s and openGauss takes 23.973 s, about 4.72 and 7.54 times the FileDB time, respectively. Both DBMSs show more variation in absolute time. PostgreSQL reaches 24.634 s in one measured trial, while openGauss reaches 57.270 s. These measurements are retained in the summary and the ranges shown in @fig-update.


= Discussion
== Title retrieval
PostgreSQL is fastest for repeated retrieval. The primary key on `tconst` does not support the condition on `primary_title`. FileDB splits every TSV row on each query, while database storage avoids this parsing. The drop from warm-up to measured times in PostgreSQL and openGauss suggests that cache reuse benefits repeated retrieval.

== Person-name update
Experiment B favours FileDB's sequential rewrite. The PostgreSQL checks in @tab-update-diagnostics help explain the additional database work. The scan timing is for a SELECT of `nconst` using the same `primary_name LIKE '%T%'` condition.

#figure(
  pillar.table(
    cols: "ll",
    [Measurement], [Value],
    [Total people], [15,741,192],
    [Matching people], [1,308,114 (8.31%)],
    [Only index], [`people_pkey`: B-tree on `nconst`],
    [Matching SELECT plan], [`Seq Scan on people`],
    [Matching SELECT time], [0.981 s],
    [Cumulative row updates], [28,778,508],
    [Cumulative HOT updates], [1,521,333 (5.29% of updates)],
  ),
  kind: table,
  caption: [PostgreSQL diagnostics after Experiment B.],
) <tab-update-diagnostics>

The index on `nconst` does not support the name condition, so PostgreSQL scans the table, taking 0.981 s in the diagnostic SELECT. Updating the 1.31 million matching rows then creates new row versions and WAL records for recovery@pg_wal. Most updates also require new index entries: only 5.29% use the heap-only tuple (HOT) optimization. Although `nconst` is unchanged, HOT requires enough free space on the original page for the new row version@pg_hot. openGauss also uses MVCC and WAL-based recovery, so similar update overhead likely contributes to its longer times@og_features.

== Repeated updates and storage guarantees
PostgreSQL records 22 updates per matching row: eleven forward updates and eleven reverse updates. Each reverse UPDATE generates further row versions, index changes, and WAL. Repeated updates can leave obsolete versions awaiting vacuum and add storage and maintenance work@pg_vacuum. This work can affect later measured updates even though restoration itself is untimed. Both DBMSs use the same reverse-update procedure, so restoration overhead is also a plausible contributor to openGauss's update times.

FileDB writes a temporary TSV sequentially, flushes the output stream, and renames the file. It implements neither transaction logging nor an explicit `fsync`. Its shorter execution time suits this simple batch rewrite, while PostgreSQL and openGauss also maintain database versions and recovery logs.


= Conclusion
PostgreSQL gives the best performance for repeated title retrieval, while file-based processing is fastest for the person-name update. The results show that the relative performance depends on the operation, execution conditions, and guarantees provided by each implementation. In particular, our experiments show that DBMS are efficient at data retrieval across large database, especially if such retrieval happens multiple times; DBMS, in comparison to file-based processing, also have stronger data and transaction consistency guarantees, which comes at a cost of overhead when doing operations like updating values.
