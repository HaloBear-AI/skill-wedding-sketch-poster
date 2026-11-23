#!/usr/bin/env python3
"""Install verified OFL fonts for a source checkout of the skill."""

from hashlib import sha256
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from urllib.request import urlopen


BASE = "https://raw.githubusercontent.com/google/fonts/06bfe0d62a98375cb09c942fa18e68bd32cff057/ofl/"
TARGET = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONTS = (
    ("CutiveMono-Regular.ttf", "cutivemono/CutiveMono-Regular.ttf", 80_004,
     "96a36a00079058684982f61ee334323f8b501d7b68dcecd6049a4f9177e3a62c"),
    ("NotoSansSC-Variable.ttf", "notosanssc/NotoSansSC%5Bwght%5D.ttf", 17_772_300,
     "a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da"),
)


def install(name: str, source: str, size: int, digest: str) -> None:
    target = TARGET / name
    if target.exists():
        if target.stat().st_size != size or sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError(f"{name} differs from the pinned font. Move it aside before retrying.")
        print(f"Verified existing {name}")
        return

    with urlopen(BASE + source, timeout=45) as response:
        font = response.read(size + 1)
    if len(font) != size or sha256(font).hexdigest() != digest:
        raise ValueError(f"Download verification failed for {name}.")
    temporary = None
    try:
        with NamedTemporaryFile(dir=TARGET, prefix=f".{name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(font)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Installed and verified {name}")


if __name__ == "__main__":
    try:
        TARGET.mkdir(parents=True, exist_ok=True)
        for spec in FONTS:
            install(*spec)
    except (OSError, ValueError) as error:
        sys.exit(f"Font setup failed: {error}")
