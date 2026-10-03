"""校验所有分块译文完整性：id 覆盖、JSON 合法、占位符保留"""
import json, glob, os, re, sys

import sys as _sys
WORK = _sys.argv[1] if len(_sys.argv) > 1 else ".work"
problems = []
total = 0
for cf in sorted(glob.glob(os.path.join(WORK, "chunks", "*_c*.json"))):
    name = os.path.basename(cf).replace(".json", "")
    tf = os.path.join(WORK, "trans", name + ".json")
    if not os.path.exists(tf):
        problems.append(f"{name}: 输出文件缺失"); continue
    try:
        tr = json.load(open(tf, encoding="utf-8"))
    except Exception as e:
        problems.append(f"{name}: JSON 解析失败 {e}"); continue
    ch = json.load(open(cf, encoding="utf-8"))
    ids = {it["id"] for it in ch["items"]}
    miss = ids - set(tr.keys())
    extra = set(tr.keys()) - ids
    nnull = sum(1 for v in tr.values() if v is None)
    # 占位符校验
    ph_bad = []
    for it in ch["items"]:
        v = tr.get(it["id"])
        if v is None: continue
        src_ph = re.findall(r"⟦[PN]\d+⟧", it["text"])
        out_ph = re.findall(r"⟦[PN]\d+⟧", v)
        if sorted(src_ph) != sorted(out_ph):
            ph_bad.append(it["id"])
    total += len(ids)
    stat = f"{name}: items={len(ids)} translated={len(tr)-nnull} null={nnull}"
    if miss: stat += f" MISSING={len(miss)}"
    if extra: stat += f" EXTRA={len(extra)}"
    if ph_bad: stat += f" PH_BAD={ph_bad[:5]}"
    if miss or extra or ph_bad:
        problems.append(stat)
    else:
        print(stat)
print(f"\n总条目: {total}")
if problems:
    print("需修复:"); [print(" ", p) for p in problems]
    sys.exit(1)
print("全部通过 ✔")
