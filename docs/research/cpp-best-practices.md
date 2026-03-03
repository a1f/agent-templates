# Research: C++ Best Practices (2025-2026)

## Target: C++20 Minimum

C++20 is universally supported (GCC 16 defaults to it, Clang since v10, MSVC in VS 2022). C++23 is still experimental. Google targets C++20; Chromium targets C++23; LLVM/Qt target C++17 (conservative).

## Tooling Decisions

| Tool | Choice | Rationale |
|------|--------|-----------|
| Formatting | **clang-format** | Industry standard. No alternatives. |
| Static analysis | **clang-tidy + cppcheck** | Complementary. clang-tidy = primary (AST, auto-fix). cppcheck = CI (fast, low FP). |
| Testing | **GoogleTest** | Most widely used. Comprehensive matchers + GoogleMock. Catch2 as alternative. |
| Packages | **vcpkg** (or Conan 2) | Best CMake integration, 1700+ packages. Conan for private repos. |
| Build | **CMake 3.28+** | Modern target-based. Use CMakePresets.json. |
| IDE | **clangd** | LSP server, runs clang-tidy in real-time. |

## Rules: Key Changes from Original Design

### CHANGED:
- ~~C++17 minimum (prefer C++20)~~ → **C++20 minimum**
- ~~clang-format for formatting~~ → **clang-format + clang-tidy** (add static analysis)
- ~~sanitizers in debug~~ → **ASan+UBSan together, TSan separately** (can't combine TSan with ASan)

### ADDED:
1. **C++20 features to recommend:**
   - `concepts` over SFINAE for template constraints
   - `std::format` over printf/iostream formatting
   - `std::span` for non-owning array/buffer parameters
   - `std::string_view` for non-owning string parameters
   - Designated initializers for readability
   - Three-way comparison (`<=>`) for custom types
   - `[[nodiscard]]` with message on functions with important return values

2. **C++23 features (where available):**
   - `std::expected` for error handling with error information
   - Monadic operations on `std::optional` (`.and_then`, `.transform`, `.or_else`)
   - `std::print` / `std::println`
   - `std::generator` for lazy sequences

3. **CMake modern patterns:**
   - Require CMake 3.28+
   - Always target-based: `target_link_libraries`, `target_compile_features`
   - `target_compile_features(mylib PUBLIC cxx_std_20)` not global `CMAKE_CXX_STANDARD`
   - Use `CMakePresets.json` for build configurations
   - Never `file(GLOB)` for sources

4. **Compiler warnings:** `-Wall -Wextra -Wpedantic -Werror` in CI

5. **clang-tidy check groups:** `modernize-*`, `bugprone-*`, `performance-*`, `readability-*`, `cppcoreguidelines-*`

6. **Modules:** NOT recommended as default. Consider only for greenfield projects with CMake 4.0+.

7. **Ranges:** Recommend for data transformation pipelines. Not needed for simple loops.

8. **Coroutines:** Only with library support (cppcoro, Asio). Don't write custom promise types.

## What Major Projects Use

| Project | C++ Std | Formatting | Testing | Key practice |
|---------|---------|-----------|---------|-------------|
| LLVM | C++17 | clang-format | GoogleTest | No RTTI/exceptions, 80-col |
| Chromium | C++23 | clang-format | GoogleTest | `raw_ptr<T>`, forward declarations |
| Google | C++20 | clang-format | GoogleTest | Comprehensive style guide |
| Qt 6 | C++17 | Qt style | Qt Test | No RTTI, Q_OBJECT macro |

## Sources

- [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
- [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)
- [Chromium C++ Style](https://chromium.googlesource.com/chromium/src/+/HEAD/styleguide/c++/c++.md)
- [CppCon 2025 Best Practices](https://cppcon.org/class-2025-best-practices/)
- [std::expected (C++23)](https://www.modernescpp.com/index.php/c23-a-new-way-of-error-handling-with-stdexpected/)
- [Modern CMake](https://cliutils.gitlab.io/modern-cmake/modern-cmake.pdf)
