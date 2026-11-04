# Automated playthrough recording

`tools/arcade/record_playthrough.py` runs the unchanged PRG in VICE and drives
its joystick through the first two boards and the complete first intermission.
The first recorded run with the finalized capture tool is saved locally as
`build/playthrough/first-intermission.mp4`.

The recording is **2 minutes 18.28 seconds**, 360×464, H.264 video with AAC
48 kHz mono audio. It includes the start, both boards, their completion flashes,
one lost life, the first intermission and two seconds of the third board.
The intermission begins around **2:04**. The bot finishes with two lives.

Both boards reach 244 eaten pellets through ordinary movement. The bot only
writes joystick inputs; it never edits CPU RAM/registers, pellet arrays,
lives, invulnerability, score or level counters. There are no forced board
completions, restored game snapshots or stitched gameplay segments. The PRG
hash matches the accepted white-maze revision `ed6ca44`.

## Capture method

The external bot reads the logical maze, Pac-Man's position and ghost state
through VICE's monitor. A weighted shortest-path search seeks remaining dots
while penalizing routes close to dangerous ghosts. It updates its direction
every two video frames. The game still supplies movement, collision detection,
ghost behavior, score, sound, death and intermission transitions.

A raster-conditioned monitor checkpoint captures each frame at line 1, after
the preceding visible picture is complete. Twelve stepped instructions leave
the capture window before the checkpoint is re-enabled. The expressions use
explicit parentheses for VICE's condition precedence. See the primary
[VICE monitor](https://vice-emu.sourceforge.io/vice_12.html) and
[binary-monitor command documentation](https://vice-emu.sourceforge.io/vice_13.html).

Frames are sampled from VICE's actual raster buffer, including partially erased
or redrawn software sprites. Capture does not wait for `video_frame_end`, select
only completed game renders, interpolate motion or correct the game's flicker.
Playback uses the NTSC frame rate, `1022727/(65*261)` = approximately 60.2845 Hz.
Generation runs faster than playback; this recording took about 28 host seconds.

The video keeps the full VIC display and a narrow border, with nearest-neighbor
scaling for the NTSC pixel aspect. Sound recording begins with video capture,
after autostart, avoiding the missing audio samples that autostart warp can
cause. The WAV/video duration difference is about 19 ms; the final mux pads the
short audio tail. No time stretching is applied to the game audio.

## Reproduce

The tool needs the ordinary build dependencies, VICE with the installed VIC-20
ROMs, a graphical display and an FFmpeg executable with H.264/AAC encoding.
On this Linux setup, VICE's ALSA null output avoids requiring speakers.

```sh
make
python3 tools/arcade/record_playthrough.py
```

Use `--output build/playthrough-new` to preserve an earlier recording, or
`--ffmpeg /path/to/ffmpeg` to select an encoder. If FFmpeg is absent, an optional
local installation supplies the binary without changing system packages:

```sh
python3 -m pip install --target build/capture/python imageio-ffmpeg
python3 tools/arcade/record_playthrough.py
```

The bot is a simple policy and can lose a game under different starting timing.
A game over or frame-limit timeout makes the tool fail rather than forcing an
intermission. `--radius` adjusts ghost avoidance; the recorded run uses 5.

## Evidence and validation

The [compact capture record](baselines/first-intermission-playthrough.json)
preserves the game/tool/input/video hashes, milestones and verification.
Raw capture evidence remains under ignored `build/playthrough/`:

- `first-intermission.mp4`: the final video.
- `report.json`: frame counts, board completion, scene and life transitions.
- `inputs.json`: the complete joystick-change timeline.
- `vice-audio.wav` and `video-only.mp4`: source audio/video before muxing.
- `vice.log` and `ffmpeg.log`: emulator and encoder logs.
- `verification.json`, `decode.log`, `audio-validation.log`: delivery checks.

All **8,336 frames** decode successfully. Audio is non-silent, with a measured
peak of −3.8 dB. Both boards complete, the first intermission starts and finishes,
and the next board becomes playable. No guest code changes were made for this
capture; it records the existing 42-test white-maze build.

## Published routes

The recorder above is a pellet-seeking bot and stops after the first
intermission. A separate VICE session followed the published PacStrats trails
through the third intermission on the current PRG, again by joystick writes
only. Details and the recording path are in [validation](VALIDATION.md).
`record_playthrough.py` still records the first-intermission bot.
