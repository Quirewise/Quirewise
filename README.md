# Quirewise application

The root repository is now the application and composition repository. Format implementations live in independent, sibling Git repositories:

- `quirewise-runtime`
- `quirewise-image`
- `quirewise-archive`
- `quirewise-page`
- `quirewise-pdg`
- `quirewise-document`
- `quirewise-ebook`
- `quirewise-text`
- `quirewise-data`
- `quirewise-spreadsheet`
- `quirewise-audio`
- `quirewise-subtitle`
- `quirewise-vector`
- `quirewise-comic`

The application never compiles a nested copy of those repositories. Install the libraries, add their install prefixes to `CMAKE_PREFIX_PATH`, and select the libraries to compose with `QUIREWISE_LINK_*` options.

```powershell
cmake -S . -B .tmp/build-app -DQUIREWISE_LINK_IMAGE=ON -DQUIREWISE_LINK_ARCHIVE=ON
cmake --build .tmp/build-app
.\.tmp\build-app\quirewise.exe --libraries
```

Validate the independent-library dependency graph from the workspace root:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python tools/validate_dependency_graph.py --workspace ..
```

The same check is available as a CMake target when configuring with
`-DQUIREWISE_VALIDATE_DEPENDENCIES=ON`:

```powershell
cmake --build .tmp/build-app --target quirewise_validate_dependencies
```

The check rejects dependency cycles, package-config dependencies missing from
the build graph, and library source that reaches into another library or the
application.

An installed-package consumer smoke project is kept at
`tools/consumer_smoke/`. Configure it with a semicolon-separated
`CMAKE_PREFIX_PATH` containing the library install prefixes to verify that all
exported targets can be consumed together.

The old nested repositories and old root implementation are preserved under `.to_delete/` during migration. They are not part of the new build graph.
