"""列合并块拆分补丁 v3（最终版）
- X_GAP 收紧至 2.0pt
- 父块有效译文 = 分块译文 ∪ 规范译文（规范行结构与源行严格对应，优先）
- 伪块占位符按父块原始数字序列解析（每文档独立索引，无跨文档缓存）
- 拆分/译文写入 extract/*.json + trans/*_cZZ.json
前置：extract/*.json 必须为新鲜父块版（含 line_ys/line_x0s/line_ws/line_hs）
"""
import fitz, json, re, os, glob, sys

import sys as _sys
BASE = _sys.argv[1] if len(_sys.argv) > 1 else "."
DOCS = _sys.argv[2:] if len(_sys.argv) > 2 else ["DOC"]
Y_TOL = 2.5
X_GAP = 2.0

def eff_trans(dn, ext):
    tr = {}
    for f in sorted(glob.glob(f"{BASE}/.work/trans/{dn}_c*.json")):
        if "_cZZ" in f: continue
        tr.update({k: v for k, v in json.load(open(f)).items() if v})
    tr.update(canonical_mod.apply_recurring(dn, ext))
    return tr

def main():
    _fxp = os.path.join(BASE, ".work", "lys_fixmap.json")
    global FIXMAP
    FIXMAP = json.load(open(_fxp, encoding="utf-8")) if os.path.exists(_fxp) else {}
    for dn in DOCS:
        ext = json.load(open(f"{BASE}/.work/extract/{dn}.json"))
        tr = eff_trans(dn, ext)
        doc = fitz.open(f"{BASE}/{dn}.pdf")
        split_trans = {}
        nsplit = 0
        for p in ext["pages"]:
            page = doc[p["page"] - 1]
            page_boxes = []
            for bl in page.get_text("dict")["blocks"]:
                if bl["type"] != 0: continue
                lines = [ln for ln in bl["lines"] if "".join(sp["text"] for sp in ln["spans"]).strip()]
                if not lines: continue
                page_boxes.append([tuple(ln["bbox"]) for ln in lines])
            if len(page_boxes) != len(p["blocks"]):
                print(f"  !! {dn} p{p['page']}: 块数不匹配，跳过该页")
                continue
            newblocks = []
            for bi, b in enumerate(p["blocks"]):
                lb = page_boxes[bi]
                lys = b.get("line_ys")
                if not lys or len(lys) < 2 or len(lb) != len(lys) or b.get("rot"):
                    newblocks.append(b); continue
                rows = []
                for li, bb in enumerate(lb):
                    for r in rows:
                        if abs(r[0][1][1] - bb[1]) <= Y_TOL:
                            r.append((li, bb)); break
                    else:
                        rows.append([(li, bb)])
                colsplit = False
                for r in rows:
                    if len(r) < 2: continue
                    xs = sorted(r, key=lambda t: t[1][0])
                    for a, b2 in zip(xs, xs[1:]):
                        if b2[1][0] - a[1][2] > X_GAP:
                            colsplit = True
                if not colsplit:
                    newblocks.append(b); continue
                zh = tr.get(b["id"])
                if zh is None:
                    newblocks.append(b); continue
                # 行序修复：分块按旧行序翻译，提取件已按 y 升序重排（lys_fixmap）
                try:
                    _fm = FIXMAP.get(dn, {}).get(b["id"])
                    if _fm and "\n" in zh:
                        _o, _p = _fm.get("order") or [], _fm.get("ph") or {}
                        _zl = zh.split("\n")
                        if _o and len(_zl) == len(_o):
                            zh = "\n".join(_zl[i] for i in _o)
                        if _p:
                            zh = re.sub(r"⟦N(\d+)⟧", lambda m: f"⟦N{_p.get(int(m.group(1)), int(m.group(1)))}⟧", zh)
                except Exception:
                    pass
                zlines = zh.split("\n")
                if len(zlines) != len(lys):
                    newblocks.append(b); continue
                src_lines = b["text"].split("\n")
                # 父块数字序列（占位符解析基准）
                parent_runs = re.findall(r"\d+", b["text"].replace("\xa0", " "))
                def sub(m):
                    i = int(m.group(1))
                    return parent_runs[i] if i < len(parent_runs) else ""
                for li, bb in enumerate(lb):
                    x0, y0, x1, y1 = bb
                    txt = src_lines[li] if li < len(src_lines) else ""
                    pb = {"id": f"{b['id']}#{li}", "page": p["page"],
                          "text": txt.replace("\xa0", " "),
                          "bbox": [round(x0,1), round(y0,1), round(x1,1), round(y1,1)],
                          "size": b["size"], "bold": b["bold"], "italic": b.get("italic", False),
                          "color": b["color"], "align": "l", "nlines": 1,
                          "line_ys": [round(y0,1)], "line_x0s": [round(x0,1)],
                          "line_ws": [round(x1-x0,1)], "line_hs": [round(y1-y0,1)]}
                    if b.get("rot"): pb["rot"] = b["rot"]
                    newblocks.append(pb)
                    zl = re.sub(r"⟦N(\d+)⟧", sub, zlines[li].strip())
                    if zl:
                        split_trans[pb["id"]] = zl
                nsplit += 1
            p["blocks"] = newblocks
        json.dump(ext, open(f"{BASE}/.work/extract/{dn}.json", "w"), ensure_ascii=False)
        json.dump(split_trans, open(f"{BASE}/.work/trans/{dn}_cZZ.json", "w"), ensure_ascii=False)
        nph = sum(1 for v in split_trans.values() if "⟦" in v)
        print(f"{dn}: 拆分 {nsplit} 块, 伪块译文 {len(split_trans)} 条, 未解析占位符 {nph}")
        doc.close()

if __name__ == "__main__":
    import os as _os
    _d = _os.path.dirname(_os.path.abspath(__file__))
    _sys.path.insert(0, _d)
    import canonical as canonical_mod
    canonical_mod.WORK = BASE + "/.work" if _os.path.isdir(BASE + "/.work") else BASE
    main()
