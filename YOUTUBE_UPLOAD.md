# YouTube upload packages — agentic homebrew Pac-Man

Both packages now describe the project as **agentic homebrew**: coding agents
performed the conversion and optimization work under human direction, with
play testing and visual review determining which changes were kept.

| Package | Write-up | Landscape thumbnail | Portrait cover |
| --- | --- | --- | --- |
| Initial Pass | [Read](youtube/INITIAL_PASS.md) | [Open](youtube/vic20-pacman-thumbnail.png) | [Open](youtube/vic20-pacman-shorts-cover.png) |
| Final Optimized | [Read](youtube/final/WRITEUP.md) | [Open](youtube/final/vic20-pacman-thumbnail.png) | [Open](youtube/final/vic20-pacman-shorts-cover.png) |

The existing 2:18 recording is **Initial Pass** footage. It predates the
glyph-pool flicker fix and fourteen speed improvements. The Final Optimized
package describes the current default build and selects the existing
[through-game-over.mp4](build/through-game-over/through-game-over.mp4)
recording for upload.

## Initial Pass: copy-ready fields

| Field | File or prepared value |
| --- | --- |
| Title | [title.txt](youtube/title.txt) |
| Description | [description.txt](youtube/description.txt) |
| Tags | [tags.txt](youtube/tags.txt) |
| Pinned comment | [pinned-comment.txt](youtube/pinned-comment.txt) |
| Standard-video metadata | [upload-metadata.json](youtube/upload-metadata.json) |
| Portrait-video metadata | [upload-metadata-shorts.json](youtube/upload-metadata-shorts.json) |
| Landscape video | [Existing 1080p recording](build/youtube/vic20-pacman-first-intermission-1080p.mp4) |
| Portrait video | [Existing original recording](build/playthrough/first-intermission.mp4) |
| Recording date | November 1, 2026 |
| Chapters | 00:00 Start and board 1; 01:08 Board 2; 02:04 First intermission |

Title:

> Pac-Man on VIC-20 | Agentic Homebrew — Initial Pass

The description now leads with the coding agents' role and human direction.
It explains that the joystick bot recording the playthrough is separate from
the coding agents used for development. Its forward-looking paragraph
identifies the subsequent optimized milestone without attributing those
changes to the early recording. Historical FPS figures from different
workloads have been removed from this upload copy.

## Final Optimized: copy-ready fields

| Field | File or prepared value |
| --- | --- |
| Title | [title.txt](youtube/final/title.txt) |
| Description | [description.txt](youtube/final/description.txt) |
| Tags | [tags.txt](youtube/final/tags.txt) |
| Pinned comment | [pinned-comment.txt](youtube/final/pinned-comment.txt) |
| Standard-video metadata | [upload-metadata.json](youtube/final/upload-metadata.json) |
| Portrait-video metadata | [upload-metadata-shorts.json](youtube/final/upload-metadata-shorts.json) |
| Video | [through-game-over.mp4](build/through-game-over/through-game-over.mp4), approximately 10:01 |
| Recording date and chapters | Unspecified |

Title:

> Pac-Man on VIC-20 | Agentic Homebrew — Final Optimized

The final copy covers the finished-cell glyph-pool flicker fix, refined
graphics for Pac-Man himself and the frightened (scared) ghosts, redesigned
fonts for more legible text and scores, and all fourteen accepted speed improvements.
It reports **22.07 → 33.85 completed redraws/s**, approximately **53% more**
than the first accepted pool build on the saved VICE route. It distinguishes
that average from both the gameplay clock and a fixed display frame rate.
The [full write-up](youtube/final/WRITEUP.md) includes every accepted stage.

The final description and write-up also explain the technical compromises:
one foreground color per 8×16 cell, CPU-drawn actors, limited graphics memory,
uneven redraw timing, and the VIC sound hardware. They distinguish shared-cell
color clash from erase/redraw flicker and explain why white walls help.

The upload follows the PacStrats patterns documented in
[10yard's Pac-Man Trainer (pactrainer)](https://github.com/10yard/pactrainer).
It completes boards 1–9 and the third intermission with no deaths. Afterwards,
the run was deliberately ended to demonstrate Pac-Man's death animation and
the Game Over screen. This intentional ending is separate from the death-free
pattern run. The capture report records four deliberate deaths while using up
the remaining lives.

The standard-video metadata selects this full-length recording. The portrait
cover remains available, with its metadata awaiting a selected Shorts excerpt.

“Final Optimized” identifies the completed optimization milestone. Some
color sharing, partial updates and uneven pacing remain. Further development
can focus on extended play testing, gameplay checks and presentation polish.

## Other upload fields

These are prepared editorial settings. Channel-specific commercial fields
remain tied to the channel's actual arrangements.

| Field | Prepared value |
| --- | --- |
| Category | Gaming |
| Game | Pac-Man (1980), if offered in the selector |
| Playlist title | Agentic Homebrew: Pac-Man on the VIC-20 |
| Playlist description | Building and refining a native VIC-20 Pac-Man conversion with coding agents, human direction and live play testing, from the initial pass through the optimized milestone. |
| Audience | General retro-computing and game-development audience; not made for kids |
| Age restriction | None |
| Video / metadata language | English |
| Captions | Game audio; no spoken narration supplied for transcription. |
| Recording location | Leave blank |
| License | Standard YouTube License |
| Embedding | On |
| Notify subscribers | On |
| Automatic featured places | Off |
| Comments | On, Basic moderation; sort by Top comments |
| Show like count | On |
| Cards / end screen | None prepared |
| Remixing | Off |
| Paid promotion | Use actual sponsorship status |
| Monetization | Use the channel setting |
| Visibility / schedule | Public when ready; no publication date prepared |
| Premiere | Off |

Production notes: coding agents helped implement and optimize the game.
The thumbnail artwork was generated with the built-in imagegen tool, and
the write-ups and upload copy also use AI assistance. The existing video is
actual VICE gameplay recorded through ordinary joystick input.

## Thumbnail files and prompts

The Initial Pass thumbnails use a cyan-bordered stage badge. The Final
Optimized set uses a yellow-bordered badge. All four explicitly say
**AGENTIC HOMEBREW** and **BUILT WITH CODING AGENTS**.

The portrait covers were recomposed vertically, with deliberate black
margins to protect the entire headline and maze in centered preview crops.
They are separate designs from the landscape thumbnails.

All four are PNG files below 2 MB. The native generated dimensions and crop
checks are recorded in [asset-verification.json](youtube/asset-verification.json).
Portrait source canvases have extra vertical space; the essential artwork
survives centered 9:16 and 4:5 crops.

| Prompt | Saved file |
| --- | --- |
| Initial landscape | [thumbnail-prompt.txt](youtube/thumbnail-prompt.txt) |
| Initial portrait, including crop refinement | [thumbnail-shorts-prompt.txt](youtube/thumbnail-shorts-prompt.txt) |
| Final landscape | [thumbnail-prompt.txt](youtube/final/thumbnail-prompt.txt) |
| Final portrait | [thumbnail-shorts-prompt.txt](youtube/final/thumbnail-shorts-prompt.txt) |

These are AI-designed thumbnails based on real VICE references, rather than
pixel-exact screenshots. The [reference manifest](youtube/references/provenance.json)
identifies the original frames and the final accepted executable.
