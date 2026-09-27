# Synthetic-graph check for E024: flag off == original add_safe_divisions_postlink; flag on only adds.
# Run from the repo root with numpy + scipy: PYTHONHASHSEED=0 python server/tests/test_nn_fallback.py
import json, random, numpy as np
from scipy.spatial import cKDTree
def extract(path):
    src=''.join(json.load(open(path))['cells'][5]['source'])
    a=src.index('def add_safe_divisions_postlink('); b=src.index('\ndef ',a+10)
    return src[a:b]
base=extract('submit-e016-x138-r05-diverge125/notebook.ipynb')   # E006 + diag (same function body as E013 + diag)
fb=extract('submit-e024-x138-r05-nnfallback/notebook.ipynb')
def make_env(flag, dc_seed):
    g=dict(np=np, cKDTree=cKDTree, OUTPUT_SAFE_DIVISIONS=True, SAFE_DIV_GLOBAL_FRAC_CAP=1.0, SAFE_DIV_FRAME_FRAC_CAP=1.0,
           SAFE_DIV_REQUIRE_MUTUAL_NN=True, SAFE_DIV_REQUIRE_DIVERGENCE=True, SAFE_DIV_EXISTING_CHILD_MAX_UM=10.0,
           SAFE_DIV_MAX_UM=9.0, SAFE_DIV_SISTER_MAX_UM=14.0, SAFE_DIV_DIVERGE_UM=2.25, SAFE_DIV_SISTER_SYMMETRY_TAU=0.6,
           DEEPCENTER_SAFE_DIV_VETO=True, DEEPCENTER_SAFE_DIV_THRESHOLD=0.25, SAFE_DIV_NN_FALLBACK=flag)
    pos=lambda n: np.array([n['z'],n['y'],n['x']],float)
    g['_position_um']=pos; g['edge_distance_um']=lambda a,b: float(np.linalg.norm(pos(a)-pos(b)))
    g['node_point']=lambda n:(n['z'],n['y'],n['x'])
    def dc(dataset,t,pt,*a):
        return random.Random(hash((dc_seed, round(pt[0],6), round(pt[1],6), round(pt[2],6)))).random()<0.5
    g['deepcenter_accept_repair_point']=dc
    g['divnet_rescue_parent']=lambda d,t,s,src,fc: s%3==0
    g['divnet_accept_parent']=lambda d,t,s,src,fc: s%5!=0
    g['divnet_rank_bonus']=lambda *a:0.0
    return g
def graph(seed):
    r=random.Random(seed); nodes={}; edges=[]; nid=0
    for tr in range(60):
        z,y,x=r.uniform(0,30),r.uniform(0,60),r.uniform(0,60); t0=r.randint(0,3); L=r.randint(1,6); prev=None
        for t in range(t0,t0+L):
            z+=r.gauss(0,1);y+=r.gauss(0,1.5);x+=r.gauss(0,1.5)
            nodes[nid]=dict(t=t,z=z,y=y,x=x)
            if prev is not None: edges.append(dict(source_id=prev,target_id=nid))
            prev=nid; nid+=1
    return nodes,edges
def run(fsrc,flag,seed):
    g=make_env(flag,seed); exec(fsrc,g)
    n,e=graph(seed); st={k:0 for k in ['safe_division_mutual_nn_rejected','safe_division_divergence_rejected','safe_division_geometric_candidates','safe_division_symmetry_rejected','safe_division_candidates','safe_division_skipped_cap']}
    import io,contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        out=g['add_safe_divisions_postlink'](n,e,st,dataset='d')
    return sorted((x['source_id'],x['target_id']) for x in out if x.get('safe_division')), st
same=diff=fbused=0
for s in range(300):
    a,_=run(base,False,s); b,_=run(fb,False,s)
    assert a==b, s
    c,st=run(fb,True,s)
    fbused+=st.get('sd_diag_nn_fallback_used',0)
    if c!=a: diff+=1
    # every original addition whose parent is not displaced should be kept unless target conflict
print('flag off identical on 300 graphs; flag on changed', diff, 'graphs; fallback used', fbused, 'times')
lost=0; gained=0
for s in range(300):
    a,_=run(base,False,s); c,st=run(fb,True,s)
    if set(a)-set(c): lost+=1; print('seed',s,'lost',set(a)-set(c),'gained',set(c)-set(a))
    gained+=len(set(c)-set(a))
print('graphs where an original division was lost:', lost, '| divisions gained:', gained)
