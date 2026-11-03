#!/usr/bin/env python3
"""Boot the private PRG in real VICE, exercise coin/start, capture video/audio."""
import argparse, json, socket, struct, subprocess, time, wave
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


class Monitor:
    def __init__(self, s):
        self.s = s
        self.req = 0

    def read(self, n):
        data = bytearray()
        while len(data) < n:
            chunk = self.s.recv(n - len(data))
            if not chunk:
                raise EOFError("VICE binary monitor closed")
            data.extend(chunk)
        return bytes(data)

    def cmd(self, kind, body=b""):
        self.req += 1
        request = self.req
        self.s.sendall(struct.pack("<BBIIB", 2, 2, len(body), request, kind) + body)
        while True:
            stx, version, length, response, error, req = struct.unpack(
                "<BBIBBI", self.read(12)
            )
            data = self.read(length)
            if req != request:
                continue
            if error:
                raise RuntimeError(f"VICE command {kind:02x}: error {error:02x}")
            return data

    def resume(self):
        self.cmd(0xAA)

    def memory(self, start, size):
        return self.cmd(1, struct.pack("<BHHBH", 0, start, start + size - 1, 0, 0))[2:]

    def store(self, start, data):
        self.cmd(
            2, struct.pack("<BHHBH", 0, start, start + len(data) - 1, 0, 0) + data
        )

    def joy(self, value, port=0):
        self.cmd(0xA2, struct.pack("<HH", port, 255 ^ value))
        self.resume()

    def screenshot(self, path):
        palette_data = self.cmd(0x91, b"\0")
        count = struct.unpack_from("<H", palette_data)[0]
        palette = []
        pos = 2
        for _ in range(count):
            size = palette_data[pos]
            palette.extend(palette_data[pos + 1 : pos + 4])
            pos += size + 1
        data = self.cmd(0x84, b"\0\0")
        debug_w, debug_h, x, y, w, h = struct.unpack_from("<6H", data, 4)
        length = struct.unpack_from("<I", data, 17)[0]
        pixels = data[21 : 21 + length]
        # VICE 3.7 declares/sends four fewer display bytes than its own buffer
        # length field. The missing pixels are at the far bottom-right border.
        if len(pixels) == debug_w * debug_h - 4:
            pixels += b"\0" * 4
        im = Image.frombytes("P", (debug_w, debug_h), pixels)
        im.putpalette(palette + [0] * (768 - len(palette)))
        # VIC pixels have a 3:2 aspect on an NTSC display.
        im = im.convert("RGB")
        im.resize((debug_w * 3 // 2, debug_h * 2), Image.Resampling.NEAREST).save(path)
        return {"width": debug_w, "height": debug_h, "inner": [x, y, w, h]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="build/preview")
    ap.add_argument("--maze-flash", action="store_true")
    ap.add_argument("--font-rewards", action="store_true",
                    help="Capture synthetic ghost reward fixtures after normal play")
    args = ap.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    labels = {
        p[2][1:]: int(p[1], 16)
        for line in (ROOT / "build/pacman.lbl").read_text().splitlines()
        if len(p := line.split()) == 3
    }
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    raw = out / "vice-audio-raw.wav"
    log = (out / "vice.log").open("w")
    cmd = [
        "xvic",
        "-model",
        "vic20ntsc",
        "-memory",
        "all",
        "-autostartprgmode",
        "1",
        "-controlport1device",
        "37",
        "-binarymonitor",
        "-binarymonitoraddress",
        f"127.0.0.1:{port}",
        "-sounddev",
        "alsa",
        "-soundarg",
        "null",
        "-soundoutput",
        "1",
        "-soundrecdev",
        "wav",
        "-soundrecarg",
        str(raw),
        "-speed",
        "100" if args.maze_flash else "0",
        "-autostart",
        str(ROOT / "build/pacman.prg"),
    ]
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    mon = None
    try:
        until = time.monotonic() + 20
        while True:
            try:
                s = socket.create_connection(("127.0.0.1", port), timeout=1)
                break
            except OSError:
                if p.poll() is not None:
                    raise RuntimeError(
                        "VICE exited during launch; see " + str(out / "vice.log")
                    )
                if time.monotonic() > until:
                    raise RuntimeError("VICE binary monitor did not start")
                time.sleep(0.05)
        s.settimeout(5)
        mon = Monitor(s)
        # The I/O simulation device powers up with all digital lines low.
        # Release them before boot so the arcade coin debouncer sees an edge.
        mon.joy(0)

        def read_state():
            value = mon.memory(0x9002, 4)
            state = mon.memory(0xE00, 0x76)
            ticks = int.from_bytes(mon.memory(labels["arcade_ticks"], 2), "little")
            mon.resume()
            return value, state, ticks

        def wait(predicate, timeout=20):
            deadline = time.monotonic() + timeout
            while True:
                regs, state, ticks = read_state()
                if predicate(regs, state, ticks):
                    return state, ticks
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        f"VICE wait timed out, game state {state[:9].hex()}"
                    )
                time.sleep(0.01)

        wait(
            lambda r, s, t: r[0] == 0x8E
            and r[1] & 0x7F == 29
            and r[3] == 0x8C
            and s[0] == 1
        )
        _, start = read_state()[1:]
        wait(lambda r, s, t: (t - start) & 65535 >= 60)
        screen = mon.screenshot(out / "vice-attract.png")
        mon.resume()
        # Joystick fire is coin with no credits, then one-player start on a new press.
        mon.joy(16)
        wait(lambda r, s, t: s[0x6E] >= 1)
        mon.joy(0)
        _, tick = read_state()[1:]
        wait(lambda r, s, t: (t - tick) & 65535 >= 20)
        mon.joy(16)
        wait(lambda r, s, t: s[0] == 3)
        mon.joy(0)
        wait(lambda r, s, t: s[0] == 3 and s[4] == 3)
        state, tick = read_state()[1:]
        wait(lambda r, s, t: (t - tick) & 65535 >= 120)
        mon.screenshot(out / "vice-game.png")
        mon.resume()
        # Keep a short real-chip audio sample of the arcade tune and normal play.
        _, tick = read_state()[1:]
        state, last = wait(lambda r, s, t: (t - tick) & 65535 >= 180)
        report = {
            "boot": True,
            "coin_and_start": True,
            "game_state": list(state[:9]),
            "tick": last,
            "display": screen,
            "emulator": "VICE NTSC VIC-20, full expansion",
        }
        if args.font_rewards:
            report["synthetic_reward_fixtures"] = []
            for count, points in enumerate((200, 400, 800, 1600), 1):
                # The real arcade priority swaps run in isr_008d: powered-up
                # Pac-Man moves to output slot 2, the reward to slot 4.
                for address, data in (
                    (0xA4, bytes((1, 0, 1))),
                    (0xAC, bytes(4)),
                    (0xD0, bytes((count, 1))),
                    (0xC02, bytes((39 + count, 24))),
                    (0xC0B, b"\0"),
                ):
                    mon.store(address, data)
                _, tick = read_state()[1:]
                wait(lambda r, s, t: (t - tick) & 65535 >= 12)
                path = out / f"vice-reward-{points}.png"
                mon.screenshot(path)
                attrs = mon.memory(0xC20, 16)
                assert attrs[3] == 0 and attrs[5] == 24, attrs.hex()
                report["synthetic_reward_fixtures"].append({
                    "points": points, "image": path.name,
                    "hidden_output_slot": 2, "reward_output_slot": 4,
                    "attributes": list(attrs),
                })
                mon.resume()
        if args.maze_flash:
            # Prepare a completed board without making the user play through
            # 244 dots. The original state machine supplies all flash phases.
            board = mon.memory(0xE13, 1)[0]
            maze = bytearray(mon.memory(0x400, 1024))
            for i, tile in enumerate(maze):
                if tile in (0x10, 0x12, 0x14):
                    maze[i] = 0x40
            mon.store(0x400, maze)
            mon.store(labels["full_dirty"], b"\x02")
            mon.store(0xE0E, b"\xf4")
            mon.resume()
            phases = []
            pictures = []
            for phase, level in enumerate(range(15, 30, 2)):
                colour = 6 if phase % 2 == 0 else 1
                deadline = time.monotonic() + 15
                while True:
                    state = mon.memory(0xE00, 9)
                    pending = mon.memory(labels["maze_flash"], 1)[0]
                    actual = mon.memory(0x960E, 1)[0] & 7
                    if state[4] == level and not pending and actual == colour:
                        break
                    mon.resume()
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            f"VICE missed maze flash {phase}: {state.hex()}"
                        )
                    time.sleep(0.005)
                path = out / f"vice-flash-{phase}.png"
                mon.screenshot(path)
                with Image.open(path) as picture:
                    pictures.append(picture.copy())
                phases.append({"level_state": level, "colour": actual})
                # Keep the last capture paused while encoding the GIF, so
                # host-side image work cannot consume the transition we test.
                if phase < 7:
                    mon.resume()
            pictures[0].save(
                out / "vice-maze-flash.gif",
                save_all=True,
                append_images=pictures[1:],
                duration=198,
                loop=0,
            )
            report["maze_flash"] = phases
            # Follow the real next-board rebuild after the final flash. Keep
            # intermediate captures separate from completed presentation.
            deadline = time.monotonic() + 15
            partial = []
            seen_ticks = set()
            while True:
                state = mon.memory(0xE00, 0x20)
                phase = mon.memory(labels["rebuild_phase"], 1)[0]
                dirty = mon.memory(labels["full_dirty"], 1)[0]
                active = mon.memory(labels["bulk_active"], 1)[0]
                tick = int.from_bytes(mon.memory(labels["arcade_ticks"], 2), "little")
                if phase and tick // 12 not in seen_ticks and len(partial) < 12:
                    seen_ticks.add(tick // 12)
                    path = out / f"vice-rebuild-{len(partial)}.png"
                    mon.screenshot(path)
                    partial.append({"tick": tick, "phase": phase})
                if state[0x13] == (board + 1) & 255 and state[4] == 3 and not (phase or dirty or active):
                    mon.screenshot(out / "vice-next-board.png")
                    report["board_transition"] = {
                        "from_board": board,
                        "to_board": state[0x13],
                        "settled": True,
                        "partial_captures": partial,
                    }
                    break
                mon.resume()
                if time.monotonic() >= deadline:
                    raise RuntimeError("VICE next board did not settle")
                time.sleep(0.005)
            if not partial:
                raise RuntimeError("VICE did not observe bounded rebuild work")
        mon.cmd(0xBB)
        p.wait(timeout=5)
        mon = None
        s.close()
        with wave.open(str(raw), "rb") as f:
            params = f.getparams()
            samples = f.readframes(f.getnframes())
        if params.nchannels < 1 or params.sampwidth != 2:
            raise RuntimeError("VICE produced invalid audio")
        import array

        pcm = array.array("h", samples)
        first = next(
            (i // params.nchannels for i, v in enumerate(pcm) if abs(v) > 150), None
        )
        if first is None:
            raise RuntimeError("VICE audio is silent")
        first = max(0, first - params.framerate // 50)
        with wave.open(str(out / "vice-audio.wav"), "wb") as f:
            f.setparams(params)
            f.writeframes(samples[first * params.nchannels * 2 :])
        report["audio"] = {
            "channels": params.nchannels,
            "rate": params.framerate,
            "frames": params.nframes - first,
            "peak": max(abs(v) for v in pcm),
        }
        (out / "vice-validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        if p.poll() is None:
            p.terminate()
            p.wait(timeout=5)
        if mon:
            try:
                mon.s.close()
            except OSError:
                pass
        log.close()


if __name__ == "__main__":
    main()
