from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class RabbitZip:
    hz: float
    base_bpm: float
    rabbit_bpm: float
    keycount: float
    x: float
    angle: float
    last_angle: float
    corrected_bpm: float


def calc_rabbit_zip(hz: float, base_bpm: float, *, x: float | None = None) -> RabbitZip:
    rabbit_bpm = hz * 15.0
    keycount = rabbit_bpm / base_bpm
    if x is None:
        x = max(1.0, float(math.floor(keycount)))
    angle = 180.0 * x / keycount
    last_angle = angle * (keycount - math.floor(keycount))
    corrected_bpm = rabbit_bpm * (angle / 180.0)
    return RabbitZip(
        hz=hz,
        base_bpm=base_bpm,
        rabbit_bpm=rabbit_bpm,
        keycount=keycount,
        x=x,
        angle=angle,
        last_angle=last_angle,
        corrected_bpm=corrected_bpm,
    )


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("hz", type=float)
    p.add_argument("base_bpm", type=float)
    p.add_argument("--x", type=float, default=None)
    args = p.parse_args()
    r = calc_rabbit_zip(args.hz, args.base_bpm, x=args.x)
    for k, v in r.__dict__.items():
        print(f"{k}: {v}")
