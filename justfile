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

