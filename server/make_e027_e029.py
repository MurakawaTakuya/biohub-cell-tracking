"""E027-E029: two one-line knobs reported in discussion 743929 (a fork of the public x138 notebook, 0.957 -> 0.958 -> 0.959),
applied on E013 (gate 0.3, rescue 0.5) with SAFEDIV_DIAG logging. Neither key is in the notebook's configuration guard.
  E027: ILP_DIVISION_WEIGHT 1.2 -> 0.4
  E028: READMIT_MIN_SCORE 0.965 -> 0.94
  E029: both
  E030 / E031: readmit min score 0.92 / 0.90 (step further after E028 won)
"""
import json

from make_e016_e019 import E006, ROOT, add_diag, append_env

VARIANTS = [
    ("e027-x138-r05-ilpdiv04", "E027: E013 with ILP division weight 0.4.", {"BIOHUB_ILP_DIVISION_WEIGHT": "0.4"}, "Biohub E027 x138 R05 ILPDiv04"),
    ("e028-x138-r05-readmit094", "E028: E013 with readmit min score 0.94.", {"BIOHUB_READMIT_MIN_SCORE": "0.94"}, "Biohub E028 x138 R05 Readmit094"),
    ("e029-x138-r05-ilpdiv04-readmit094", "E029: E013 with ILP division weight 0.4 and readmit min score 0.94.",
     {"BIOHUB_ILP_DIVISION_WEIGHT": "0.4", "BIOHUB_READMIT_MIN_SCORE": "0.94"}, "Biohub E029 x138 R05 ILPDiv04 Readmit094"),
    # 9/29: E028 (readmit 0.94) was the new best, so step further in the same direction.
    ("e030-x138-r05-readmit092", "E030: E013 with readmit min score 0.92.", {"BIOHUB_READMIT_MIN_SCORE": "0.92"}, "Biohub E030 x138 R05 Readmit092"),
    ("e031-x138-r05-readmit090", "E031: E013 with readmit min score 0.90.", {"BIOHUB_READMIT_MIN_SCORE": "0.90"}, "Biohub E031 x138 R05 Readmit090"),
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
