"""Build DivNet variants on the B004 configuration (B002's validator-selected overrides, validator off).

All variants share B004's post-process config, so the only difference from B004 is how DivNet is used.
Source notebook: submit-geo-divnet/geo-divnet.ipynb (regenerate it with make_notebook.py first).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "submit-geo-divnet"
B004_OVERRIDES = json.loads((ROOT / "local_outputs/geo_out/ppsweep_selected.json").read_text())["overrides"]

VARIANTS = {
    # dir: (kernel id, title, DivNet env)
    "submit-e003-divnet-gate03": ("versavice/biohub-e003-divnet-gate03", "Biohub E003 DivNet Gate03",
                                  {"BIOHUB_DIVNET_MIN_PROB": "0.3", "BIOHUB_DIVNET_RANK_WEIGHT_UM": "0.0"}),
    "submit-e004-divnet-rank": ("versavice/biohub-e004-divnet-rank", "Biohub E004 DivNet Rank",
                                {"BIOHUB_DIVNET_MIN_PROB": "0.0", "BIOHUB_DIVNET_RANK_WEIGHT_UM": "10.0"}),
    "submit-e005-divnet-rescue07": ("versavice/biohub-e005-divnet-rescue07", "Biohub E005 DivNet Rescue07",
                                    {"BIOHUB_DIVNET_MIN_PROB": "0.0", "BIOHUB_DIVNET_RANK_WEIGHT_UM": "0.0",
                                     "BIOHUB_DIVNET_RESCUE_MIN_PROB": "0.7"}),
}

import sys

# Optional: build only the named variant dirs (already-pushed dirs are left untouched).
selected = set(sys.argv[1:]) or set(VARIANTS)
for out_dir, (kid, title, divnet_env) in VARIANTS.items():
    if out_dir not in selected:
        continue
    nb = json.loads((SRC / "geo-divnet.ipynb").read_text())
    extra = "\n\n# B004 config fixed (B002 validator selection), validator skipped; DivNet variant settings.\n"
    extra += 'os.environ["BIOHUB_VALIDATOR_ENABLE"] = "0"\n'
    for k, v in B004_OVERRIDES.items():
        extra += f'os.environ["BIOHUB_{k}"] = "{v}"\n'
    for k, v in divnet_env.items():
        extra += f'os.environ["{k}"] = "{v}"\n'
    nb["cells"][0]["source"] = ("".join(nb["cells"][0]["source"]) + extra).splitlines(keepends=True)
    for c in nb["cells"]:
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    out = ROOT / out_dir
    out.mkdir(exist_ok=True)
    (out / "notebook.ipynb").write_text(json.dumps(nb, indent=1))
    meta = json.loads((SRC / "kernel-metadata.json").read_text())
    meta.update(id=kid, title=title, code_file="notebook.ipynb")
    (out / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    print(out_dir, divnet_env)
