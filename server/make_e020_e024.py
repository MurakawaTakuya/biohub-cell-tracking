"""E020-E024: 9/28 candidates, prepared before the E016-E019 scores arrive (see docs/session_handoff.md).

All start from E006 + SAFEDIV_DIAG logging (same as E016-E019) and E013's rescue 0.5, then:
  E020: E016 (divergence 1.25) with rescue 0.7
  E021: E019 (gate 0.5 + divergence 1.25) with rescue 0.7
  E022: E013 with divergence 1.75
  E023: E018 (gate 0.5) with divergence 1.75
  E024: E013 with nearest-neighbour fallback: try the 2nd-nearest candidate to the existing daughter
        only when the nearest one fails every per-candidate check (BIOHUB_SAFE_DIV_NN_FALLBACK=1).
        With the flag off the function behaves exactly as before.
"""
import json
from pathlib import Path

from make_e016_e019 import E006, ROOT, add_diag, append_env

NN_QUERY = (
    "            mutual_nn_id = None\n"
    "            if candidate_tree is not None:\n"
    "                _, nn_idx = candidate_tree.query(_position_um(existing_child))\n"
    "                mutual_nn_id = candidate_ids[int(nn_idx)]\n"
)
NN_QUERY_NEW = (
    "            mutual_nn_id = None\n"
    "            _nn_order = None\n"
    "            if candidate_tree is not None:\n"
    "                if SAFE_DIV_NN_FALLBACK and len(candidate_ids) >= 2:\n"
    "                    _, _nn_idx2 = candidate_tree.query(_position_um(existing_child), k=2)\n"
    "                    _nn_order = [candidate_ids[int(i)] for i in _nn_idx2]\n"
    "                    mutual_nn_id = _nn_order[0]\n"
    "                else:\n"
    "                    _, nn_idx = candidate_tree.query(_position_um(existing_child))\n"
    "                    mutual_nn_id = candidate_ids[int(nn_idx)]\n"
)
LOOP = "            for candidate_id in candidate_ids:\n                if (source_id, candidate_id) in existing_edges:"
LOOP_NEW = ("            for candidate_id in (_nn_order if _nn_order is not None else candidate_ids):\n"
            "                if (source_id, candidate_id) in existing_edges:")
NN_CHECK = "                if SAFE_DIV_REQUIRE_MUTUAL_NN and candidate_id != mutual_nn_id:\n"
NN_CHECK_NEW = "                if SAFE_DIV_REQUIRE_MUTUAL_NN and _nn_order is None and candidate_id != mutual_nn_id:\n"
APPEND = "                proposals.append((score, source_id, candidate_id, parent_dist, sister_dist))\n"
APPEND_NEW = (APPEND
              + "                if _nn_order is not None:\n"
              + "                    if candidate_id != _nn_order[0]:\n"
              + '                        stats["sd_diag_nn_fallback_used"] = stats.get("sd_diag_nn_fallback_used", 0) + 1\n'
              + "                    break\n")
DEF = "def add_safe_divisions_postlink(\n"


def add_nn_fallback(cell):
    a = cell.index(DEF)
    b = cell.index("\ndef ", a + 10)
    f = cell[a:b]
    for old, new in [(NN_QUERY, NN_QUERY_NEW), (LOOP, LOOP_NEW), (NN_CHECK, NN_CHECK_NEW), (APPEND, APPEND_NEW)]:
        assert f.count(old) == 1, old[:40]
        f = f.replace(old, new)
    flag = 'SAFE_DIV_NN_FALLBACK = os.environ.get("BIOHUB_SAFE_DIV_NN_FALLBACK", "0") != "0"\n\n\n'
    return cell[:a] + flag + f + cell[b:]


R05 = {"BIOHUB_DIVNET_RESCUE_MIN_PROB": "0.5"}
VARIANTS = [
    ("e020-x138-r07-diverge125", "E020: E016 with rescue 0.7.",
     {"BIOHUB_SAFE_DIV_DIVERGE_UM": "1.25", "BIOHUB_DIVNET_RESCUE_MIN_PROB": "0.7"}, "Biohub E020 x138 R07 Diverge125", False),
    ("e021-x138-r07-gate05-diverge125", "E021: E019 with rescue 0.7.",
     {"BIOHUB_DIVNET_MIN_PROB": "0.5", "BIOHUB_SAFE_DIV_DIVERGE_UM": "1.25", "BIOHUB_DIVNET_RESCUE_MIN_PROB": "0.7"},
     "Biohub E021 x138 R07 Gate05 Diverge125", False),
    ("e022-x138-r05-diverge175", "E022: E013 with divergence 1.75 um.",
     {"BIOHUB_SAFE_DIV_DIVERGE_UM": "1.75"}, "Biohub E022 x138 R05 Diverge175", False),
    ("e023-x138-r05-gate05-diverge175", "E023: E018 with divergence 1.75 um.",
     {"BIOHUB_DIVNET_MIN_PROB": "0.5", "BIOHUB_SAFE_DIV_DIVERGE_UM": "1.75"}, "Biohub E023 x138 R05 Gate05 Diverge175", False),
    ("e024-x138-r05-nnfallback", "E024: E013 with nearest-neighbour fallback to the 2nd candidate.",
     {"BIOHUB_SAFE_DIV_NN_FALLBACK": "1"}, "Biohub E024 x138 R05 NNFallback", True),
]

if __name__ == "__main__":
    for tag, header, env, title, fallback in VARIANTS:
        nb = json.loads((E006 / "notebook.ipynb").read_text())
        meta = json.loads((E006 / "kernel-metadata.json").read_text())
        cell = add_diag("".join(nb["cells"][5]["source"]))
        if fallback:
            cell = add_nn_fallback(cell)
        nb["cells"][5]["source"] = cell.splitlines(keepends=True)
        append_env(nb, "E013: DivNet rescue 0.5 on E006.", R05)
        append_env(nb, header, env)
        out = ROOT / f"submit-{tag}"
        out.mkdir(exist_ok=True)
        (out / "notebook.ipynb").write_text(json.dumps(nb, indent=1))
        (out / "kernel-metadata.json").write_text(json.dumps(dict(meta, id=f"versavice/biohub-{tag}", title=title), indent=2))
        print("wrote", out)
