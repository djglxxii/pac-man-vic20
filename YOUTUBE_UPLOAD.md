# YouTube upload package — VIC-20 Pac-Man

Prepared for the recorded 2:18 gameplay video. The text below is ready to copy
into YouTube Studio; individual text files are also in [youtube/](youtube/).

## Your existing Short

Your uploaded video is a Short, so use the new
[vertical Shorts cover](youtube/vic20-pacman-shorts-cover.png). The original
thumbnail was designed for the separate landscape video. Its wide, side-by-side
layout can lose the headline or maze in a vertical preview.

The new cover stacks the headline and maze, with important content centered
and extra space around the edges for narrower preview crops and interface
overlays. It is a separate asset; the landscape thumbnail remains available.

To replace the cover on your existing Short, open YouTube Studio on a computer:
**Content → Shorts → your video → Edit → Thumbnail → Upload file**, then save.
YouTube currently documents uploaded Shorts thumbnails for verified accounts
on desktop and recommends 9:16 artwork.
[YouTube’s Shorts thumbnail instructions](https://support.google.com/youtube/answer/72431).

| Upload format | Video | Cover |
| --- | --- | --- |
| Your current Short | [Original portrait recording](build/playthrough/first-intermission.mp4) | [Vertical Shorts cover](youtube/vic20-pacman-shorts-cover.png) |
| Alternative standard video | [1920×1080 landscape recording](build/youtube/vic20-pacman-first-intermission-1080p.mp4) | [Landscape thumbnail](youtube/vic20-pacman-thumbnail.png) |

## Video file

The [original portrait capture](build/playthrough/first-intermission.mp4) is the
Short version. To publish a standard video instead, upload
[the 1920×1080 landscape version](build/youtube/vic20-pacman-first-intermission-1080p.mp4).
It keeps the full portrait game centered with black borders,
integer nearest-neighbor scaling, the original sound and the original timing.

The landscape version matters here: YouTube categorizes square/vertical videos
up to three minutes as Shorts. A wider format is the supported way to keep this
as a standard video. [YouTube’s format guidance](https://support.google.com/youtube/answer/15424877).

## Title

```text
Pac-Man on the VIC-20 | Homebrew Conversion Gameplay
```

[Copy from title.txt](youtube/title.txt). 52 characters.

## Description

```text
Pac-Man on an expanded VIC-20! This work-in-progress homebrew conversion adapts the original arcade game logic into native 6502 code, with graphics and sound built around the VIC-20's limits.

This computer-controlled playthrough clears the first two boards and reaches the complete first intermission. It was captured in the VICE emulator using normal joystick input, with original game audio and no commentary. The game handles movement, collisions, scoring and progression throughout.

WHY THE WHITE MAZE?
The VIC-20 shares one foreground color across each 8x16 display cell. White walls and pellets give the maze a consistent appearance, while completion flashes blue and white four times. Colored characters can still tint nearby pixels sharing their cell.

UNDER THE HOOD
The conversion combines C compiled with LLVM-MOS and handwritten 6502 assembly. Artwork, music, effect data and difficulty tables come from the arcade ROM set. Gameplay retains its approximately 60.606 Hz update clock, including the original ghost behavior and intermissions.

Rendering currently measures around 48 FPS in normal play and 54 FPS with frightened ghosts. Flicker is still visible. Our next priority is reducing the gaps between erasing and redrawing sprites, followed by memory reuse and further rendering optimizations.

CHAPTERS
00:00 Start and board 1
01:08 Board 2
02:04 First intermission

TECHNICAL NOTES
Target: NTSC VIC-20 with +3K and BLK1/2/3/5 RAM expansion.
Capture: VICE, with a joystick-driven bot. Both boards reach 244 eaten pellets through gameplay.
The video includes one lost life and a brief look at the third board after the intermission.

CREDITS
Original game: Pac-Man (Namco), using the Midway arcade ROM set as the reference.
Game logic adapted from Mark Burkley's C translation:
https://github.com/mburkley/pacman-c
Emulator: VICE
https://vice-emu.sourceforge.io/

How does the flicker look on your display? Feedback from VIC-20 owners and homebrew developers is welcome.

#VIC20 #PacMan #RetroGaming
```

[Copy from description.txt](youtube/description.txt). 2019 characters.
The chapter times match this exact capture; all three chapters exceed ten
seconds. This chapter setup is intended for the standard-video version.
[YouTube chapter guidance](https://support.google.com/youtube/answer/9884579).

## Tags

Paste into the Tags field, rather than adding the list to the description:

```text
VIC-20, VIC20, Commodore VIC-20, Pac-Man, Pacman, Pac Man, VIC-20 Pac-Man, homebrew, homebrew games, arcade conversion, retro gaming, retro computing, 6502, Commodore, VICE emulator, game development, Pac-Man intermission, LLVM-MOS
```

[Copy from tags.txt](youtube/tags.txt).

## Thumbnail

For your Short, use
[vic20-pacman-shorts-cover.png](youtube/vic20-pacman-shorts-cover.png).
It uses a portrait composition with centered PAC-MAN / VIC-20 lettering and
the white maze underneath. Its title and maze fit inside a centered 4:5 preview
crop. The saved PNG is 941×1672 pixels and about 0.83 MB. The
[Shorts generation prompt](youtube/thumbnail-shorts-prompt.txt) is saved with it.

For a standard landscape upload, use
[vic20-pacman-thumbnail.png](youtube/vic20-pacman-thumbnail.png).
That design places the lettering beside the maze and is intended for the
1920×1080 landscape video.

Generated using the built-in imagegen tool; the
[complete generation prompt](youtube/thumbnail-prompt.txt) is saved with it.
The saved PNG is 1672×941 pixels (approximately 16:9), RGB, and about 1.11 MB.
It meets the minimum width and is below the mobile 2 MB limit in
[YouTube’s thumbnail guidance](https://support.google.com/youtube/answer/72431).

## Playlist

Suggested playlist title:

```text
VIC-20 Homebrew: Pac-Man Conversion
```

Suggested playlist description:

```text
Development updates and gameplay from a homebrew arcade Pac-Man conversion for an expanded NTSC VIC-20, covering graphics, sound, performance and the compromises of bringing the arcade game to Commodore hardware.
```

## Remaining upload fields

These are proposed settings for a retro-computing development video. Account
features and field names can vary. Sponsorship and monetization depend on your
channel and arrangements, so those two entries remain channel-specific.

| Field | Prepared value or setting |
| --- | --- |
| Category | Gaming |
| Game title | Search for Pac-Man (1980); select the original game if Studio offers it. |
| Audience | No, it’s not made for kids — intended for a general retro-computing/development audience. |
| Age restriction | No restriction to viewers over 18. |
| Paid promotion / branded content | Use your actual sponsorship status; no sponsor information was provided. |
| AI use / altered or synthetic content | No for this footage: it is actual emulator gameplay. The thumbnail and upload copy use AI production assistance. |
| Video language | English; the video has on-screen English and game audio, with no spoken narration. |
| Title and description language | English |
| Caption certification | This content has never aired on television in the U.S. |
| Subtitles | No spoken dialogue to transcribe; leave without a subtitle file. |
| Recording date | November 1, 2026 |
| Recording location | Leave blank. |
| License | Standard YouTube License |
| Allow embedding | On |
| Publish to subscriptions feed / notify subscribers | On |
| Automatic chapters | For the standard video, use the chapter timestamps already in the description. |
| Automatic featured places | Off; the footage is an emulator capture. |
| Automatic concepts | Leave at the channel default. |
| Shorts remixing | Do not allow remixing. |
| Comments | On, with Basic moderation. |
| Comment sorting | Top comments |
| Show how many viewers like this video | On |
| Cards | None for this upload. |
| End screen | None on this cut, keeping the final intermission visible. |
| Monetization | Use your channel’s existing setting. |
| Visibility | Public for release. |
| Premiere | Off |
| Schedule | Publish when ready; no date/time was specified. |

The audience suggestion assumes the intended viewers are retro-computing
hobbyists; it follows YouTube’s distinction for
[general-audience content](https://support.google.com/youtube/answer/9528076).
YouTube lists gameplay footage and AI assistance with thumbnails/titles among
its examples that do not require the realistic-AI-content disclosure.
[AI disclosure guidance](https://support.google.com/youtube/answer/14328491).
The field overview is based on
[YouTube’s upload documentation](https://support.google.com/youtube/answer/57407).

## Pinned comment

```text
The white maze is deliberate: the VIC-20 shares one foreground color across each 8x16 cell. It keeps walls and pellets consistent, although colored sprites can still tint a shared cell.

Next up is reducing the visible erase/redraw flicker. How distracting does it look on your screen?
```

[Copy from pinned-comment.txt](youtube/pinned-comment.txt).

## Machine-readable copy

[youtube/upload-metadata.json](youtube/upload-metadata.json) contains the title,
description, tags, chapters, playlist text, suggested settings and pinned comment
for the standard video. [youtube/upload-metadata-shorts.json](youtube/upload-metadata-shorts.json)
selects the original portrait recording and the vertical cover for a Short.
