# -*- coding: utf-8 -*-
"""重复文本统一规范译文表 + 分块瘦身 + 构建时套用（领域数据：SIG2ZH/IDENTITY 按项目重写）

SIG2ZH 为"签名→规范译文"数据表：签名 = 将块内所有数字替换为 # 后的文本（超长截 60 字符）。
IDENTITY_PREFIXES：命中前缀的签名保留原文（ASME 页脚文档代码）。
SYM：方程碎块/纯符号（无>=4字母拉丁词）→ 保留原文。
SKIP：语境依赖、交由分块译者按上下文处理的重复组（不做规范译文，避免跨语境误统一）。
"""
import json, re, os, glob
from collections import defaultdict, Counter

import sys as _sys, os as _os
WORK = _sys.argv[1] if len(_sys.argv) > 2 else _os.getcwd()
DOCS = _sys.argv[2:] if len(_sys.argv) > 2 else ["DOC"]

SIG2ZH = {
    # —— 方程/表说明引语 ——
    "where": "式中：",
    "and": "及",
    # —— 判定流图 ——
    "Yes": "是",
    "No": "否",
    "Yes\nNo": "是\n否",
    "No\nYes": "否\n是",
    # —— 注记引语 ——
    "Note:": "注：",
    "Notes:": "注：",
    "General Notes:": "总注：",
    "(General Notes:)": "（总注：）",
    "General Note:": "总注：",
    "Special Note:": "特定注：",
    "NOTES:": "注：",
    "GENERAL NOTES:": "总注：",
    "GENERAL NOTES:\n(a)": "总注：\n(a)",
    # —— Div.2/3 材料与试验表列头 ——
    "[Note (#)]": "[注(⟦N0⟧)]",
    "Note (#)": "注(⟦N0⟧)",
    "Tensile,": "抗拉,",
    "Yield,": "屈服,",
    "Temper\nThickness,": "状态\n厚度,",
    "Temp.,": "温度,",
    "Min. Yield,": "最小屈服,",
    "Grade\nUNS No.": "牌号\nUNS 号",
    "No.\nGroup": "编号\n组别",
    "Form\nSpec. No.\nType/": "型式\n标准号\n类型/",
    "Condition/\nClass/": "状态/\n等级/",
    "Condition/Thickness,": "状态/厚度,",
    "Material Specification\nType/Grade/Class\nUNS No.\nNominal Composition\nProduct Form":
        "材料标准\n类型/牌号/等级\nUNS 号\n公称成分\n产品型式",
    "Composition\nProduct": "成分\n产品",
    "Design": "设计",
    "Nominal": "公称",
    "Nominal Thickness": "公称厚度",
    "Joint\nType": "接头\n型式",
    "Joint\nCategory\nDesign Notes\nFigure": "接头\n类别\n设计说明\n图",
    "Detail": "详图",
    "MATERIALS": "材料",
    "FABRICATION": "制造",
    "Cycles": "循环次数",
    "(Normative)": "（规范性）",
    "Max. Design": "最高设计",
    "MPa\nNotes": "MPa\n注",
    "ksi\nNotes": "ksi\n注",
    "Date:": "日期：",
    "Date": "日期",
    "Tangent line": "切线",
    "°F (°C), Minimum": "°F (°C)，最小",
    "SI Units": "SI 单位",
    "PWHT Requirements": "PWHT 要求",
    "Hemispherical": "半球形",
    "Radius": "半径",
    "Type no. #": "第 ⟦N0⟧ 类",
    "Manufacturer’s Serial No.\nCRN\nNational Board No.": "制造厂序列号\nCRN\nNB 编号",
    "Manufactured by": "制造单位",
    # —— 表头通用 ——
    "Material": "材料",
    "Bolting": "螺栓连接件",
    "Form": "型式",
    "Size": "尺寸",
    "Size, in.": "尺寸, in.",
    "Nominal Size": "公称尺寸",
    "Temperature": "温度",
    "Thickness": "厚度",
    "Type": "型式",
    "Shape": "形状",
    "Condition": "状态",
    "Grade": "牌号",
    "Specified": "规定值",
    "Classification": "类别",
    "Examination": "检测",
    "Required": "是否要求",
    "Remarks": "备注",
    "Description": "说明",
    "Results": "结果",
    "Parameter": "参数",
    "Legend:": "图例：",
    # —— 页眉/栏目 ——
    "MANDATORY APPENDIX": "强制性附录 ⟦N0⟧",
    "NONMANDATORY APPENDIX": "非强制性附录 ⟦N0⟧",
    "Mandatory Appendix": "强制性附录 ⟦N0⟧",
    "Nonmandatory Appendix": "非强制性附录 ⟦N0⟧",
    "Annex": "附录 ⟦N0⟧",
    "Figure": "图 ⟦N0⟧",
    "Table": "表 ⟦N0⟧",
    "INTENTIONALLY LEFT BLANK": "本页有意留空",
    "CASTI Guidebook to ASME Section VIII Div. # – Pressure Vessels – Third Edition":
        "CASTI 指南：ASME 第VIII卷 第⟦N0⟧册——压力容器（第三版）",
    "Division #": "第⟦N0⟧册",
    "DIVISION #": "第⟦N0⟧册",
    "Chapter": "章",
    "Appendix": "附录",
    "Table of Contents": "目录",
    # —— 修订汇总表（Div.1 Summary of Changes）——
    "Revised": "修订",
    "Revised in its entirety": "全文修订",
    "Page\nLocation\nChange": "页码\n位置\n修改内容",
    # —— 表格表单字段 ——
    "10 test samples __________": "10 个试样 __________________",
    "(#/#)": "⟦N0⟧/⟦N1⟧",
}

# 保留原文的签名（标准号/代号/单位/纯数值表）
IDENTITY = {
    "(#)", "[kg]", "[mm]", "±#%", "(#/#)",
}

# 命中前缀即保留原文（ASME 页眉页脚文档代码 + 页码标签；# 为数字占位）
IDENTITY_PREFIXES_RX = re.compile(r"^ASME BPVC\.VIII\.")

# 模式规则：(签名正则, 词替换表)。在 rep_ph（占位符形式）上做整词替换，⟦N⟧ 结构不动 →
# 构建时按各块自身数字序列回填，规避数字错位。用于图/表/附录标签族。
RX_RULES = [
    (re.compile(r"^Figure "), {"Figure": "图"}),
    (re.compile(r"^Fig\. "), {"Fig.": "图"}),
    (re.compile(r"^TABLE "), {"TABLE": "表"}),
    (re.compile(r"^Table "), {"Table": "表"}),
    (re.compile(r"^MANDATORY APPENDIX "), {"MANDATORY APPENDIX": "强制性附录"}),
    (re.compile(r"^Mandatory Appendix "), {"Mandatory Appendix": "强制性附录"}),
    (re.compile(r"^NONMANDATORY APPENDIX "), {"NONMANDATORY APPENDIX": "非强制性附录"}),
    (re.compile(r"^Nonmandatory Appendix "), {"Nonmandatory Appendix": "非强制性附录"}),
    (re.compile(r"^ANNEX "), {"ANNEX": "附录"}),
    (re.compile(r"^Annex "), {"Annex": "附录"}),
    (re.compile(r"^ARTICLE "), {"ARTICLE": "条款"}),
    (re.compile(r"^Article "), {"Article": "条款"}),
    (re.compile(r"Subject Index"), {"Subject Index": "主题索引"}),
    (re.compile(r"^Revised in its entirety$"), {"Revised in its entirety": "全文修订"}),
    (re.compile(r"^Revised$"), {"Revised": "修订"}),
    # 委员会人名（词首字母缩写式）→ 保留原文
    (re.compile(r"^[A-Z]\.( ?[A-Z]\.){0,2} [A-Z][a-zA-Z'’-]+(,? (Jr|Sr|III)$)?$"), None),
    (re.compile(r"^[A-Z][a-zA-Z'’-]+, [A-Z]\. ?[A-Z]?$"), None),  # Rahoi, D. W.
    # 节尾关键词（编号换行 + 关键词）
    (re.compile(r"#[.#]*\nSCOPE$"), {"SCOPE": "范围"}),
    (re.compile(r"#[.#]*\nFIGURES$"), {"FIGURES": "图"}),
    (re.compile(r"#[.#]*\nNOMENCLATURE$"), {"NOMENCLATURE": "术语与符号"}),
    (re.compile(r"#[.#]*\nTABLES$"), {"TABLES": "表"}),
    (re.compile(r"#[.#]*\nGENERAL$"), {"GENERAL": "总则"}),
    (re.compile(r"^10 test samples _+$"), {"test samples": "个试样"}),
]

# 语境依赖：不做规范译文，留给分块译者按上下文翻译
SKIP = {
    "Member", "Chair", "Vice Chair", "Chairman", "Secretary", "Alternate",
    "Honorary Member", "Contributing Member", "Consulting Member", "Staff",
}

SYM_RE_LATIN = re.compile(r"[A-Za-z]{4,}")
SYM_RE_FULL = re.compile(r"[\d\s.,\-–—°×/%≥≤<>+=()^\[\]{}|±·∙∕'\"^~:;?!*&#$_A-Za-zÅÄÅÉÈÑÖÜαβγδεθλμπσΔΩ≈≡—–‘’“”]*")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

def is_symbolic(t):
    s = t.strip()
    if not s or CJK_RE.search(s):
        return False
    if re.fullmatch(r"(.)\1{3,}", s):     # 同字符连排碎块：jjjj / ÅÅÅÅ / zzzz
        return True
    if SYM_RE_LATIN.search(s):
        return False
    return bool(SYM_RE_FULL.fullmatch(s))

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
                if len(t) < 90:
                    occ[norm_key(t)].append(t)
        m = {}
        for k, v in occ.items():
            if len(v) < 3: continue
            # R3 护栏：组内各变体数字段数必须一致，否则模板回填会错位 → 交由分块翻译
            if len({len(re.findall(r"\d+", t)) for t in v}) > 1:
                continue
            rep = Counter(v).most_common(1)[0][0]
            rep_ph = ph_all(rep)
            sig = sig_of(rep_ph)
            if k in SKIP:
                continue
            if sig in SIG2ZH:
                zh = SIG2ZH[sig]
            else:
                zh = None
                for rx, wmap in RX_RULES:
                    if rx.match(sig):
                        if wmap is None:       # 人名等：保留原文
                            zh = rep_ph
                        else:
                            zh = rep_ph
                            for w, z in wmap.items():
                                zh = re.sub(rf"\b{re.escape(w)}\b", z, zh)
                        break
            if zh is not None:
                pass
            elif IDENTITY_PREFIXES_RX.match(sig):
                zh = rep_ph
            elif sig in IDENTITY or not re.search(r"[A-Za-z]{2,}", rep_ph) or is_symbolic(rep):
                zh = rep_ph          # 纯数字/符号/单位/方程碎块：保留原文
            else:
                missing.append((dn, sig, rep)); continue
            m[k] = zh
        rec[dn] = m
        print(f"{dn}: {len(m)} 组规范译文")
    json.dump(rec, open(f"{WORK}/recurring.json", "w"), ensure_ascii=False, indent=1)
    # 缺失报告（不阻塞）：语境依赖或待补表，人工裁决后进 SIG2ZH/IDENTITY/SKIP
    with open(f"{WORK}/missing_sigs.txt", "w", encoding="utf-8") as f:
        seen = set()
        for dn, sig, rep in missing:
            if sig in seen: continue
            seen.add(sig)
            f.write(f"{sig}\t{rep[:70]!r}\n")
    print(f"未覆盖签名 {len(seen)} 种 → {WORK}/missing_sigs.txt")
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
            k = norm_key(t)
            if k in rec and len(t) < 90:
                zh = rec[k]
                runs = re.findall(r"\d+", t)
                zh = re.sub(r"⟦N(\d+)⟧", lambda m: runs[int(m.group(1))] if int(m.group(1)) < len(runs) else "", zh)
                out[b["id"]] = zh
    return out

if __name__ == "__main__":
    rec, missing = build_recurring()
    slim_chunks(rec)
