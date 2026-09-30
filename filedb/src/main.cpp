#include "CLI/CLI.hpp"
#include <fmt/core.h>
#include <fmt/color.h>
#include <spdlog/spdlog.h>
#include <CLI/CLI.hpp>

int main(int argc, char *argv[]) {
  CLI::App app{"File-based data retrieval and manipulation program"};
  argv = app.ensure_utf8(argv);

  // CLI11_PARSE(app, argc, argv);
  try {
    app.parse(argc, argv);
  } catch (const CLI::ParseError &e) {
    return app.exit(e);
  }
  
  spdlog::info("Hello, world! {}", 42);
  
  return 0;
}
