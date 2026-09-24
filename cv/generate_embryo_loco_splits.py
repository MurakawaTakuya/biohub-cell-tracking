#!/usr/bin/env python3
"""Create leakage-safe leave-one-embryo-out splits for the Biohub train set.

The competition's examples make it tempting to split individual clips at
random. That leaks embryo-specific appearance and motion statistics, so this
script holds out every clip with the same embryo prefix together.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def embryo_id(name: str) -> str:
    return name.removesuffix(".zarr").split("_", 1)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    samples = sorted(path.name.removesuffix(".zarr") for path in args.train_dir.glob("*.zarr"))
    if not samples:
        raise FileNotFoundError(f"No .zarr samples under {args.train_dir}")

    embryos = sorted({embryo_id(name) for name in samples})
    if len(embryos) < 2:
        raise ValueError(f"Need at least two embryos for LOEO CV, found {embryos}")

    folds = []
    for held_out in embryos:
        test = [name for name in samples if embryo_id(name) == held_out]
        train = [name for name in samples if embryo_id(name) != held_out]
        folds.append({"held_out_embryo": held_out, "train": train, "test": test})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(folds, indent=2) + "\n")
    print(f"Wrote {len(folds)} embryo-level folds to {args.out}")
    for fold in folds:
        print(f"holdout={fold['held_out_embryo']}: train={len(fold['train'])}, test={len(fold['test'])}")


if __name__ == "__main__":
    main()
