# -*- coding: utf-8 -*-
"""重复文本统一规范译文表 + 分块瘦身 + 构建时套用（通用机制）

SIG2ZH 为"签名→规范译文"数据表：签名 = 将块内所有数字替换为 # 后的文本。
换一个领域/项目时，按相同格式重写 SIG2ZH / IDENTITY（运行 scripts/canonical.py
会先扫描重复组并报告未覆盖签名，照提示补表即可）。
下方数据为工业标准类文档的示例片段，可整体替换。
"""
import json, re, os, glob
from collections import defaultdict, Counter

import sys as _sys, os as _os
WORK = _sys.argv[1] if len(_sys.argv) > 2 else _os.getcwd()
DOCS = _sys.argv[2:] if len(_sys.argv) > 2 else ["DOC"]

# 签名 -> 规范中文（⟦Ni⟧ 与原文数字串一一对应；纯数字/符号组自动保留原文）
SIG2ZH = {
    # —— 通用示例（按你的文档领域重写）——
    "#.# General": "⟦N0⟧.⟦N1⟧ 总则",                       # 章节标题
    "Document code\nTitle": "文件编号\n标题",                # 表头
    "Term\nDefinition": "术语\n定义",                        # 表头
    "Topic\nReference\nDescription": "主题\n参考条款\n说明",  # 修订表表头
    "Note:": "注：",
    "Guidance note:": "指导性说明：",
    # 运行本脚本会列出"未覆盖签名"，照提示逐条补全即可
}
# 明确保留原文的签名（标准号/代号/单位/纯数值表）
IDENTITY = {
    "EN ISO #", "[kg]", "[mm]", "[tonnes]", "(HAZ)",
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
