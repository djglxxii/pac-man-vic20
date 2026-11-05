# Agentic homebrew Pac-Man: YouTube assets

Both sets explicitly identify this as an **agentic homebrew**, built with
coding agents under human direction and play testing.

| Milestone | Write-up | Landscape thumbnail | Portrait cover |
| --- | --- | --- | --- |
| Initial Pass | [Initial write-up](INITIAL_PASS.md) | [Landscape](vic20-pacman-thumbnail.png) | [Portrait](vic20-pacman-shorts-cover.png) |
| Final Optimized | [Final write-up](final/WRITEUP.md) | [Landscape](final/vic20-pacman-thumbnail.png) | [Portrait](final/vic20-pacman-shorts-cover.png) |

The existing root-level text and metadata files describe the **Initial Pass**
recording. The separate **final/** directory contains final-milestone copy,
metadata and both new thumbnails. The [upload guide](../YOUTUBE_UPLOAD.md)
maps the fields and files.

The final milestone includes refined graphics for Pac-Man himself and the
frightened (scared) ghosts, redesigned fonts for more legible text and scores,
the glyph-pool flicker fix and fourteen accepted
speed optimizations. Its saved-route average is 33.85 completed redraws/s,
compared with 22.07 for the first accepted pool build. That is not a direct
comparison with the earlier video's workload or a locked frame rate.

The [final write-up](final/WRITEUP.md#why-color-clashes-and-other-compromises-remain)
explains shared-cell color clashes, software sprites, CPU and graphics-memory
limits, uneven redraw timing and the sound-hardware differences.

The older 2:18 recording is Initial Pass footage. The Final Optimized upload
uses [through-game-over.mp4](../build/through-game-over/through-game-over.mp4):
PacStrats patterns documented in
[10yard's pactrainer](https://github.com/10yard/pactrainer), no deaths through
the third intermission, then an intentional game-over demonstration.
The full-length recording is selected in the standard-video metadata;
no separate Shorts excerpt has been prepared. Recording date and chapters
remain unspecified.

## Artwork and provenance

All four thumbnails were created with the **built-in imagegen tool**.
They are AI-designed promotional artwork based on actual VICE references,
not pixel-exact screenshots or benchmark evidence. The literal source frames
are preserved in [references/](references/).

The initial landscape/portrait prompts are [here](thumbnail-prompt.txt) and
[here](thumbnail-shorts-prompt.txt). The final landscape/portrait prompts are
[here](final/thumbnail-prompt.txt) and [here](final/thumbnail-shorts-prompt.txt).
The initial portrait prompt also retains its crop-safety refinement.

Portrait covers are composed separately rather than cropped from landscape.
Their complete essential artwork fits a centered 4:5 preview; decorative
pixels outside that region are intentional. Native output sizes, byte counts,
hashes and preview bounds are recorded in
[asset-verification.json](asset-verification.json). These crop checks address
the chosen preview, not every interface overlay or crop a platform may use.

The [reference manifest](references/provenance.json) identifies each frame,
including the final accepted program hash. No gameplay code, timing or assets
were changed to make these thumbnails.
