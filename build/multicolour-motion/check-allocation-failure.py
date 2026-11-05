"""Inject capacity exhaustion and follow the real preparation failure branch."""
import json
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
build = ROOT / "build/multicolour-motion"
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools/arcade"))
from native import Sim
from check_multicolour_motion import expected_scene, image_state

listing = (build / "cell-allocation.lst").read_text()
match = re.search(r"^([0-9A-F]{6})r.*?\bprepare_failed:$", listing, re.M)
failure_address = 0x2000 + int(match[1], 16)
maximum = bytes(value for actor in range(6)
                for value in (3 + actor * 12, 59, 0, 2 + actor % 6))
replay = (build / "replay.bin").read_bytes()
poses = json.loads((build / "poses.json").read_text())["images"]
charset = (build / "background-charset.bin").read_bytes()
background = [charset[c * 8:c * 8 + 8] for c in (build / "background-map.bin").read_bytes()]
colors = (build / "background-colors.bin").read_bytes()
packet = build / "failure-packet.bin"
dump_path = build / "failure.ram"
work_path = build / "failure-map.bin"
guard_path = build / "failure-guard.bin"
guard_path.write_bytes(bytes([0xA5]) * 960)
cases = []
for column, path in ((18, "left"), (17, "middle"), (16, "right")):
    sim = Sim(build / "motion.prg")
    def load(data):
        packet.write_bytes(data)
        sim.cmd("load actors " + str(packet.relative_to(ROOT)))
    def dump():
        sim.cmd("dump " + str(dump_path.relative_to(ROOT)))
        return dump_path.read_bytes()
    try:
        sim.cmd("until demo_ready 100")
        sim.cmd("load $1c40 " + str(guard_path.relative_to(ROOT)))
        load(maximum)
        sim.cmd("call mc_prepare")
        assert sim.peek("mc_new_count")[0] == 54
        memory = dump()
        work = sim.labels["cell_work"]
        work_path.write_bytes(memory[work:work + 567])
        sim.cmd("call mc_abort")
        # Run the normal caller with valid maximum-footprint metadata. Inject
        # one extra allocation at the first band, with existing cells allowing
        # the middle/right variants to reach their respective allocation paths.
        sim.cmd("until mc_prepare 100")
        load(maximum)
        sim.cmd("until resolve_row 100")
        sim.cmd("load cell_work " + str(work_path.relative_to(ROOT)))
        sim.cmd("poke mc_new_count 54")
        sim.cmd("poke current_band 7")
        sim.cmd(f"poke actor_col {column}")
        before = image_state(dump())
        hit = sim.cmd(f"until ${failure_address:x} 100")
        assert any(line.startswith(f"hit ${failure_address:04X} ") for line in hit), hit
        assert sim.peek("mc_status")[0] == 1
        assert sim.peek("mc_new_count")[0] == 54
        assert image_state(dump()) == before
        sim.cmd("until demo_presented 100")
        memory = dump()
        assert memory[sim.labels["mc_pending"]] == 0
        assert memory[work:work + 567] == bytes([255]) * 567
        assert image_state(memory) == before
        assert memory[0x1C40:0x2000] == bytes([0xA5]) * 960
        load(replay[:24])
        sim.cmd("call mc_prepare")
        sim.cmd("call mc_commit")
        memory = dump()
        assert image_state(memory) == expected_scene(replay[:24], poses, background, colors)
        assert memory[sim.labels["mc_status"]] == 0
        assert memory[0x1C40:0x2000] == bytes([0xA5]) * 960
        cases.append({"allocation_path": path, "caller_reached_failure_branch": True,
                      "visible_image_and_guard_preserved": True,
                      "map_cleanup_and_subsequent_recovery": True})
    finally:
        sim.close()
result = {"status": "passed", "failure_branch": failure_address,
          "native_test_only": True, "capacity_fault_injected": True,
          "cases": cases}
(build / "cell-allocation-failure.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
