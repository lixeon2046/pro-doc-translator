#!/usr/bin/env python3
"""表格单元格覆盖率：源表格含源语言文字的单元格，在输出同位置必须检出目标语言
用法: python3 tables_coverage.py <src.pdf> <out.pdf> [--tol 7] [--min-latin 2]
"""
import fitz, re, sys, argparse

def cell_text(page, rect):
    r = fitz.Rect(rect)
    if r.is_empty or r.width <= 1 or r.height <= 1: return ""
    return " ".join(page.get_text("text", clip=r).split())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--tol", type=float, default=7)
    ap.add_argument("--min-latin", type=int, default=2, help="单元格最少源语言词长")
    a = ap.parse_args()
    src = fitz.open(a.src); out = fitz.open(a.out)
    ncell = miss = 0
    issues = []
    for pno in range(len(src)):
        try:
            tabs = src[pno].find_tables()
        except Exception:
            continue
        if not tabs.tables: continue
        for t in tabs.tables:
            for row in t.rows:
                for c in row.cells:
                    if c is None: continue
                    en = cell_text(src[pno], c)
                    if len(re.findall(r"[A-Za-z]{3,}", en)) < a.min_latin: continue
                    ncell += 1
                    zh = cell_text(out[pno], c) or cell_text(out[pno], fitz.Rect(c) + (-a.tol, -a.tol, a.tol, a.tol))
                    if not re.search(r"[\u4e00-\u9fff]", zh):
                        miss += 1
                        issues.append({"page": pno+1, "en": en[:60]})
    src.close(); out.close()
    print(f"检查单元格 {ncell}，缺失 {miss}")
    for x in issues[:12]: print("   p%d | %s" % (x["page"], x["en"]))
    # 退出码：缺失率 >5% 报警（剩余常为应保留的标准代号，需人工/代理裁决）
    sys.exit(0 if ncell == 0 or miss / ncell <= 0.05 else 1)

if __name__ == "__main__":
    main()
