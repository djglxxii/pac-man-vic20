#!/usr/bin/env python3
"""SNAPBUG data generator.

Builds the maze tables, the character set (font, wall tiles, items) and the
sprite source images, and writes them as ca65 include files.

  python3 tools/mkdata.py OUTDIR [--preview DIR]
"""
import sys, os
from collections import deque

W, H = 21, 21          # maze size in tiles
MAZE_SCREEN_ROW = 2    # maze row 0 is screen row 2
SCREEN_COLS = 21
SCREEN_ROWS = 24

# '#' wall  '.' seed  'o' honey  ' ' open (no seed)  'T' tunnel (open, slow)
# 'x' void  '-' nest door  'n' nest interior
MAZE = [
    "#####################",  # 0
    "#.........#.........#",  # 1
    "#o##.####.#.####.##o#",  # 2
    "#...................#",  # 3
    "#.##.#.#######.#.##.#",  # 4
    "#....#....#....#....#",  # 5
    "####.####.#.####.####",  # 6
    "xxx#.#         #.#xxx",  # 7
    "####.# ###-### #.####",  # 8
    "TTTT.. #nnnnn# ..TTTT",  # 9
    "####.# ####### #.####",  # 10
    "xxx#.#         #.#xxx",  # 11
    "####.#.#######.#.####",  # 12
    "#.........#.........#",  # 13
    "#o##.####.#.####.##o#",  # 14
    "#..#.............#..#",  # 15
    "##.#.#.#######.#.#.##",  # 16
    "#....#....#....#....#",  # 17
    "#.#######.#.#######.#",  # 18
    "#...................#",  # 19
    "#####################",  # 20
]

# Directions: 0=up 1=left 2=down 3=right  (reverse = d^2, left turn = d+1)
DX = [0, -1, 0, 1]
DY = [-1, 0, 1, 0]

PLAYER_START = (10, 15)
DOOR_TILE = (10, 8)
HOME_TILE = (10, 7)      # tile just above the door: eyes aim here
BONUS_TILE = (10, 11)
TUNNEL_ROW = 9

# ---------------------------------------------------------------- maze checks
def check_maze():
    assert len(MAZE) == H, len(MAZE)
    for r, row in enumerate(MAZE):
        assert len(row) == W, (r, len(row), row)
        assert row == row[::-1], ("not symmetric", r, row)

    def walk(c, r):
        return MAZE[r][c] in ".o T"

    # no dead ends for open tiles; 2x2 wall blocks forbidden
    for r in range(H):
        for c in range(W):
            if walk(c, r):
                n = 0
                for d in range(4):
                    cc, rr = (c + DX[d]) % W, r + DY[d]
                    if 0 <= rr < H and walk(cc, rr):
                        n += 1
                assert n >= 2, ("dead end", c, r)
            if c < W - 1 and r < H - 1:
                blk = [MAZE[r][c], MAZE[r][c+1], MAZE[r+1][c], MAZE[r+1][c+1]]
                assert blk.count('#') < 4, ("2x2 wall", c, r)
    # connectivity
    start = PLAYER_START
    seen = {start}
    q = deque([start])
    while q:
        c, r = q.popleft()
        for d in range(4):
            cc, rr = (c + DX[d]) % W, r + DY[d]
            if 0 <= rr < H and walk(cc, rr) and (cc, rr) not in seen:
                seen.add((cc, rr)); q.append((cc, rr))
    allw = {(c, r) for r in range(H) for c in range(W) if walk(c, r)}
    assert seen == allw, ("unreachable", allw - seen)
    assert walk(*PLAYER_START) and walk(*HOME_TILE) and walk(*BONUS_TILE)
    assert MAZE[DOOR_TILE[1]][DOOR_TILE[0]] == '-'

def home_dirs():
    """BFS from HOME_TILE; for every open tile, the direction that leads home."""
    def walk(c, r):
        return MAZE[r][c] in ".o T"
    dist = {HOME_TILE: 0}
    q = deque([HOME_TILE])
    while q:
        c, r = q.popleft()
        for d in range(4):
            cc, rr = (c + DX[d]) % W, r + DY[d]
            if 0 <= rr < H and walk(cc, rr) and (cc, rr) not in dist:
                dist[(cc, rr)] = dist[(c, r)] + 1
                q.append((cc, rr))
    out = [0] * (W * H)
    for (c, r), dd in dist.items():
        best = None
        for d in (0, 1, 2, 3):
            cc, rr = (c + DX[d]) % W, r + DY[d]
            if (cc, rr) in dist and dist[(cc, rr)] < dd:
                best = d; break
        out[r * W + c] = best if best is not None else 0
    return out

# ---------------------------------------------------------------- bitmaps
def art(rows):
    """8 strings of 8 chars ('X'/'#' set) -> list of 8 bytes."""
    assert len(rows) == 8, rows
    out = []
    for s in rows:
        s = s.ljust(8, '.')
        assert len(s) == 8, s
        b = 0
        for i, ch in enumerate(s):
            if ch in 'X#':
                b |= 0x80 >> i
        out.append(b)
    return out

def to_grid(b):
    return [[(row >> (7 - x)) & 1 for x in range(8)] for row in b]

def from_grid(g):
    return [sum(g[y][x] << (7 - x) for x in range(8)) for y in range(8)]

def rot_cw(b):     # rotate 90 degrees clockwise
    g = to_grid(b)
    return from_grid([[g[7 - x][y] for x in range(8)] for y in range(8)])

def flip_h(b):
    g = to_grid(b)
    return from_grid([row[::-1] for row in g])

def flip_v(b):
    return list(reversed(b))

def silhouette(b):
    """Filled outline mask: every pixel not reachable from the border via
    empty pixels."""
    g = to_grid(b)
    outside = [[False] * 8 for _ in range(8)]
    q = deque()
    for i in range(8):
        for (x, y) in ((i, 0), (i, 7), (0, i), (7, i)):
            if not g[y][x] and not outside[y][x]:
                outside[y][x] = True; q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = x + dx, y + dy
            if 0 <= xx < 8 and 0 <= yy < 8 and not g[yy][xx] and not outside[yy][xx]:
                outside[yy][xx] = True; q.append((xx, yy))
    return from_grid([[0 if outside[y][x] else 1 for x in range(8)] for y in range(8)])

# ---------------------------------------------------------------- font
# Original chunky 7x7 arcade-style font (column 7 and row 7 blank).
FONT = {
' ': ["......."]*7,
'0': [".XXXXX.", "XX...XX", "XX..XXX", "XX.X.XX", "XXX..XX", "XX...XX", ".XXXXX."],
'1': ["..XX...", ".XXX...", "..XX...", "..XX...", "..XX...", "..XX...", "XXXXXX."],
'2': [".XXXXX.", "XX...XX", ".....XX", "..XXXX.", ".XX....", "XX.....", "XXXXXXX"],
'3': [".XXXXX.", "XX...XX", ".....XX", "...XXX.", ".....XX", "XX...XX", ".XXXXX."],
'4': ["...XXX.", "..XXXX.", ".XX.XX.", "XX..XX.", "XXXXXXX", "....XX.", "....XX."],
'5': ["XXXXXXX", "XX.....", "XXXXXX.", ".....XX", ".....XX", "XX...XX", ".XXXXX."],
'6': ["..XXXX.", ".XX....", "XX.....", "XXXXXX.", "XX...XX", "XX...XX", ".XXXXX."],
'7': ["XXXXXXX", "XX...XX", "....XX.", "...XX..", "..XX...", "..XX...", "..XX..."],
'8': [".XXXXX.", "XX...XX", "XX...XX", ".XXXXX.", "XX...XX", "XX...XX", ".XXXXX."],
'9': [".XXXXX.", "XX...XX", "XX...XX", ".XXXXXX", ".....XX", "....XX.", ".XXXX.."],
'A': ["..XXX..", ".XX.XX.", "XX...XX", "XX...XX", "XXXXXXX", "XX...XX", "XX...XX"],
'B': ["XXXXXX.", "XX...XX", "XX...XX", "XXXXXX.", "XX...XX", "XX...XX", "XXXXXX."],
'C': ["..XXXX.", ".XX..XX", "XX.....", "XX.....", "XX.....", ".XX..XX", "..XXXX."],
'D': ["XXXXX..", "XX..XX.", "XX...XX", "XX...XX", "XX...XX", "XX..XX.", "XXXXX.."],
'E': ["XXXXXXX", "XX.....", "XX.....", "XXXXXX.", "XX.....", "XX.....", "XXXXXXX"],
'F': ["XXXXXXX", "XX.....", "XX.....", "XXXXXX.", "XX.....", "XX.....", "XX....."],
'G': ["..XXXXX", ".XX....", "XX.....", "XX..XXX", "XX...XX", ".XX..XX", "..XXXXX"],
'H': ["XX...XX", "XX...XX", "XX...XX", "XXXXXXX", "XX...XX", "XX...XX", "XX...XX"],
'I': ["XXXXXX.", "..XX...", "..XX...", "..XX...", "..XX...", "..XX...", "XXXXXX."],
'J': ["....XXX", ".....XX", ".....XX", ".....XX", "XX...XX", "XX...XX", ".XXXXX."],
'K': ["XX...XX", "XX..XX.", "XX.XX..", "XXXX...", "XXXXX..", "XX.XXX.", "XX..XXX"],
'L': ["XX.....", "XX.....", "XX.....", "XX.....", "XX.....", "XX.....", "XXXXXXX"],
'M': ["XX...XX", "XXX.XXX", "XXXXXXX", "XXXXXXX", "XX.X.XX", "XX...XX", "XX...XX"],
'N': ["XX...XX", "XXX..XX", "XXXX.XX", "XXXXXXX", "XX.XXXX", "XX..XXX", "XX...XX"],
'O': [".XXXXX.", "XX...XX", "XX...XX", "XX...XX", "XX...XX", "XX...XX", ".XXXXX."],
'P': ["XXXXXX.", "XX...XX", "XX...XX", "XX...XX", "XXXXXX.", "XX.....", "XX....."],
'Q': [".XXXXX.", "XX...XX", "XX...XX", "XX...XX", "XX.XXXX", "XX..XX.", ".XXXX.X"],
'R': ["XXXXXX.", "XX...XX", "XX...XX", "XX..XXX", "XXXXX..", "XX.XXX.", "XX..XXX"],
'S': [".XXXX..", "XX..XX.", "XX.....", ".XXXXX.", ".....XX", "XX...XX", ".XXXXX."],
'T': ["XXXXXX.", "..XX...", "..XX...", "..XX...", "..XX...", "..XX...", "..XX..."],
'U': ["XX...XX", "XX...XX", "XX...XX", "XX...XX", "XX...XX", "XX...XX", ".XXXXX."],
'V': ["XX...XX", "XX...XX", "XX...XX", "XXX.XXX", ".XXXXX.", "..XXX..", "...X..."],
'W': ["XX...XX", "XX...XX", "XX.X.XX", "XXXXXXX", "XXXXXXX", "XXX.XXX", "XX...XX"],
'X': ["XX...XX", "XXX.XXX", ".XXXXX.", "..XXX..", ".XXXXX.", "XXX.XXX", "XX...XX"],
'Y': ["XX..XX.", "XX..XX.", "XX..XX.", ".XXXX..", "..XX...", "..XX...", "..XX..."],
'Z': ["XXXXXXX", "....XXX", "...XXX.", "..XXX..", ".XXX...", "XXX....", "XXXXXXX"],
'!': ["..XX...", "..XX...", "..XX...", "..XX...", "..XX...", ".......", "..XX..."],
'-': [".......", ".......", ".......", ".XXXXX.", ".......", ".......", "......."],
'.': [".......", ".......", ".......", ".......", ".......", "..XX...", "..XX..."],
':': [".......", "..XX...", "..XX...", ".......", "..XX...", "..XX...", "......."],
'/': [".....XX", "....XX.", "...XX..", "..XX...", ".XX....", "XX.....", "......."],
'(': ["...XX..", "..XX...", ".XX....", ".XX....", ".XX....", "..XX...", "...XX.."],
')': [".XX....", "..XX...", "...XX..", "...XX..", "...XX..", "..XX...", ".XX...."],
'=': [".......", ".......", "XXXXXX.", ".......", "XXXXXX.", ".......", "......."],
'\'':["..XX...", "..XX...", ".XX....", ".......", ".......", ".......", "......."],
'@': [".XXXXX.", "X.....X", "X..XX.X", "X.X.X.X", "X..XX..", "X......", ".XXXXX."],  # (c) mark
}

def font_glyph(ch):
    rows = FONT[ch]
    assert len(rows) == 7, ch
    return art([r + "." for r in rows] + ["........"])

# ---------------------------------------------------------------- tiles
def wall_glyph(mask):
    """mask bits: 1=up 2=left 4=down 8=right (connected wall neighbours)."""
    g = [[0] * 8 for _ in range(8)]
    def setp(x, y): g[y][x] = 1
    up, left, down, right = mask & 1, mask & 2, mask & 4, mask & 8
    corner = None
    if mask == 4 | 8: corner = 'dr'
    elif mask == 4 | 2: corner = 'dl'
    elif mask == 1 | 8: corner = 'ur'
    elif mask == 1 | 2: corner = 'ul'
    if corner:
        base = art(["........", "........", "........", ".....XXX",
                    "....XXXX", "...XXX..", "...XX...", "...XX..."])  # down+right
        b = base
        if corner == 'dl': b = flip_h(base)
        if corner == 'ur': b = flip_v(base)
        if corner == 'ul': b = flip_v(flip_h(base))
        return b
    for y in (3, 4):
        for x in (3, 4):
            setp(x, y)
    if up:
        for y in range(0, 4):
            setp(3, y); setp(4, y)
    if down:
        for y in range(4, 8):
            setp(3, y); setp(4, y)
    if left:
        for x in range(0, 4):
            setp(x, 3); setp(x, 4)
    if right:
        for x in range(4, 8):
            setp(x, 3); setp(x, 4)
    return from_grid(g)

# 8x8 reductions of the arcade tiles. Dots stay 2x2; the pellet is kept
# one pixel narrower than tall so it stays round on wide NTSC pixels.
# honey_glyph in src/snapbug.s must match HONEY.
DOT = art(["........", "........", "........", "...XX...", "...XX...", "........", "........", "........"])
HONEY = art(["........", "..XXXX..", ".XXXXXX.", ".XXXXXX.", ".XXXXXX.", ".XXXXXX.", "..XXXX..", "........"])
DOOR = art(["........", "........", "........", "XXXXXXXX", "XXXXXXXX", "........", "........", "........"])
# LIFE uses the player's right-facing pose, defined with the sprites below.

# Bonus items, level order: (name, art, colour, points).
# Hand-drawn reductions of arcade sprites 0,1,2,4,5,6,3,7 respectively.
# Single-color silhouettes retain stems, cherry pairs, melon netting, the
# flagship's raised wings, bell clapper and key teeth. Scores stay unchanged.
ITEMS = [
    ("CHERRY", [".....XX.", "....X.X.", "...X..X.", "..X...X.", ".XX..XX.", "XXX.XXX.", "XXX.XXX.", ".X...X.."], 2, 100),
    ("BERRY",  ["...XX...", "..XXXX..", ".XXXXXX.", ".X.XXXX.", ".XXX.XX.", "..XXXX..", "..X.X...", "...XX..."], 2, 300),
    ("ORANGE", ["....XX..", "...XX...", "..XXXX..", ".XXXXXX.", ".XXXXXX.", ".XXXXXX.", "..XXXX..", "...XX..."], 7, 500),
    ("APPLE",  ["....X...", "...XX...", ".XX.XX..", ".XXXXXX.", ".XXXX.X.", ".XXXXXX.", "..XXXX..", "..X.XX.."], 2, 700),
    ("MELON",  ["....X...", "...XX...", "..XXXX..", ".X.XX.X.", ".XXXXXX.", ".XX.XXX.", ".X.XX.X.", "..XXXX.."], 5, 1000),
    ("GALAX",  [".X....X.", ".X.XX.X.", ".XXXXXX.", ".XX..XX.", "..XXXX..", "...XX...", "...XX...", "...XX..."], 7, 2000),
    ("BELL",   ["...XX...", "..XXXX..", "..XXXX..", ".XXXXXX.", ".XXXX.X.", ".XXXXXX.", "XXXXXXXX", "...XX..."], 7, 3000),
    ("KEY",    ["..XXXX..", "..X..X..", "..X..X..", "..XXXX..", "...X....", "...XXX..", "...X....", "...XX..."], 1, 5000),
]

# ---------------------------------------------------------------- sprites
# Pac-Man reductions: no eyes, just a round disk and a wedge-shaped mouth.
# Keep the same 6x8 envelope in every direction for wide NTSC pixels;
# rotating a tall bitmap would make the side-facing poses too wide.
# Frame 0 is wide (also the stopped pose), frame 1 is narrow. The shared
# closed disk completes the wide/narrow/closed/narrow chomp cycle.
BUG_UP = [
    art(["........",
         "..X..X..",
         ".XX..XX.",
         ".XX..XX.",
         ".XXXXXX.",
         ".XXXXXX.",
         "..XXXX..",
         "...XX..."]),
    art(["...X....",
         "..XX.X..",
         ".XXX.XX.",
         ".XXX.XX.",
         ".XXXXXX.",
         ".XXXXXX.",
         "..XXXX..",
         "...XX..."]),
]
BUG_RIGHT = [
    art(["...XX...", "..XXXX..", ".XXXX...", ".XXX....",
         ".XXX....", ".XXXX...", "..XXXX..", "...XX..."]),
    art(["...XX...", "..XXXX..", ".XXXXXX.", ".XXXX...",
         ".XXXX...", ".XXXXXX.", "..XXXX..", "...XX..."]),
]
BUG_CLOSED = art(["...XX...", "..XXXX..", ".XXXXXX.", ".XXXXXX.",
                  ".XXXXXX.", ".XXXXXX.", "..XXXX..", "...XX..."])
LIFE = BUG_RIGHT[0]

# Ghost dome and connected skirt: only the bottom row changes phase.
# Directional eye holes are cut into rows 2-4, inside the outline.
SPIDER_UP = [
    art(["...XX...",
         "..XXXX..",
         ".XXXXXX.",
         ".XXXXXX.",
         ".XXXXXX.",
         ".XXXXXX.",
         ".XXXXXX.",
         ".XX..XX."]),
    art(["...XX...",
         "..XXXX..",
         ".XXXXXX.",
         ".XXXXXX.",
         ".XXXXXX.",
         ".XXXXXX.",
         ".XXXXXX.",
         ".X.XX.X."]),
]
# Two-pixel eye holes have a solid rim, masking dots behind the face.
SPIDER_EYES = {
    0: [(2, 2), (2, 3), (5, 2), (5, 3)],
    1: [(2, 3), (2, 4), (4, 3), (4, 4)],
    2: [(2, 3), (2, 4), (5, 3), (5, 4)],
    3: [(3, 3), (3, 4), (5, 3), (5, 4)],
}
# Small eyes above a zigzag mouth. Only the skirt moves.
FRIGHT = [
    art(["...XX...",
         "..XXXX..",
         ".XXXXXX.",
         ".X.XX.X.",
         ".XXXXXX.",
         ".XX..XX.",
         ".X.XX.X.",
         ".XX..XX."]),
    art(["...XX...",
         "..XXXX..",
         ".XXXXXX.",
         ".X.XX.X.",
         ".XXXXXX.",
         ".XX..XX.",
         ".X.XX.X.",
         ".X.XX.X."]),
]
# Returning eyes: white sockets and black directional pupils. Use an
# explicit mask because pupils at the socket edges must also hide the maze.
EYES_MASK = art(["........", "........", "XXX.XXX.", "XXX.XXX.",
                 "XXX.XXX.", "XXX.XXX.", "........", "........"])
EYE_PUPILS = {
    0: [(1, 2), (1, 3), (5, 2), (5, 3)],
    1: [(0, 3), (0, 4), (4, 3), (4, 4)],
    2: [(1, 4), (1, 5), (5, 4), (5, 5)],
    3: [(2, 3), (2, 4), (6, 3), (6, 4)],
}
EYES = {}
for d, pupils in EYE_PUPILS.items():
    g = to_grid(EYES_MASK)
    for x, y in pupils:
        g[y][x] = 0
    EYES[d] = from_grid(g)

# Death: the upward mouth opens until only the lower crescent remains.
POP = [
    art(["........", "........", ".X....X.", ".XX..XX.", ".XXXXXX.", ".XXXXXX.", "..XXXX..", "...XX..."]),
    art(["........", "........", "........", "........", ".X....X.", ".XXXXXX.", "..XXXX..", "...XX..."]),
    art(["........", "........", "........", "........", "........", "........", "..XXXX..", "........"]),
    art(["........"] * 8),
]
POP_SPARK = art([".X....X.", "..X..X..", "........", ".X....X.",
                 "........", "..X..X..", ".X....X.", "........"])

# 3x5 digits for score popups
MINI = {
    '0': ["XXX", "X.X", "X.X", "X.X", "XXX"],
    '1': [".X.", "XX.", ".X.", ".X.", "XXX"],
    '2': ["XXX", "..X", "XXX", "X..", "XXX"],
    '4': ["X.X", "X.X", "XXX", "..X", "..X"],
    '6': ["XXX", "X..", "XXX", "X.X", "XXX"],
    '8': ["XXX", "X.X", "XXX", "X.X", "XXX"],
}

def popup_pair(text):
    """Render text in 3x5 digits into a 16x8 strip -> (left img, right img)."""
    width = len(text) * 4 - 1
    x0 = (16 - width) // 2
    g = [[0] * 16 for _ in range(8)]
    for i, ch in enumerate(text):
        for y, row in enumerate(MINI[ch]):
            for x, p in enumerate(row):
                if p == 'X':
                    g[y + 1][x0 + i * 4 + x] = 1
    left = from_grid([row[:8] for row in g])
    right = from_grid([row[8:] for row in g])
    return left, right

def build_eye_variant(body, d):
    """Cut directional eye holes without changing the ghost's outline."""
    g = to_grid(body)
    for x, y in SPIDER_EYES[d]:
        g[y][x] = 0
    return from_grid(g)

def sprites():
    """Return list of (name, bytes8) in image-index order."""
    imgs = []
    # 0..7 player: dir*2 + frame  (dir 0=up 1=left 2=down 3=right)
    for d in range(4):
        for f in range(2):
            b = (BUG_UP[f], flip_h(BUG_RIGHT[f]),
                 flip_v(BUG_UP[f]), BUG_RIGHT[f])[d]
            imgs.append((f"bug_d{d}_f{f}", b))
    # 8..15 spider: dir*2 + frame
    for d in range(4):
        for f in range(2):
            imgs.append((f"spider_d{d}_f{f}", build_eye_variant(SPIDER_UP[f], d)))
    # 16,17 fright
    imgs.append(("fright_f0", FRIGHT[0]))
    imgs.append(("fright_f1", FRIGHT[1]))
    # 18..21 eyes by dir
    for d in range(4):
        imgs.append((f"eyes_d{d}", EYES[d]))
    # 22..25 pop (death)
    for i, p in enumerate(POP):
        imgs.append((f"pop{i}", p))
    # 26..33 score popups: 200 400 800 1600 (left,right)
    for t in ("200", "400", "800", "1600"):
        l, r = popup_pair(t)
        imgs.append((f"pts{t}_l", l))
        imgs.append((f"pts{t}_r", r))
    # Shared poses are appended, preserving all existing sprite indices.
    imgs.append(("bug_closed", BUG_CLOSED))
    imgs.append(("pop_spark", POP_SPARK))
    return imgs

def sprite_mask(name, b):
    if name.startswith("pts"):
        return [0xFF] * 8
    if name.startswith("eyes_d"):
        return EYES_MASK
    return silhouette(b)

# ---------------------------------------------------------------- charset
CH_BLANK = 0x20
CH_WALL0 = 0x60          # 0x60..0x6F wall glyph by mask
CH_DOOR = 0x70
CH_DOT = 0x71
CH_HONEY = 0x72
CH_LIFE = 0x73
CH_ITEM0 = 0x74          # 0x74..0x7B
CH_DYN0 = 0xC0           # dynamic sprite chars 0xC0..0xFF

COL_WALL = 6   # blue
COL_DOT = 7    # yellow seeds
COL_HONEY = 1  # white honey
COL_DOOR = 4   # purple
COL_TEXT = 1

def build_charset():
    cs = [[0] * 8 for _ in range(256)]
    for ch in FONT:
        cs[ord(ch)] = font_glyph(ch)
    for m in range(16):
        cs[CH_WALL0 + m] = wall_glyph(m)
    cs[CH_DOOR] = DOOR
    cs[CH_DOT] = DOT
    cs[CH_HONEY] = HONEY
    cs[CH_LIFE] = LIFE
    for i, it in enumerate(ITEMS):
        cs[CH_ITEM0 + i] = art(it[1])
    return cs

def maze_tables():
    attr, chars, cols = [], [], []
    def is_wall(c, r):
        if c < 0 or c >= W:
            return r in (TUNNEL_ROW - 1, TUNNEL_ROW + 1)
        if r < 0 or r >= H:
            return False
        return MAZE[r][c] in "#-"
    dots = 0
    for r in range(H):
        for c in range(W):
            t = MAZE[r][c]
            if t == '#':
                m = 0
                for d, bit in ((0, 1), (1, 2), (2, 4), (3, 8)):
                    if is_wall(c + DX[d], r + DY[d]):
                        m |= bit
                attr.append(1); chars.append(CH_WALL0 + m); cols.append(COL_WALL)
            elif t == '.':
                attr.append(0); chars.append(CH_DOT); cols.append(COL_DOT); dots += 1
            elif t == 'o':
                attr.append(0); chars.append(CH_HONEY); cols.append(COL_HONEY); dots += 1
            elif t == ' ':
                attr.append(0); chars.append(CH_BLANK); cols.append(COL_TEXT)
            elif t == 'T':
                attr.append(4); chars.append(CH_BLANK); cols.append(COL_TEXT)
            elif t == 'x':
                attr.append(1); chars.append(CH_BLANK); cols.append(COL_TEXT)
            elif t == '-':
                attr.append(2); chars.append(CH_DOOR); cols.append(COL_DOOR)
            elif t == 'n':
                attr.append(3); chars.append(CH_BLANK); cols.append(COL_TEXT)
            else:
                raise ValueError(t)
    return attr, chars, cols, dots

# ---------------------------------------------------------------- output
def fmt_bytes(label, data, per=16):
    out = [f"{label}:"] if label else []
    for i in range(0, len(data), per):
        out.append("    .byte " + ",".join(f"${b:02X}" for b in data[i:i + per]))
    return "\n".join(out) + "\n"

def main():
    outdir = sys.argv[1]
    preview = None
    if "--preview" in sys.argv:
        preview = sys.argv[sys.argv.index("--preview") + 1]
    os.makedirs(outdir, exist_ok=True)
    check_maze()
    attr, chars, cols, dots = maze_tables()
    hd = home_dirs()
    cs = build_charset()
    imgs = sprites()
    assert len(imgs) <= 40

    with open(os.path.join(outdir, "charset.bin"), "wb") as f:
        f.write(bytes(b for g in cs for b in g))

    s = []
    s.append("; generated by tools/mkdata.py -- do not edit\n")
    s.append(f"MAZE_W = {W}\nMAZE_H = {H}\nMAZE_ROW0 = {MAZE_SCREEN_ROW}\n")
    s.append(f"TOTAL_DOTS = {dots}\n")
    s.append(f"PSTART_X = {PLAYER_START[0]}\nPSTART_Y = {PLAYER_START[1]}\n")
    s.append(f"HOME_X = {HOME_TILE[0]}\nHOME_Y = {HOME_TILE[1]}\n")
    s.append(f"DOOR_X = {DOOR_TILE[0]}\nDOOR_Y = {DOOR_TILE[1]}\n")
    s.append(f"BONUS_X = {BONUS_TILE[0]}\nBONUS_Y = {BONUS_TILE[1]}\n")
    s.append(f"TUNNEL_ROW = {TUNNEL_ROW}\n")
    s.append(f"CH_BLANK = ${CH_BLANK:02X}\nCH_DOOR = ${CH_DOOR:02X}\nCH_DOT = ${CH_DOT:02X}\n")
    s.append(f"CH_HONEY = ${CH_HONEY:02X}\nCH_LIFE = ${CH_LIFE:02X}\nCH_ITEM0 = ${CH_ITEM0:02X}\n")
    s.append(f"CH_DYN0 = ${CH_DYN0:02X}\nCH_WALL0 = ${CH_WALL0:02X}\n")
    s.append(f"COL_WALL = {COL_WALL}\nCOL_DOT = {COL_DOT}\nCOL_HONEY = {COL_HONEY}\nCOL_TEXT = {COL_TEXT}\n")
    s.append(f"NUM_IMAGES = {len(imgs)}\n")
    for i, (name, _) in enumerate(imgs):
        s.append(f"IMG_{name.upper()} = {i}\n")
    with open(os.path.join(outdir, "consts.inc"), "w") as f:
        f.write("".join(s))

    d = []
    d.append("; generated by tools/mkdata.py -- do not edit\n")
    d.append(fmt_bytes("maze_attr", attr, W))
    d.append(fmt_bytes("maze_chars", chars, W))
    d.append(fmt_bytes("maze_cols", cols, W))
    d.append(fmt_bytes("home_dir", hd, W))
    # sprite sources: 8 data bytes then 8 mask bytes per image
    src = []
    for name, b in imgs:
        # Pupils stay black; score popups stay readable over walls/seeds.
        mask = sprite_mask(name, b)
        src += b + mask
    d.append(fmt_bytes("sprite_src", src, 16))
    d.append(fmt_bytes("item_points_hi", [((it[3] // 100) // 10) << 4 | ((it[3] // 100) % 10) if it[3] < 10000 else 0 for it in ITEMS], 8))
    d.append(fmt_bytes("item_cols", [it[2] for it in ITEMS], 8))
    with open(os.path.join(outdir, "data.inc"), "w") as f:
        f.write("".join(d))

    print(f"maze ok: {dots} seeds, {len(imgs)} sprite images")

    if preview:
        os.makedirs(preview, exist_ok=True)
        write_previews(preview, cs, imgs, chars, cols)

PAL = [(0, 0, 0), (255, 255, 255), (182, 31, 33), (77, 240, 255), (180, 63, 255),
       (68, 226, 55), (26, 52, 255), (220, 215, 27)]

def write_previews(pdir, cs, imgs, chars, cols):
    from PIL import Image
    S = 4
    im = Image.new("RGB", (W * 8 * S, H * 8 * S))
    px = im.load()
    for r in range(H):
        for c in range(W):
            g = cs[chars[r * W + c]]
            col = PAL[cols[r * W + c]]
            for y in range(8):
                for x in range(8):
                    if (g[y] >> (7 - x)) & 1:
                        for a in range(S):
                            for b in range(S):
                                px[(c * 8 + x) * S + a, (r * 8 + y) * S + b] = col
    im.save(os.path.join(pdir, "maze.png"))
    S = 8
    n = len(imgs)
    im = Image.new("RGB", (n * 10 * S, 10 * S), (40, 40, 40))
    px = im.load()
    for i, (name, b) in enumerate(imgs):
        for y in range(8):
            for x in range(8):
                on = (b[y] >> (7 - x)) & 1
                c = (255, 220, 0) if on else (0, 0, 0)
                for a in range(S):
                    for bb in range(S):
                        px[(i * 10 + 1 + x) * S + a, (1 + y) * S + bb] = c
    im.save(os.path.join(pdir, "sprites.png"))
    im = Image.new("RGB", (16 * 9 * 4, 16 * 9 * 4), (40, 40, 40))
    px = im.load()
    for code in range(256):
        g = cs[code]
        ox, oy = (code % 16) * 9, (code // 16) * 9
        for y in range(8):
            for x in range(8):
                if (g[y] >> (7 - x)) & 1:
                    for a in range(4):
                        for bb in range(4):
                            px[(ox + x) * 4 + a, (oy + y) * 4 + bb] = (255, 255, 255)
    im.save(os.path.join(pdir, "charset.png"))
    write_actor_previews(pdir, imgs)

def write_actor_previews(pdir, imgs):
    """Labeled sprite sheet and animation at the NTSC 3:2 pixel aspect."""
    from PIL import Image, ImageDraw

    def tile(b, color):
        im = Image.new("RGB", (8, 8))
        im.putdata([PAL[color] if (row >> (7 - x)) & 1 else PAL[0]
                    for row in b for x in range(8)])
        return im.resize((72, 48), Image.Resampling.NEAREST)

    sheet = Image.new("RGB", (8 * 112, ((len(imgs) + 7) // 8) * 80), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    for i, (name, b) in enumerate(imgs):
        color = (2 if name.startswith("spider") else
                 6 if name.startswith("fright") else
                 1 if name.startswith("eyes") else
                 3 if name.startswith("pts") else 7)
        x, y = (i % 8) * 112, (i // 8) * 80
        draw.text((x + 4, y + 4), f"{i}: {name}", fill="white")
        sheet.paste(tile(b, color), (x + 20, y + 22))
    sheet.save(os.path.join(pdir, "sprites-ntsc.png"))

    sheet = Image.new("RGB", (8 * 112, 104), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    for i, (name, rows, color, points) in enumerate(ITEMS):
        x = i * 112
        draw.text((x + 8, 6), name, fill="white")
        sheet.paste(tile(art(rows), color), (x + 20, 26))
        draw.text((x + 8, 84), f"{points} PTS", fill="white")
    sheet.save(os.path.join(pdir, "items-ntsc.png"))

    frames = []
    images = dict(imgs)
    death = [BUG_CLOSED, BUG_CLOSED, BUG_UP[1], BUG_UP[0],
             POP[0], POP[0], POP[1], POP[1], POP[2], POP[2],
             POP_SPARK, POP_SPARK, POP[3], POP[3], POP[3], POP[3]]
    for t in range(32):
        im = Image.new("RGB", (560, 5 * 72 + 24), (24, 24, 28))
        draw = ImageDraw.Draw(im)
        for d, direction in enumerate(("UP", "LEFT", "DOWN", "RIGHT")):
            draw.text((160 + d * 100, 6), direction, fill="white")
        for r, label in enumerate(("PAC-MAN", "GHOSTS", "FRIGHTENED", "RETURNING EYES", "DEATH")):
            draw.text((8, 48 + r * 72), label, fill="white")
        f = (0, 1, 2, 1)[t % 4]
        for d in range(4):
            poses = [BUG_CLOSED if f == 2 else images[f"bug_d{d}_f{f}"],
                     images[f"spider_d{d}_f{(t // 2) % 2}"],
                     FRIGHT[(t // 2) % 2], EYES[d]]
            for r, (b, color) in enumerate(zip(poses, (7, (2, 4, 3, 7)[d], 6, 1))):
                im.paste(tile(b, color), (148 + d * 100, 28 + r * 72))
        im.paste(tile(death[t // 2], 7), (148, 28 + 4 * 72))
        frames.append(im)
    frames[0].save(os.path.join(pdir, "actors.gif"), save_all=True,
                   append_images=frames[1:], duration=80, loop=0)

if __name__ == "__main__":
    main()
