#include <filesystem>
#include <chrono>
#include <format>
#include <fstream>
#include <iostream>
#include <unordered_map>
#include <vector>
#include <cerrno>
#include <unistd.h>

using Row = std::vector<std::string>;

Row parse_row(std::string_view line) {
  Row row;
  std::size_t start = 0;

  while (true) {
    const auto tab = line.find('\t', start);
    if (tab == std::string::npos) {
      row.emplace_back(line.substr(start));
      break;
    }

    row.emplace_back(line.substr(start, tab - start));
    start = tab + 1;
  }

  return row;
}

void write_row(std::ostream& out, const Row& row) {
  for (std::size_t i = 0; i < row.size(); ++i) {
    if (i > 0) {
      out.put('\t');
    }

    out << row[i];
  }

  out.put('\n');
}

struct Schema {
  std::vector<std::string> cols;
  std::unordered_map<std::string, std::size_t> col_idx;

  static Schema read(std::istream& in) {
    std::string line;

    if (!std::getline(in, line)) {
      throw std::runtime_error("Could not read from file");
    }

    if (!line.empty() && line.back() == '\r') {
      line.pop_back();
    }

    Schema schema;
    schema.cols = parse_row(line);

    // create column index
    for (std::size_t i = 0; i < schema.cols.size(); ++i) {
      const auto& name = schema.cols[i];

      if (!schema.col_idx.emplace(name, i).second) {
        throw std::runtime_error(
            "Duplicate column name: " + name
        );
      }
    }

    std::cerr << std::format("Parsed {} columns: ", schema.cols.size()) << std::endl;
    for (const auto& col : schema.cols) {
      std::cerr << std::format("`{}`", col) << std::endl;
    }

    return schema;
  }

  std::size_t column(std::string_view name) const {
    const auto it = col_idx.find(std::string(name));

    if (it == col_idx.end()) {
      throw std::runtime_error(
          "Unknown column: " + std::string(name)
      );
    }

    return it->second;
  }
};


std::size_t find_rows(
  const std::filesystem::path& filename,
  std::string_view field,
  std::string_view keyword,
  std::ostream& out = std::cout
  ) {
  // Open file
  std::fstream file(filename, std::ios::in);

  if (!file) {
    std::cerr << std::format("Could not open file") << std::endl;
    return 1;
  }

  const auto schema = Schema::read(file);

  for (const auto& [name, index] : schema.col_idx) {
    std::cerr << '[' << name << "] -> " << index << '\n';
  }

  const auto col = schema.column(field);
  const std::string key(keyword);

  write_row(out, schema.cols);

  std::size_t count = 0;
  std::size_t line_number = 1;
  std::string line;
  while (std::getline(file, line)) {
    line_number++;

    auto row = parse_row(line);

    // row must match schema
    if (row.size() != schema.cols.size()) {
      throw std::runtime_error("Invalid row at line " + std::to_string(line_number));
    }

    if (row[col].find(key) != std::string::npos) {
      write_row(out, row);
      count++;
    }
  }

  return count;
}

struct UpdateResult {
    std::size_t rows_changed = 0;
    std::size_t replacements = 0;
};

void write_record(std::ostream& out, const Row& row) {
    for (std::size_t i = 0; i < row.size(); ++i) {
        if (i > 0) {
            out.put('\t');
        }

        out << row[i];
    }

    out.put('\n');
}

UpdateResult update_tsv(
    const std::filesystem::path& filename,
    std::string_view field,
    std::string_view needle,
    std::string_view replacement
) {
    namespace fs = std::filesystem;

    if (needle.empty()) {
        throw std::invalid_argument("Search string cannot be empty");
    }

    if (needle.find_first_of("\t\r\n") != std::string_view::npos ||
        replacement.find_first_of("\t\r\n") != std::string_view::npos) {
        throw std::invalid_argument(
            "Search and replacement cannot contain tabs or newlines"
        );
    }

    std::ifstream in(filename, std::ios::binary);

    if (!in) {
        throw std::runtime_error("Cannot open input file");
    }

    const Schema schema = Schema::read(in);
    const std::size_t col = schema.column(field);

    // Temporary file in the same directory.
    fs::path temp = filename;
    temp += ".tmp";

    std::ofstream out(temp, std::ios::binary | std::ios::trunc);

    if (!out) {
        throw std::runtime_error("Cannot create temporary file");
    }

    UpdateResult result;

    try {
        write_record(out, schema.cols);

        std::string line;

        while (std::getline(in, line)) {
            // Handle CRLF input.
            if (!line.empty() && line.back() == '\r') {
                line.pop_back();
            }

            Row row = parse_row(line);

            if (row.size() != schema.cols.size()) {
                throw std::runtime_error("Malformed TSV row");
            }

            std::string& value = row[col];
            std::size_t pos = 0;
            std::size_t count = 0;

            while ((pos = value.find(needle, pos))
                   != std::string::npos) {
                value.replace(pos, needle.size(), replacement);
                pos += replacement.size();
                ++count;
            }

            if (count > 0) {
                ++result.rows_changed;
                result.replacements += count;
            }

            write_record(out, row);
        }

        if (in.bad()) {
            throw std::runtime_error("Error reading input file");
        }

        out.flush();

        if (!out) {
            throw std::runtime_error("Error writing temporary file");
        }

        out.close();

        if (!out) {
            throw std::runtime_error("Error closing temporary file");
        }

        in.close();

        if (result.replacements > 0) {
            fs::rename(temp, filename);
        } else {
            fs::remove(temp);
        }

    } catch (...) {
        out.close();

        std::error_code ec;
        fs::remove(temp, ec);

        throw;
    }

    return result;
}


int main(int argc, char *argv[]) {
  std::ios::sync_with_stdio(false);
  std::cerr << std::format("[DEBUG] PWD: {}", std::filesystem::current_path().string()) << std::endl;
  if (argc < 2) {
    std::cerr << std::format("Usage: {} <filename> find <field> <keyword>",
                             argv[0])
              << std::endl;
    std::cerr << std::format(
                     "Usage: {} <filename> update <field> <find> <replace>",
                     argv[0])
              << std::endl;
    return 1;
  }
  std::string filename = argv[1];


  const auto start = std::chrono::steady_clock::now();
  if (std::string command = argv[2]; command == "find") {
    auto matches = find_rows(
      filename,
      std::string(argv[3]),
      std::string(argv[4]),
      std::cout
    );
    std::cerr << std::endl;
    std::cerr << std::format("Found {} rows.", matches) << std::endl;
  } else if (command == "update") {
    const auto result = update_tsv(
            argv[1], argv[3], argv[4], argv[5]
        );

    std::cerr << std::format(
        "Updated {} rows; {} replacements.\n",
        result.rows_changed,
        result.replacements
    );
  } else {
    std::cerr << std::format("Unknown command: {}", command) << std::endl;
    return 1;
  }
  const auto end = std::chrono::steady_clock::now();
  const std::chrono::duration<double> elapsed = end - start;
  const auto elapsed_ms =
    std::chrono::duration_cast<std::chrono::milliseconds>(
        end - start
    );
  std::cerr << std::format("Execution took {} seconds ({} ms).", elapsed.count(), elapsed_ms.count()) << std::endl;

  return 0;
}