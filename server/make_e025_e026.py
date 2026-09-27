"""E025 / E026: tighten one safe-division geometry filter on E013 (gate 0.3, rescue 0.5), with SAFEDIV_DIAG logging.
Loosening divergence lowered the public LB (E016 0.956, E019 0.955), so test the opposite direction.
  E025: divergence 2.25 -> 3.0 um
  E026: sister symmetry tau 0.6 -> 0.4
"""
import json

from make_e016_e019 import E006, ROOT, add_diag, append_env

VARIANTS = [
    ("e025-x138-r05-diverge300", "E025: E013 with divergence 3.0 um.", {"BIOHUB_SAFE_DIV_DIVERGE_UM": "3.0"}, "Biohub E025 x138 R05 Diverge300"),
    ("e026-x138-r05-symtau04", "E026: E013 with sister symmetry tau 0.4.", {"BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU": "0.4"}, "Biohub E026 x138 R05 SymTau04"),
]

if __name__ == "__main__":
    for tag, header, env, title in VARIANTS:
        nb = json.loads((E006 / "notebook.ipynb").read_text())
        meta = json.loads((E006 / "kernel-metadata.json").read_text())
        nb["cells"][5]["source"] = add_diag("".join(nb["cells"][5]["source"])).splitlines(keepends=True)
        append_env(nb, "E013: DivNet rescue 0.5 on E006.", {"BIOHUB_DIVNET_RESCUE_MIN_PROB": "0.5"})
        append_env(nb, header, env)
        out = ROOT / f"submit-{tag}"
        out.mkdir(exist_ok=True)
        (out / "notebook.ipynb").write_text(json.dumps(nb, indent=1))
        (out / "kernel-metadata.json").write_text(json.dumps(dict(meta, id=f"versavice/biohub-{tag}", title=title), indent=2))
        print("wrote", out)
