#!/usr/bin/env just --justfile

# list avaliable recipes
default:
  just --list

# Build Debug
debug:
    cmake -S filedb -B filedb/cmake-build-debug-wsl -DCMAKE_BUILD_TYPE=Debug
    cmake --build filedb/cmake-build-debug-wsl --parallel

# Build Release
release:
    cmake -S filedb -B filedb/cmake-build-release-wsl -DCMAKE_BUILD_TYPE=Release
    cmake --build filedb/cmake-build-release-wsl --parallel

# Build Debug and run with arguments
run-debug *args: debug
    ./filedb/cmake-build-debug-wsl/FileDB {{args}}

# Build Release and run with arguments
run-release *args: release
    ./filedb/cmake-build-release-wsl/FileDB {{args}}

rebuild-pg:
    uv run --script dataset/import_data.py --data-dir dataset/tsv --dsn "postgresql://postgres:Gauss%40123@localhost:10001/postgres"

rebuild-gauss:
    uv run --script dataset/import_data.py --data-dir dataset/tsv --dsn "postgresql://gaussdb:Gauss%40123@localhost:10002/postgres"

[parallel]
rebuild-db: rebuild-pg rebuild-gauss

connect-pg:
    psql "postgresql://postgres:Gauss%40123@localhost:10001/postgres"

connect-gauss:
    psql "postgresql://gaussdb:Gauss%40123@localhost:10002/postgres"

download-tsv:
    wget https://datasets.imdbws.com/title.basics.tsv.gz -O- | gzip -dv > dataset/tsv/title.basics.tsv
    wget https://datasets.imdbws.com/name.basics.tsv.gz -O- | gzip -dv > dataset/tsv/name.basics.tsv
    wget https://datasets.imdbws.com/title.principals.tsv.gz -O- | gzip -dv > dataset/tsv/title.principals.tsv

rebuild-tsv:
    cp -v dataset/backup_tsv/name.basics.tsv dataset/tsv/name.basics.tsv
    cp -v dataset/backup_tsv/title.basics.tsv dataset/tsv/title.basics.tsv
    cp -v dataset/backup_tsv/title.principals.tsv dataset/tsv/title.principals.tsv