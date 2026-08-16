---
paths: "**/*.cpp", "**/*.cc", "**/*.h", "**/*.hpp", "**/CMakeLists.txt"
---

# C++ Rules

Target C++20 minimum (GCC 13+, Clang 16+, MSVC 17.6+). Use CMake 3.28+ with modern target-based configuration. Prefer modern idioms, strict warnings, and static analysis throughout.

## Tooling

- **Formatter:** clang-format (project `.clang-format` at repo root)
- **Static analysis:** clang-tidy with checks: `modernize-*`, `bugprone-*`, `performance-*`, `readability-*`, `cppcoreguidelines-*`
- **Testing:** GoogleTest + GoogleMock
- **Package manager:** vcpkg (preferred) or Conan 2 for private registries
- **Build system:** CMake 3.28+ with `CMakePresets.json`
- **IDE support:** clangd (runs clang-tidy in real-time)

## Ownership and Resource Management

Use RAII for all resource management. Never call `new`/`delete` directly.

- **Default:** `std::unique_ptr<T>` for single ownership
- **Shared ownership:** `std::shared_ptr<T>` only when ownership is genuinely shared
- **Breaking cycles:** `std::weak_ptr<T>` to break `shared_ptr` reference cycles
- Use `std::make_unique` and `std::make_shared` for construction
- Prefer value types and stack allocation when object lifetime is scoped

## `constexpr` and `const`

Apply `constexpr` and `const` wherever possible. Prefer `constexpr` functions for compile-time evaluation. Use `consteval` for functions that must always run at compile time. Mark variables `const` unless mutation is required.

## C++20 Features

- **Concepts** over SFINAE for template constraints — clearer errors, more readable
- **`std::format`** over printf/iostream for string formatting
- **`std::span<T>`** for non-owning buffer/array parameters
- **`std::string_view`** for non-owning string parameters (do not store — the caller owns the data)
- **Designated initializers** for aggregate types to improve readability
- **Three-way comparison (`<=>`)** for custom types instead of writing all six operators
- **`[[nodiscard("reason")]]`** on functions whose return value must not be silently discarded

## C++23 Features (Where Available)

Use these when the project's minimum compiler version supports them:

- **`std::expected<T, E>`** for error handling that carries error information (preferred over exceptions for expected failure paths)
- **Monadic `std::optional`** — use `.and_then()`, `.transform()`, `.or_else()` for chaining
- **`std::print` / `std::println`** over `std::cout` for formatted output

## CMake

Use modern target-based CMake exclusively. Never set global variables for compile settings.

- Set standard per-target: `target_compile_features(mylib PUBLIC cxx_std_20)` — not `CMAKE_CXX_STANDARD`
- Link per-target: `target_link_libraries(myapp PRIVATE mylib)`
- Use `CMakePresets.json` for build configurations (debug, release, CI)
- **Never use `file(GLOB)` for sources** — list source files explicitly so CMake detects additions/removals
- Export targets with `install(TARGETS ... EXPORT ...)` for library projects

## Compiler Warnings

Enable strict warnings. Treat warnings as errors in CI.

```cmake
target_compile_options(mylib PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-Wall -Wextra -Wpedantic -Werror>
    $<$<CXX_COMPILER_ID:MSVC>:/W4 /WX>
)
```

## Sanitizers

- **Debug builds:** Enable ASan + UBSan together (`-fsanitize=address,undefined`)
- **Thread safety:** Enable TSan separately (`-fsanitize=thread`) — TSan cannot combine with ASan
- Configure sanitizer builds in `CMakePresets.json` as dedicated presets

## Ranges

Use `std::ranges` and views for data transformation pipelines where they improve clarity. Not needed for simple `for` loops over a single container — a range-based `for` is fine there.

## Modules

**NOT the default.** Header/source pairs remain the standard approach. Consider C++20 modules only for greenfield projects using CMake 4.0+ where tooling support is confirmed.

## Coroutines

Use coroutines only with established library support (cppcoro, Boost.Asio, libunifex). Do not write custom promise types or awaitables unless building a coroutine library.

## Error Handling

- Use `std::expected<T, E>` (C++23) or a Result type for expected failure paths
- Reserve exceptions for truly exceptional conditions (programming errors, unrecoverable states)
- Never throw in destructors
- Mark functions `noexcept` when they genuinely cannot throw

## Documentation

- Document all public API types and functions with Doxygen-style comments (`///` or `/** */`)
- Add `@throws` when the caller must handle an error, and `@param`/`@return` only for a contract
  the signature cannot carry (a unit, a range, a lifetime), never to repeat a type. The tags sit
  below the one-sentence summary and outside its three-line cap in `comments.md`, one line per tag
- Prefer self-documenting names and types over verbose comments; length and the test for an
  inline comment are in `comments.md`

## No `std::cout` in Library Code

Library code must not write to `stdout`/`stderr` directly. Use a logging abstraction (spdlog, fmtlib + custom sink) or accept a callback/sink. Application code initializes the logger and controls output.
