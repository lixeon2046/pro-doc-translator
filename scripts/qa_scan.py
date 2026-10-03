#!/usr/bin/env python3
"""输出 PDF 质量扫描：越界 / 占位符残留 / 微字 / 页脚页码 / 叠印 / 残留源语言
用法: python3 qa_scan.py <file.pdf> [--src <原文件.pdf>] [--margin 566] [--minfs 4.5]
      [--allow-re "正则白名单"] [--footer-clip 500,735,570,755 --footer-re "第\\s*\\d+\\s*页"]
      [--cjk-only]  # 仅检查含CJK的span（翻译到中文时用）
"""
import fitz, re, sys, argparse
from collections import Counter

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--src")
    ap.add_argument("--margin", type=float, default=566)
    ap.add_argument("--minfs", type=float, default=4.5)
    ap.add_argument("--allow-re", action="append", default=[])
    ap.add_argument("--footer-clip", default=None)
    ap.add_argument("--footer-re", default=r"第\s*\d+\s*页")
    ap.add_argument("--cjk-only", action="store_true")
    a = ap.parse_args()
    CJK = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")
    allow = [re.compile(p) for p in a.allow_re]
    d = fitz.open(a.pdf)
    ov = ph = tiny = ovl = foot_bad = 0
    samples = {"ov": [], "ph": [], "tiny": [], "ovl": []}
    fc = [float(v) for v in a.footer_clip.split(",")] if a.footer_clip else None
    for pno in range(len(d)):
        if fc and pno > 1:
            foot = d[pno].get_text("text", clip=fitz.Rect(*fc)).strip()
            if foot and CJK.search(foot) and not re.search(a.footer_re, foot):
                foot_bad += 1
        spans = []
        for bl in d[pno].get_text("dict")["blocks"]:
            if bl["type"] != 0: continue
            for ln in bl["lines"]:
                x0, y0, x1, y1 = ln["bbox"]
                txt = "".join(sp["text"] for sp in ln["spans"]).strip()
                if x1 > a.margin and x0 < a.margin + 10:
                    if not any(p.search(txt) for p in allow):
                        ov += 1
                        if len(samples["ov"]) < 5: samples["ov"].append((pno+1, round(x1), txt[:50]))
                if "⟦" in txt:
                    ph += 1
                    if len(samples["ph"]) < 5: samples["ph"].append((pno+1, txt[:50]))
                for sp in ln["spans"]:
                    if a.cjk_only and not CJK.search(sp["text"]): continue
                    if sp["size"] < a.minfs and CJK.search(sp["text"]) and len(sp["text"].strip()) > 1:
                        tiny += 1
                        if len(samples["tiny"]) < 5: samples["tiny"].append((pno+1, round(sp["size"],1), sp["text"][:30]))
                    if CJK.search(sp["text"]) and len(sp["text"].strip()) > 1:
                        spans.append((fitz.Rect(sp["bbox"]), sp["text"]))
        for i in range(len(spans)):
            for j in range(i+1, len(spans)):
                if spans[i][1] == spans[j][1]: continue  # 伪粗体双绘
                r = fitz.Rect(spans[i][0]); r.intersect(spans[j][0])
                if r.is_valid and r.width > 2 and r.height > 2:
                    ovl += 1
                    if len(samples["ovl"]) < 5: samples["ovl"].append((pno+1, spans[i][1][:15], spans[j][1][:15]))
    d.close()
    print(f"越界{ov} 占位符{ph} 微字{tiny} 叠印{ovl} 页脚缺页码{foot_bad}")
    for k, v in samples.items():
        for s in v: print(f"  {k}: {s}")
    sys.exit(0 if (ov == ph == tiny == ovl == foot_bad == 0) else 1)

if __name__ == "__main__":
    main()
