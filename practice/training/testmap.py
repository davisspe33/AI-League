import importlib.util, json, sys
spec=importlib.util.spec_from_file_location("bp","BalancedPathfinder/index.py"); bp=importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
rows="""n c7 c7 n n n n n c7 c7
w w w w w c7 w w w w
c40 w n c7 c7 c5 c7 c7 w c41
c4 w c8 w n c7 w c8 w c5
c7 n n c7 c7 c7 c7 c7 c7 n
c8 n w w w w w w w c18
c7 n c1 n c8 c7 c8 n c7 n
w w w c7 c7 c7 c7 c7 w n
c7 c7 w c8 w c8 w c8 w c31
treasure c7 c30 c2 c7 c1 c7 c5 c7 c7""".split("\n")
g=[["wall" if x=="w" else "normal" if x=="n" else x for x in r.split()] for r in rows]
assert len(g)==10 and all(len(r)==10 for r in g)
names="ABCDEFGHIJ"
def lab(p): return f"{names[p[1]]}{p[0]+1}"
def run(label,**o):
    P=bp.make_params(o); mv=bp.plan_moves(g,(0,0),"balanced",P); r=bp.evaluate(g,(0,0),mv,P)
    path=[(0,0)]
    for m in mv: path.append(tuple(m) if not isinstance(m,str) else m)
    print(label, "steps",r["steps"],"chal",r["challenges"],"E[score]",round(r["objective"]),"P(treas)",round(r["p_treasure"],2),"E[lives]",round(r["exp_lives"],2))
    return mv
full={k:1.0 for k in ("c1","c2","c3","c4","c5","c6","c17","c18")}
mv=run("default       ")
mv=run("all-correct   ",p_success={**bp.DEFAULT_PARAMS["p_success"],**full,"c30":1.0,"c31":1.0},step_cost=0)
print(mv[:60])
run("skip c2,c4    ",p_success={**bp.DEFAULT_PARAMS["p_success"],**full,"c2":.05,"c4":.05,"c30":1.0,"c31":1.0},step_cost=0)
run("cap 6 chal    ",p_success={**bp.DEFAULT_PARAMS["p_success"],**full,"c30":1.0,"c31":1.0},step_cost=0,max_challenges=6)
