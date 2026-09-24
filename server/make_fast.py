"""Make fast variants: fix the validator-selected post-process config and skip the validator.

The validator re-runs the pipeline on 8 train movies for each sweep candidate, which pushed
the hidden-test rerun past the runtime limit. Its choice only depends on train data, so the
selected overrides from the public run can be hard-coded without changing the output.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VARIANTS = {
    # source notebook dir, notebook file, overrides chosen by that notebook's own validator
    "submit-geo-fast": ("submit-geometric-fusion", "biohub-geometric-fusion.ipynb", "local_outputs/geo_out/ppsweep_selected.json",
                        "versavice/biohub-geo-fast", "Biohub Geo Fast"),
    "submit-geo-divnet-fast": ("submit-geo-divnet", "geo-divnet.ipynb", "local_outputs/divnet_out/ppsweep_selected.json",
                               "versavice/biohub-geo-divnet-fast", "Biohub Geo DivNet Fast"),
}

for out_dir, (src_dir, nb_name, sel_path, kid, title) in VARIANTS.items():
    overrides = json.loads((ROOT / sel_path).read_text())["overrides"]
    nb = json.loads(((ROOT / src_dir) / nb_name).read_text())
    extra = "\n\n# Fast variant: validator-selected post-process config fixed, validator skipped.\n"
    extra += 'os.environ["BIOHUB_VALIDATOR_ENABLE"] = "0"\n'
    for k, v in overrides.items():
        extra += f'os.environ["BIOHUB_{k}"] = "{v}"\n'
    cell0 = "".join(nb["cells"][0]["source"]) + extra
    nb["cells"][0]["source"] = cell0.splitlines(keepends=True)
    for c in nb["cells"]:
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    (ROOT / out_dir).mkdir(exist_ok=True)
    ((ROOT / out_dir) / nb_name).write_text(json.dumps(nb, indent=1))
    meta = json.loads(((ROOT / src_dir) / "kernel-metadata.json").read_text())
    meta.update(id=kid, title=title, code_file=nb_name)
    ((ROOT / out_dir) / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    print(out_dir, overrides)
