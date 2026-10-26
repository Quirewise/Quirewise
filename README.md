# Quirewise application

The root repository is now the application and composition repository. Format implementations live in independent, sibling Git repositories:

- `quirewise-runtime`
- `quirewise-image`
- `quirewise-archive`
- `quirewise-page`
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

The old nested repositories and old root implementation are preserved under `.to_delete/` during migration. They are not part of the new build graph.
