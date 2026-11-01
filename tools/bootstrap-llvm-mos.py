#!/usr/bin/env python3
"""Install the pinned, local Linux x86-64 LLVM-MOS SDK (no system changes)."""
import argparse, hashlib, shutil, tarfile, tempfile, urllib.request
from pathlib import Path

VERSION = "23.4.0"
SHA256 = "0b1dbc8a2b15db88a1a400a687ea24cf1a38548c5ba9fdd61a473e4580ba00c1"
URL = f"https://github.com/llvm-mos/llvm-mos-sdk/releases/download/v{VERSION}/llvm-mos-linux.tar.xz"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="tools/llvm-mos")
    args = ap.parse_args()
    out = Path(args.output)
    compiler = out / "bin/mos-sim-clang"
    if compiler.exists():
        compiler.touch()
        return
    print(f"Downloading LLVM-MOS SDK {VERSION} (116 MB) into {out}", flush=True)
    with tempfile.TemporaryDirectory(prefix="vic-man-toolchain-") as temp:
        temp = Path(temp)
        archive = temp / "sdk.tar.xz"
        urllib.request.urlretrieve(URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            raise SystemExit("LLVM-MOS archive checksum mismatch")
        with tarfile.open(archive) as tar:
            tar.extractall(temp / "unpack", filter="data")
        candidates = list((temp / "unpack").glob("*/bin/mos-sim-clang"))
        if len(candidates) != 1:
            raise SystemExit("Unexpected LLVM-MOS archive layout")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(candidates[0].parent.parent), str(out))
    compiler.touch()


if __name__ == "__main__":
    main()
