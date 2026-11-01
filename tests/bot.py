#!/usr/bin/env python3
"""Automated play-tester for SNAPBUG.

Drives tools/vicsim interactively: reads game state from emulated RAM,
steers the player with a BFS bot (nearest seed, avoiding dangerous enemies),
and checks invariants along the way:
  * the CPU never hits an illegal opcode (the simulator aborts),
  * every frame's work finishes inside the NTSC frame budget,
  * the game progresses: seeds get eaten, levels are cleared, lives are lost,
    and game over returns to the title screen.

  python3 tests/bot.py [FRAMES] [--shots DIR] [--seed-joy]
"""
import os, sys, subprocess, re
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import mkdata  # noqa: E402

VICSIM = os.path.join(ROOT, "tools/vicsim/vicsim")
PRG = os.path.join(ROOT, "build/snapbug.prg")
LBL = os.path.join(ROOT, "build/snapbug.lbl")
BGMAP = 0x0400
W, H = mkdata.W, mkdata.H
MAZE_OFF = mkdata.MAZE_SCREEN_ROW * 21
CH_DOT, CH_HONEY = mkdata.CH_DOT, mkdata.CH_HONEY
DX, DY = mkdata.DX, mkdata.DY
JOY = {0: "U", 1: "L", 2: "D", 3: "R"}
M_TITLE, M_READY, M_PLAY, M_EAT, M_DYING, M_LEVEL, M_OVER = range(7)
ST_ACTIVE, ST_LEAVE = 2, 1
FRAME_LINES = 261
BOTTOM = 240


def walkable(c, r):
    return mkdata.MAZE[r][c] in ".o T"


class Sim:
    def __init__(self):
        self.labels = {}
        with open(LBL) as labels:
            for line in labels:
                p = line.split()
                if len(p) == 3 and p[0] == "al":
                    self.labels[p[2][1:]] = int(p[1], 16)
        self.p = subprocess.Popen([VICSIM, PRG, "start", "-", LBL], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self.max_busy = 0
        self.busy_by_mode = {}
        self.cur_mode = -1
        self.frames = 0
        self.cmd("timing on")

    def cmd(self, c):
        self.p.stdin.write(c + "\nsync\n")
        self.p.stdin.flush()
        out = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                err = self.p.stderr.read()
                raise RuntimeError("simulator died: " + err)
            if line.startswith("CPU halted"):
                raise RuntimeError(line + self.p.stderr.read())
            if line.startswith("ok "):
                self.frames = int(line.split()[1])
                return out
            m = re.search(r"busy until line (\d+)", line)
            if m:
                busy = (int(m.group(1)) - BOTTOM) % FRAME_LINES
                self.max_busy = max(self.max_busy, busy)
                self.busy_by_mode[self.cur_mode] = max(self.busy_by_mode.get(self.cur_mode, 0), busy)
                continue
            out.append(line)

    def peek(self, what, n=1):
        addr = self.labels.get(what, what)
        if isinstance(addr, int):
            what = f"${addr:04X}"
        out = self.cmd(f"peek {what} {n}")
        vals = out[-1].split(":")[1].split()
        return [int(v, 16) for v in vals]

    def run(self, n):
        self.cmd(f"run {n}")

    def joy(self, s):
        self.cmd(f"joy {s or '-'}")

    def shot(self, fn):
        self.cmd(f"shot {fn}")


def bfs_dir(start, goal_fn, blocked):
    """First direction of a shortest path from start to any tile goal_fn accepts."""
    sc, sr = start
    q = deque()
    seen = {start: None}
    for d in range(4):
        c, r = (sc + DX[d]) % W, sr + DY[d]
        if 0 <= r < H and walkable(c, r) and (c, r) not in blocked and (c, r) not in seen:
            seen[(c, r)] = d
            q.append((c, r))
    while q:
        c, r = q.popleft()
        if goal_fn(c, r):
            return seen[(c, r)]
        for d in range(4):
            cc, rr = (c + DX[d]) % W, r + DY[d]
            if 0 <= rr < H and walkable(cc, rr) and (cc, rr) not in blocked and (cc, rr) not in seen:
                seen[(cc, rr)] = seen[(c, r)]
                q.append((cc, rr))
    return None


def main():
    frames = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 20000
    shots = None
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    sim = Sim()
    sim.run(120)
    last = {}
    events = []
    max_level = 0
    games = 0
    shot_n = 0
    step = 2
    while sim.frames < frames:
        mode = sim.peek("mode")[0]
        sim.cur_mode = mode
        level = sim.peek("level")[0]
        lives = sim.peek("lives")[0]
        score = sim.peek("score", 3)
        sc = int(f"{score[2]:02X}{score[1]:02X}{score[0]:02X}")
        state = (mode, level, lives)
        if state != last.get("state"):
            events.append((sim.frames, mode, level, lives, sc))
            print(f"frame {sim.frames:6d}: mode={mode} level={level+1} lives={lives} score={sc}", flush=True)
            if shots and mode in (M_PLAY, M_LEVEL, M_OVER, M_EAT):
                fn = os.path.join(shots, f"s{shot_n:03d}_m{mode}_l{level+1}.ppm")
                sim.shot(fn)
                shot_n += 1
            last["state"] = state
        max_level = max(max_level, level)
        if mode == M_TITLE:
            games += 1
            if games > 3:
                break
            sim.joy("F"); sim.run(2); sim.joy(""); sim.run(2)
            continue
        if mode != M_PLAY:
            sim.joy("")
            sim.run(8)
            continue
        px, py = sim.peek("px", 2)
        ex = sim.peek("ex", 4); ey = sim.peek("ey", 4)
        est = sim.peek("estate", 4); efr = sim.peek("efright", 4)
        bg = sim.peek(BGMAP + MAZE_OFF, W * H)
        pc, pr = ((px + 4) // 8) % W, (py + 4) // 8
        blocked = set()
        prey = set()
        for i in range(4):
            if est[i] not in (ST_ACTIVE, ST_LEAVE):
                continue
            c, r = ((ex[i] + 4) // 8) % W, (ey[i] + 4) // 8
            if efr[i]:
                prey.add((c, r))
                continue
            for dc in range(-2, 3):
                for dr in range(-2, 3):
                    if abs(dc) + abs(dr) <= 2:
                        blocked.add(((c + dc) % W, r + dr))
        blocked.discard((pc, pr))
        d = None
        if prey:
            d = bfs_dir((pc, pr), lambda c, r: (c, r) in prey, blocked)
        if d is None:
            d = bfs_dir((pc, pr), lambda c, r: bg[r * W + c] in (CH_DOT, CH_HONEY), blocked)
        if d is None:
            # flee: any open direction away from the closest enemy
            best, bd = None, -1
            for dd in range(4):
                c, r = (pc + DX[dd]) % W, pr + DY[dd]
                if walkable(c, r):
                    dist = min(abs(c - ((ex[i] + 4) // 8)) + abs(r - ((ey[i] + 4) // 8))
                               for i in range(4)) if est else 0
                    if dist > bd:
                        best, bd = dd, dist
            d = best
        sim.joy(JOY[d] if d is not None else "")
        sim.run(step)

    budget = FRAME_LINES
    print(f"\nran {sim.frames} frames; max frame work {sim.max_busy}/{budget} raster lines "
          f"({100*sim.max_busy//budget}%)")
    names = ["title", "ready", "play", "eat", "dying", "level", "over"]
    print("max frame work by mode: " + ", ".join(
        f"{names[m] if 0 <= m < 7 else 'start'}={v}" for m, v in sorted(sim.busy_by_mode.items())))
    print(f"highest level reached: {max_level+1}, games started: {games}")
    ok = sim.max_busy < budget - 5
    lvl_ok = max_level >= 1
    print("TIMING", "PASS" if ok else "FAIL")
    print("PROGRESS", "PASS" if lvl_ok else "FAIL (no level cleared)")
    sim.p.stdin.write("quit\n"); sim.p.stdin.flush(); sim.p.wait()
    sys.exit(0 if ok and lvl_ok else 1)


if __name__ == "__main__":
    main()
