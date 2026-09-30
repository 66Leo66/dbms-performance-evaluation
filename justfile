#!/usr/bin/env just --justfile

# list avaliable recipes
default:
  just --list

build:
  cd filedb/ && bazel build //src:filedb

run *ARGS:
  cd filedb/ && bazel run //src:filedb -- {{ARGS}}

refresh-compile-commands:
  cd filedb/ && bazel build @hedron_compile_commands//:refresh_all
