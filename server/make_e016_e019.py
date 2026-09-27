"""E016-E019: E013 (gate 0.3, rescue 0.5) + safe-division geometry / gate changes, with diagnostic logging.

2x2 (rescue 0.5 everywhere):
            gate 0.3   gate 0.5
  div 2.25  E013       E018
  div 1.25  E016       E019
E017: E013 + one-directional nearest-neighbour requirement off.

The diagnostics only add counters and one print per dataset (SAFEDIV_DIAG); decisions are unchanged:
  - divergence rejections split into structure (no single t+2 successor) vs distance (increment < threshold)
  - distance rejections whose increment lies in [1.25, 2.25)
  - proposals left unused because the per-frame cap was reached
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
E006 = ROOT / "submit-e006-x138-gate03"

DIV = 'stats["safe_division_divergence_rejected"] += 1'
FRAME_CAP = "            if added_this_frame >= frame_cap:\n                break"
END = '    if added:\n        stats["safe_divisions_added"] = len(added)'
DIST_TEST = "                    if grandchild_dist - sister_dist < SAFE_DIV_DIVERGE_UM:\n"


def bump(key):
    return f'stats["{key}"] = stats.get("{key}", 0) + 1'


def add_diag(cell):
    a = cell.index("def add_safe_divisions_postlink(")
    b = cell.index("\ndef ", a + 10)
    f = cell[a:b]
    assert f.count(DIV) == 3 and f.count(FRAME_CAP) == 1 and f.count(END) == 1 and f.count(DIST_TEST) == 1
    i1 = f.index(DIV)
    i2 = f.index(DIV, i1 + 1)
    i3 = f.index(DIV, i2 + 1)
    ind = " " * 24
    f = (
        f[:i3] + DIV + "\n" + ind + bump("sd_diag_div_distance")
        + "\n" + ind + "if grandchild_dist - sister_dist >= 1.25:\n" + ind + "    " + bump("sd_diag_div_distance_125_225")
        + f[i3 + len(DIV):]
    )
    f = f[:i2] + DIV + "\n" + ind + bump("sd_diag_div_structure") + f[i2 + len(DIV):]
    f = f[:i1] + DIV + "\n" + ind + bump("sd_diag_div_structure") + f[i1 + len(DIV):]
    f = f.replace(FRAME_CAP, "            if added_this_frame >= frame_cap:\n"
                  "                stats[\"sd_diag_frame_cap_unused\"] = stats.get(\"sd_diag_frame_cap_unused\", 0) + 1\n"
                  "                break")
    f = f.replace(END, '    print(f"  [{dataset}] SAFEDIV_DIAG", {k: v for k, v in stats.items() if k.startswith("sd_diag_")}, flush=True)\n' + END)
    return cell[:a] + f + cell[b:]


def append_env(nb, header, env):
    c0 = "".join(nb["cells"][0]["source"]) + f"\n# {header}\n" + "".join(f'os.environ["{k}"] = "{v}"\n' for k, v in env.items())
    nb["cells"][0]["source"] = c0.splitlines(keepends=True)


VARIANTS = [
    ("e016-x138-r05-diverge125", "E016: divergence 2.25 -> 1.25 um.", {"BIOHUB_SAFE_DIV_DIVERGE_UM": "1.25"}, "Biohub E016 x138 R05 Diverge125"),
    ("e017-x138-r05-nomutualnn", "E017: nearest-neighbour requirement off.", {"BIOHUB_SAFE_DIV_REQUIRE_MUTUAL_NN": "0"}, "Biohub E017 x138 R05 NoMutualNN"),
    ("e018-x138-r05-gate05", "E018: gate 0.3 -> 0.5.", {"BIOHUB_DIVNET_MIN_PROB": "0.5"}, "Biohub E018 x138 R05 Gate05"),
    ("e019-x138-r05-gate05-diverge125", "E019: gate 0.5 + divergence 1.25 um.",
     {"BIOHUB_DIVNET_MIN_PROB": "0.5", "BIOHUB_SAFE_DIV_DIVERGE_UM": "1.25"}, "Biohub E019 x138 R05 Gate05 Diverge125"),
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
