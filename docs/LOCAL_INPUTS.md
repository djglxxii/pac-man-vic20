# Local inputs and archived project artifacts

The repository retains our VIC-20 platform code, tools, tests, custom artwork,
documentation, gameplay recordings, screenshots and performance evidence.
Project artifacts under `build/` are selected by
[build/.gitignore](../build/.gitignore). Generated executables, raw machine
memory and extracted ROM tables remain local because they contain the omitted
game program or data. Downloaded toolchains, third-party source copies,
reference publications and interpreter caches are also excluded.

The following inputs are intentionally omitted from the current Git tree:

- `pacman.zip`, the original arcade ROM archive;
- the adapted game core and headers at `src/arcade/*.c` and `src/arcade/*.h`;
- the third-party Z80 emulator header at `tools/arcade/z80.h`;
- compiled game programs, raw RAM captures and archives containing them;
- generated ROM/asset source and machine-readable sprite tables.

Their local working copies are preserved. A fresh checkout needs the local
game core, headers, ROM archive and Z80 reference header restored before the
existing build and reference tests can run. The current adapted core includes
VIC-specific changes, so the unmodified upstream file is not a drop-in
replacement. [local-inputs.json](local-inputs.json) records the exact working
file identities without embedding their contents. The source lineage remains
documented in [UPSTREAM.md](../src/arcade/UPSTREAM.md).

The video and screenshot captures are retained as project-created recordings;
they do not supply the omitted ROM files or arcade source. The selected final
upload is
[through-game-over.mp4](../build/through-game-over/through-game-over.mp4).

The [artifact inventory](artifact-inventory.json) records the included build
artifacts and their hashes. References in historical reports to omitted
executables, memory captures or tables describe local evidence and are not
promises that those payloads are distributed here.

The ROM archive and arcade source were tracked in earlier commits. Removing
them from the current tree does not remove those existing historical copies.
This update does not rewrite published Git history.
