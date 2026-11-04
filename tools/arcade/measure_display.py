#!/usr/bin/env python3
"""Capture lossless VICE raster frames and actor/background states, externally.

No guest instrumentation, PC gating, timer changes or renderer changes. Analyse
the resulting files with analyze_display.py; RAM pictures alone are not video.
"""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from rate_match import ROOT, Observer, call_sites, digest, game_state, write_json
from record_playthrough import FPS
from record_shadow import launch, verify_loaded_program

FRAME_CYCLES = 65*261


def capture(source, reference, out, count):
    out.mkdir(parents=True, exist_ok=True)
    (out/'frames').mkdir(exist_ok=True)
    if (out/'recording.json').exists():
        raise FileExistsError(f'Use a new output directory: {out}')
    prg = out/'captured-program.prg'
    shutil.copy2(source, prg)
    shutil.copy2(source.with_suffix('.lbl'), prg.with_suffix('.lbl'))
    labels = {p[2][1:]: int(p[1], 16) for line in
              prg.with_suffix('.lbl').read_text().splitlines() if len(p := line.split()) == 3}
    sites = call_sites(prg)
    vice, original, log = launch(prg, out)
    mon = Observer(original.s)
    mon.req, mon.last_hit = original.req, None
    frames, inputs, events = [], [], []
    expected = {x['tick']: x for x in reference['inputs']}
    phase, active, completed, last_tick = 'boot', False, 0, -1
    last_mod, epoch, captured_epoch = None, 0, None
    archive = zipfile.ZipFile(out/'memory.zip', 'w', zipfile.ZIP_DEFLATED)
    try:
        mon.joystick('-')
        identity = verify_loaded_program(mon, prg, labels)
        names = mon.register_names()
        raster = mon.checkpoint(0, 65535, '(RL == $1) && (CY < $8)')
        rearm = mon.checkpoint(0, 65535, '(RL != $1) || (CY >= $8)')
        mon.enable(rearm, False)
        hooks = {
            mon.checkpoint(sites['frame_wait']+3): 'controls',
            mon.checkpoint(sites['video_refresh']): 'render',
            mon.checkpoint(labels['video_update_end']): 'paint',
            mon.checkpoint(labels['video_frame_end']): 'complete',
        }
        palette = mon.palette()
        tables = {n: list(mon.memory(labels[n], size)) for n, size in
                  (('arcade_sprites', 768), ('arcade_eyes', 96),
                   ('arcade_sprite_class', 16), ('arcade_colors', 128))}
        write_json(out/'tables.json', tables)
        for iteration in range(150000):
            mon.last_hit = None
            mon.run_until_stop()
            hit = mon.last_hit
            registers = mon.registers()
            line, cycle = registers[names['LIN']], registers[names['CYC']]
            modulo = line*65+cycle
            if last_mod is not None and modulo < last_mod:
                epoch += FRAME_CYCLES
            last_mod = modulo
            clock = epoch+modulo
            # A controls/paint breakpoint can coincide with the raster hook.
            # VICE reports just one checkpoint then advances past the others.
            # Sample ANY stop in the window once, so that collision cannot
            # silently drop an entire displayed frame.
            if active and line == 1 and cycle < 8 and captured_epoch != epoch:
                mon.enable(raster, False)
                mon.enable(rearm, True)
                captured_epoch = epoch
                image = mon.picture(palette)
                filename = f'frames/{len(frames):05d}.png'
                image.save(out/filename)
                tick = int.from_bytes(mon.memory(labels['arcade_ticks'], 2), 'little')
                frames.append(dict(frame=len(frames), tick=tick, clock=clock,
                                   line=line, cycle=cycle, image=filename,
                                   hook=hooks.get(hit, 'raster'),
                                   completed_renders=completed,
                                   raw_sha256=digest(image.tobytes())))
                if len(frames) % 120 == 0:
                    print(f'{len(frames)}/{count} raster frames, tick {tick}', flush=True)
                if len(frames) >= count:
                    break
            if hit == rearm:
                mon.enable(rearm, False)
                mon.enable(raster, True)
                continue
            if hit == raster:
                mon.enable(raster, False)
                mon.enable(rearm, True)
                continue
            elif hooks.get(hit) == 'controls':
                mem = mon.memory(0, 4096)
                tick = int.from_bytes(mem[labels['arcade_ticks']:labels['arcade_ticks']+2], 'little')
                assert tick > last_tick, (tick, last_tick)
                last_tick = tick
                inp = expected.get(tick)
                if inp is None:
                    raise AssertionError(f'Input trace ends before tick {tick}')
                phase, direction = inp['phase'], inp['direction']
                if phase == 'play':
                    actual = game_state(mem)
                    assert actual == inp['state_sha256'], ('state mismatch', tick)
                    active = True
                inputs.append(dict(tick=tick, phase=phase, direction=direction,
                                   state_sha256=game_state(mem), clock=clock,
                                   attributes=list(mem[0xc20:0xc30]),
                                   positions=list(mem[0xc30:0xc40])))
                mon.joystick(direction)
            elif hit in hooks:
                if phase not in ('lead-in', 'play'):
                    continue
                kind = hooks[hit]
                mem = mon.memory(0, 8192)
                colors = bytes(v & 15 for v in mon.memory(0x9600, 196))
                filename = f'{len(events):05d}.bin'
                archive.writestr(filename, mem+colors)
                events.append(dict(kind=kind, clock=clock, line=line, cycle=cycle,
                                   tick=int.from_bytes(mem[labels['arcade_ticks']:labels['arcade_ticks']+2], 'little'),
                                   memory=filename))
                if kind == 'complete':
                    completed += 1
            else:
                raise AssertionError(('unexpected stop', hit))
        else:
            raise RuntimeError('Capture timed out')
        mon.cmd(0xbb)
        vice.wait(timeout=10)
        assert all(f['line'] == 1 and f['cycle'] < 8 for f in frames)
        result = dict(prg_sha256=digest(prg.read_bytes()), loaded_program=identity,
                      emulator='VICE 3.7.1 xvic, vic20ntsc, -memory all',
                      input_trace_sha256=digest(json.dumps(reference, sort_keys=True).encode()),
                      code_bytes_patched=False, pc_render_gate=False,
                      frame_rate=str(FPS), palette=palette[:48],
                      frames=frames, inputs=inputs, events=events,
                      cpu_hz=1022727, cycles_per_vic_frame=FRAME_CYCLES,
                      image_source='VICE raster drawing buffer, lossless RGB PNG',
                      memory_layout='8 KiB $0000-$1fff followed by 196 colour nibbles $9600')
        write_json(out/'recording.json', result)
        print(f'Saved {len(frames)} lossless raster frames and {len(events)} state snapshots to {out}', flush=True)
        return result
    finally:
        archive.close()
        if vice.poll() is None:
            vice.terminate()
            vice.wait(timeout=10)
        mon.s.close()
        log.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prg', type=Path, default=ROOT/'build/pacman.prg')
    p.add_argument('--input', type=Path, default=ROOT/'build/rate-match/active-1200/trial/recording.json')
    p.add_argument('--output', type=Path, default=ROOT/'build/display-profile/current/vice')
    p.add_argument('--frames', type=int, default=1200)
    args = p.parse_args()
    if args.frames < 60:
        p.error('--frames must be at least 60')
    capture(args.prg.resolve(), json.loads(args.input.read_text()), args.output.resolve(), args.frames)


if __name__ == '__main__':
    main()
