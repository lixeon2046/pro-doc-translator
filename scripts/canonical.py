# -*- coding: utf-8 -*-
"""重复文本统一规范译文表 + 分块瘦身 + 构建时套用"""
import json, re, os, glob
from collections import defaultdict, Counter

import sys as _sys, os as _os
WORK = _sys.argv[1] if len(_sys.argv) > 2 else _os.getcwd()
DOCS = _sys.argv[2:] if len(_sys.argv) > 2 else ["DOC"]

# 签名 -> 规范中文（⟦Ni⟧ 与原文数字串一一对应；纯数字/符号组自动保留原文）
SIG2ZH = {
    "#.# General": "⟦N0⟧.⟦N1⟧ 总则",
    "#.# Materials": "⟦N0⟧.⟦N1⟧ 材料",
    "#.#.# General": "⟦N0⟧.⟦N1⟧.⟦N2⟧ 总则",
    "#.#-# Equipment assemblies": "⟦N0⟧.⟦N1⟧-⟦N2⟧ 设备组件",
    "#.#-# Offshore containers": "⟦N0⟧.⟦N1⟧-⟦N2⟧ 海上集装箱",
    "#.#-# Portable offshore units": "⟦N0⟧.⟦N1⟧-⟦N2⟧ 便携式海上单元",
    "(A × CD)/MGWSub < #.#\nAnd\n(MGW + A#)/MGWSub < #.#\n#.# m":
        "(A × CD)/MGWSub < ⟦N0⟧.⟦N1⟧\n且\n(MGW + A⟦N2⟧)/MGWSub < ⟦N3⟧.⟦N4⟧\n⟦N5⟧.⟦N6⟧ m",
    "Alloy\nTemper": "合金\n状态",
    "Changes - current": "变更 — 现行",
    "Condition\nRequirement": "工况\n要求",
    "Contents": "目录",
    "Different/additional\ncriteria (compared\nwith DNV-ST-E#)": "与DNV-ST-E⟦N0⟧\n不同/附加\n的准则",
    "Document code\nTitle": "文件编号\n标题",
    "Enhancement factor": "增强系数",
    "Four leg lifting set at\nTwo leg lifting set at": "四腿吊装组件（夹角）\n两腿吊装组件（夹角）",
    "Function\nRequirements": "功能\n要求",
    "General requirements": "一般要求",
    "Guidance note #:": "指导性说明⟦N0⟧：",
    "Guidance note:": "指导性说明：",
    "Level #": "等级⟦N0⟧",
    "Minimum required working load limit (WLLmin)": "最低要求额定工作载荷（WLLmin）",
    "NORSOK Z-# clause": "NORSOK Z-⟦N0⟧ 条款",
    "Note #:": "注⟦N0⟧：",
    "Note:": "注：",
    "OFFSHORE CONTAINER DATA PLATE": "海上集装箱数据标牌",
    "R#-SE\nYes #)\nNo\nNo": "R⟦N0⟧-SE\n是 ⟦N1⟧)\n否\n否",
    "Rating": "额定值",
    "Sec.#,": "第⟦N0⟧节，",
    "Shackle dimension:": "卸扣尺寸：",
    "Single leg\nsling or\nforerunner": "单腿\n吊索或\n引索",
    "Standard — DNV-ST-E#. Edition April #, amended May #\nPage #":
        "标准 — DNV-ST-E⟦N0⟧。⟦N1⟧年4月版，⟦N2⟧年5月修订\n第⟦N3⟧页",
    "Standard — DNV-ST-E#. Edition August #\nPage #":
        "标准 — DNV-ST-E⟦N0⟧。⟦N1⟧年8月版\n第⟦N2⟧页",
    "Standard — DNV-ST-E#. Edition March #, amended December #\nPage #":
        "标准 — DNV-ST-E⟦N0⟧。⟦N1⟧年3月版，⟦N2⟧年12月修订\n第⟦N3⟧页",
    "Term\nDefinition": "术语\n定义",
    "Topic\nReference\nDescription": "主题\n参考条款\n说明",
    "Visual": "目视",
    "Welded": "焊接",
    "Working load limits [tonnes]\nNominal\nsize of\nsling leg":
        "额定工作载荷 [吨]\n吊索腿\n名义\n尺寸",
    "Yes": "是",
    "Yield strength": "屈服强度",
    "inspection": "检测",
    "max.": "最大",
    "min.": "最小",
    "where:": "式中：",
    "zone #:": "⟦N0⟧ 区：",
    "— From Table #-#, find WLLmin = #.# tonnes.\n— From Table #-#, find WLLs.":
        "— 由表⟦N0⟧-⟦N1⟧查得 WLLmin = ⟦N2⟧.⟦N3⟧ 吨。\n— 由表⟦N4⟧-⟦N5⟧查得 WLLs。",
}
IDENTITY = {  # 明确保留原文
    "DNV AS", "(HAZ)", "(Rp#.#)", "EN ISO #", "HAR/H#", "HBR/H#", "TF/T#",
    "[N/mm#]", "[kg]", "[tonnes]",
    "# mm < D ≤ # mm\n#\n#\n#", "R#\nD ≥ # mm\nD ≥ # mm\nD ≥ # mm\nD ≥ # mm",
    "[mm]\n#°\n#°\n#°\n#°\n#°\n#°\n#°\n#°\n#°\n#°",
}

def norm_key(t):
    return re.sub(r"\d+", "", t.replace("\xa0", " "))[:60]

def ph_all(rep):
    i = [-1]
    def sub(m):
        i[0] += 1
        return f"⟦N{i[0]}⟧"
    return re.sub(r"\d+", sub, rep)

def sig_of(rep_ph):
    return re.sub(r"⟦N\d+⟧", "#", rep_ph)

def build_recurring():
    rec = {}
    missing = []
    for dn in DOCS:
        data = json.load(open(f"{WORK}/extract/{dn}.json"))
        occ = defaultdict(list)
        for p in data["pages"]:
            for b in p["blocks"]:
                t = b["text"].replace("\xa0", " ")
                if not t.strip().startswith("This copy") and len(t) < 90:
                    occ[norm_key(t)].append(t)
        m = {}
        for k, v in occ.items():
            if len(v) < 3: continue
            rep = Counter(v).most_common(1)[0][0]
            rep_ph = ph_all(rep)
            sig = sig_of(rep_ph)
            if sig in SIG2ZH:
                zh = SIG2ZH[sig]
            elif sig in IDENTITY or not re.search(r"[A-Za-z]{2,}", rep_ph):
                zh = rep_ph          # 纯数字/符号/单位：保留原文
            else:
                missing.append(sig); continue
            m[k] = zh
        rec[dn] = m
        print(f"{dn}: {len(m)} 组规范译文" + (f"，未覆盖签名: {missing}" if missing else ""))
    json.dump(rec, open(f"{WORK}/recurring.json", "w"), ensure_ascii=False, indent=1)
    return rec, missing

def slim_chunks(rec):
    """从分块中剔除规范译文覆盖的条目"""
    removed = 0
    for f in glob.glob(f"{WORK}/chunks/*_c*.json"):
        name = os.path.basename(f).replace(".json", "")
        dn = name.rsplit("_c", 1)[0]
        d = json.load(open(f))
        keys = rec.get(dn, {})
        n0 = len(d["items"])
        d["items"] = [it for it in d["items"] if norm_key(it["text"].replace("\xa0"," ")) not in keys
                      and norm_key(re.sub(r"⟦P\d+⟧","",it["text"]).strip()) not in keys]
        removed += n0 - len(d["items"])
        json.dump(d, open(f, "w"), ensure_ascii=False)
    print(f"分块瘦身: 剔除 {removed} 条规范译文条目")

def apply_recurring(dn, data):
    """构建时: 对重复组块返回 {block_id: 中文}"""
    rec = json.load(open(f"{WORK}/recurring.json"))[dn]
    out = {}
    for p in data["pages"]:
        for b in p["blocks"]:
            t = b["text"].replace("\xa0", " ")
            if t.strip().startswith("This copy"): continue
            k = norm_key(t)
            if k in rec and len(t) < 90:
                zh = rec[k]
                runs = re.findall(r"\d+", t)
                zh = re.sub(r"⟦N(\d+)⟧", lambda m: runs[int(m.group(1))] if int(m.group(1)) < len(runs) else "", zh)
                out[b["id"]] = zh
    return out

if __name__ == "__main__":
    rec, missing = build_recurring()
    if missing:
        print("!! 需补签名:", missing); raise SystemExit(1)
    slim_chunks(rec)
