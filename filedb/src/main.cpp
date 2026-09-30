#define DOCTEST_CONFIG_IMPLEMENT
#include "CLI/CLI.hpp"
#include "doctest/doctest.h"
#include <fmt/color.h>
#include <fmt/core.h>
#include <spdlog/spdlog.h>

int main(int argc, char *argv[]) {
  CLI::App app{"File-based data retrieval and manipulation program"};
  argv = app.ensure_utf8(argv);

  CLI::App *unittest_app =
      app.add_subcommand("unittest", "Run unittest using doctest framework.");
  unittest_app->allow_extras();
  unittest_app->prefix_command();
  unittest_app->fallthrough(false);
  unittest_app->set_help_flag();

  // CLI11_PARSE(app, argc, argv);
  try {
    app.parse(argc, argv);
  } catch (const CLI::ParseError &e) {
    return app.exit(e);
  }

  if (unittest_app->parsed()) {
    const auto &extras = unittest_app->remaining();

    std::vector<const char *> doctest_argv;
    doctest_argv.reserve(extras.size() + 1);
    doctest_argv.push_back(argv[0]);
    for (const auto &arg : extras) {
      doctest_argv.push_back(arg.c_str());
    }

    doctest::Context context;
    context.applyCommandLine(static_cast<int>(doctest_argv.size()),
                             doctest_argv.data());

    int res = context.run();
    if (context.shouldExit()) {
      return res;
    }
  }

  spdlog::info("Hello, world! {}", 42);

  return 0;
}
