#!/usr/bin/env python3
"""通用 PDF 结构化提取：文本块 + 行级几何 + 旋转 + 表格延续页检测
用法: python3 extract_pdf.py <file.pdf> [more.pdf ...] --workdir .work
输出: <workdir>/extract/<name>.json  结构: {"doc","npages","pages":[{"page","blocks":[...]}]}
块字段: id/page/text/bbox/size/bold/italic/color/align/nlines
        + line_ys/line_x0s/line_ws/line_hs + rot(如旋转) + table_cont_pages(文档级)
"""
import fitz, json, os, re, sys, argparse
from collections import Counter

KEEP_MARKERS = ("This copy of the document",)  # 常见内部水印前缀，可按需扩展

def span_bold(sp):
    return ("Bold" in sp.get("font", "")) or bool(sp.get("flags", 0) & 16)

def extract_one(pdf_path, workdir):
    name = re.sub(r"\.pdf$", "", os.path.basename(pdf_path), flags=re.I)
    doc = fitz.open(pdf_path)
    os.makedirs(os.path.join(workdir, "extract"), exist_ok=True)
    cont_pages = table_continuations(doc)
    pages = []
    for pno in range(len(doc)):
        d = doc[pno].get_text("dict")
        blocks, bi = [], 0
        for b in d["blocks"]:
            if b["type"] != 0: continue
            lines = []
            sizes, colors, bolds, italics = [], [], [], []
            x0 = y0 = 1e9; x1 = y1 = -1e9
            for ln in b["lines"]:
                ltxt = ""
                lx0 = ly0 = 1e9; lx1 = ly1 = -1e9
                for sp in ln["spans"]:
                    if not sp["text"]: continue
                    ltxt += sp["text"]
                    sx0, sy0, sx1, sy1 = sp["bbox"]
                    lx0 = min(lx0, sx0); ly0 = min(ly0, sy0)
                    lx1 = max(lx1, sx1); ly1 = max(ly1, sy1)
                    sizes.append(round(sp["size"], 1)); colors.append(sp["color"])
                    bolds.append(span_bold(sp)); italics.append("Italic" in sp.get("font", ""))
                if ltxt.strip():
                    lines.append({"text": ltxt, "bbox": [lx0, ly0, lx1, ly1]})
                    x0 = min(x0, lx0); y0 = min(y0, ly0)
                    x1 = max(x1, lx1); y1 = max(y1, ly1)
            if not lines: continue
            text = "\n".join(l["text"] for l in lines).strip()
            if not text: continue
            size = Counter(sizes).most_common(1)[0][0]
            color = Counter(colors).most_common(1)[0][0]
            bold = bolds.count(True) > len(bolds) / 2
            italic = italics.count(True) > len(italics) / 2
            cents = [(l["bbox"][0] + l["bbox"][2]) / 2 for l in lines]
            bw = x1 - x0
            align = "l"
            if bw > 20 and max(abs(c - (x0 + x1) / 2) for c in cents) < bw * 0.06:
                align = "c"
            blk = {"id": f"p{pno+1}b{bi}", "page": pno + 1, "text": text,
                   "bbox": [round(v, 1) for v in (x0, y0, x1, y1)],
                   "size": size, "bold": bool(bold), "italic": bool(italic),
                   "color": color, "align": align, "nlines": len(lines),
                   "line_ys": [round(l["bbox"][1], 1) for l in lines],
                   "line_x0s": [round(l["bbox"][0], 1) for l in lines],
                   "line_ws": [round(l["bbox"][2] - l["bbox"][0], 1) for l in lines],
                   "line_hs": [round(l["bbox"][3] - l["bbox"][1], 1) for l in lines]}
            dirs = [tuple(ln["dir"]) for ln in b["lines"]]
            nz = [dd for dd in dirs if dd != (1.0, 0.0)]
            if nz:
                blk["rot"] = 90 if Counter(nz).most_common(1)[0][0] == (0.0, -1.0) else 270
            if any(text.strip().startswith(m) for m in KEEP_MARKERS):
                blk["keep"] = True
            blocks.append(blk); bi += 1
        pages.append({"page": pno + 1, "blocks": blocks})
    out = {"doc": name, "source": os.path.abspath(pdf_path), "npages": len(doc),
           "table_cont_pages": sorted(cont_pages), "pages": pages}
    outp = os.path.join(workdir, "extract", name + ".json")
    json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False)
    nb = sum(len(p["blocks"]) for p in pages)
    print(f"{name}: pages={len(doc)} blocks={nb} table_cont_pages={sorted(cont_pages)} -> {outp}")
    doc.close()

def table_continuations(doc):
    """跨页表格延续页：上页末表格贴底且与本页首表格列几何一致"""
    unsafe = set()
    prev_last = None
    for pno in range(len(doc)):
        try:
            tabs = doc[pno].find_tables()
        except Exception:
            tabs = None
        cur_first = cur_last = None
        if tabs and tabs.tables:
            t0 = tabs.tables[0]
            cur_first = (round(t0.bbox[0]), round(t0.bbox[2]), t0.col_count)
            tl = tabs.tables[-1]
            cur_last = (round(tl.bbox[0]), round(tl.bbox[2]), tl.col_count, tl.bbox[3])
        if prev_last and cur_first and prev_last[3] > 655:
            if prev_last[:3] == cur_first:
                unsafe.add(pno + 1)
        prev_last = cur_last
    return unsafe

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--workdir", default=".work")
    ap.add_argument("--keep-markers", nargs="*", default=list(KEEP_MARKERS),
                    help="保留英文不译的水印前缀")
    a = ap.parse_args()
    if a.keep_markers != list(KEEP_MARKERS):
        KEEP_MARKERS = tuple(a.keep_markers)
    for p in a.pdfs:
        extract_one(p, a.workdir)
