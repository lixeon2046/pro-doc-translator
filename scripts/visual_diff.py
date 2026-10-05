"""截图对比（验收证据生成）：源/成品页并排合成 + 复杂版式页自动挑选 + 局部放大。

用途（qa-protocol.md「截图对比验收」）：
  - 复杂公式页与大型表格页为**必抽页**（QA 通过不等于版式可读，需像素级对照）
  - 产出 中英并排 PNG 交视觉验收代理逐页裁决；关键区域可再放大

用法:
  python visual_diff.py <src.pdf> <out.pdf> [--pages 722 497] [--auto 4] [--dpi 110]
      [--crop PAGE:X0,Y0,X1,Y1 ...] [--workdir .work] [--tag TAG]
输出:
  .work/visual_diff/<tag>/pNNN_pair.png        整页并排（左源右成品）
  .work/visual_diff/<tag>/pNNN_crop_Z.png      局部放大（在整页图上标注区域）
  控制台打印 auto 模式挑选的页码与理由
"""
import sys, os, re, argparse
import pymupdf


def auto_pick(src, k=4):
    """挑复杂版式页：矢量图元 + 图片数 + 行密度加权最高（公式/大表聚集页）。"""
    scores = []
    for i in range(src.page_count):
        p = src[i]
        draws = len(p.get_drawings())
        imgs = len(p.get_images(full=True))
        d = p.get_text("dict")
        short_lines = sum(1 for b in d["blocks"] if b["type"] == 0
                          for l in b["lines"] if len("".join(s["text"] for s in l["spans"]).strip()) <= 12)
        scores.append((draws * 2 + imgs * 3 + short_lines, i + 1))
    scores.sort(reverse=True)
    picked, seen = [], []
    for sc, pno in scores:
        if sc <= 0:
            break
        if any(abs(pno - s) <= 2 for s in seen):
            continue
        picked.append((pno, sc))
        seen.append(pno)
        if len(picked) >= k:
            break
    return picked


def pair_image(src_pdf, out_pdf, pno, dpi, path, label_gap=8):
    a, b = pymupdf.open(src_pdf), pymupdf.open(out_pdf)
    pa, pb = a[pno - 1], b[pno - 1]
    ia = pa.get_pixmap(dpi=dpi)
    ib = pb.get_pixmap(dpi=dpi)
    h = max(ia.height, ib.height)
    canvas = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, ia.width + label_gap + ib.width, h))
    canvas.clear_with(255)
    canvas.copy(ia, pymupdf.IRect(0, 0, ia.width, ia.height))
    canvas.copy(ib, pymupdf.IRect(ia.width + label_gap, 0,
                                  ia.width + label_gap + ib.width, ib.height))
    canvas.save(path)
    a.close(); b.close()


def crop_zoom(pdf, pno, rect, dpi, path):
    d = pymupdf.open(pdf)
    pix = d[pno - 1].get_pixmap(dpi=dpi, clip=pymupdf.Rect(*rect))
    pix.save(path)
    d.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--pages", nargs="*", type=int, default=[])
    ap.add_argument("--auto", type=int, default=0, help="自动挑选复杂版式页数")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--zoom-dpi", type=int, default=200)
    ap.add_argument("--crop", nargs="*", default=[],
                    help="PAGE:X0,Y0,X1,Y1（pt，相对该页）")
    ap.add_argument("--workdir", default=".work")
    ap.add_argument("--tag", default="")
    ns = ap.parse_args()

    tag = ns.tag or (os.path.splitext(os.path.basename(ns.out))[0][:24] or "diff")
    outdir = os.path.join(ns.workdir, "visual_diff", tag)
    os.makedirs(outdir, exist_ok=True)

    pages = list(ns.pages)
    if ns.auto:
        picked = auto_pick(pymupdf.open(ns.src), ns.auto)
        pages += [p for p, _ in picked]
        print("auto 挑选（复杂版式页）:", ", ".join(f"p{p}(score {s})" for p, s in picked))

    for pno in sorted(set(pages)):
        path = os.path.join(outdir, f"p{pno:03d}_pair.png")
        pair_image(ns.src, ns.out, pno, ns.dpi, path)
        print("pair ->", path)

    for spec in ns.crop:
        m = re.match(r"(\d+):([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)", spec)
        if not m:
            print("!! crop 格式应为 PAGE:X0,Y0,X1,Y1:", spec); continue
        pno = int(m.group(1))
        rect = tuple(float(m.group(i)) for i in range(2, 6))
        path = os.path.join(outdir, f"p{pno:03d}_crop_{len(os.listdir(outdir))}.png")
        crop_zoom(ns.out, pno, rect, ns.zoom_dpi, path)
        print("crop ->", path)
    print(f"共 {len(set(pages))} 组并排图，目录 {outdir}")


if __name__ == "__main__":
    main()
