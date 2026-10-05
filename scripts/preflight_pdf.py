"""PDF 健康预检（阶段 0.5）：在提取与开工前暴露源文件地雷。

检查项（对应 pdf-layout-engine.md「四类源 PDF 陷阱」）：
  1. 文本层覆盖（原生 vs 扫描版）
  2. MediaBox / CropBox 不一致（TextWriter 坐标错位陷阱）
  3. 内容流 q/Q 配平（悬挂 CTM → 整体位移陷阱）
  4. 非 ASCII 字符审计（连字置换陷阱：ðÞ=括号、Ɵ=ti、ﬁ=fi 等）
  5. 疑似 Logo 字体（字形型徽标，红框脱字即永久丢失）
  6. 水印候选（跨页高频短文本 / 旋转文本，供"去除必要的水印"决策）
  7. 页面几何与旋转

用法: python preflight_pdf.py <pdf> [pdf2 ...] [--workdir .work]
输出: 控制台摘要 + .work/preflight/<name>.json（供主控读取决策）
"""
import sys, os, re, json, zlib
from collections import Counter, defaultdict

import pymupdf

SUSPECT_LIG = {  # 已知字体编码置换（可按领域扩充）
    "\u00F0": "(", "\u00DE": ")", "\u019F": "ti", "\uFB01": "fi", "\uFB02": "fl",
    "\uFB00": "ff", "\uFB03": "ffi", "\uFB04": "ffl", "\u00AD": "",
}
WM_HINT = re.compile(r"(www\.|http|\.com|\.cn|\.net|免费下载|水印|扫描件|仅供|内部资料)", re.I)


def check_textlayer(doc, sample=40):
    step = max(1, doc.page_count // sample)
    empty = sum(1 for i in range(0, doc.page_count, step)
                if len(doc[i].get_text().strip()) < 20)
    n = len(range(0, doc.page_count, step))
    return {"sampled": n, "empty": empty,
            "verdict": "SCANNED-OCR-REQUIRED" if empty > n * 0.5 else
                       ("MIXED" if empty else "native-ok")}


def check_boxes(doc):
    bad = []
    for i, p in enumerate(doc):
        mb, cb = p.mediabox, p.cropbox
        if abs(mb.width - cb.width) > 0.5 or abs(mb.height - cb.height) > 0.5 \
           or abs(mb.x0 - cb.x0) > 0.5 or abs(mb.y0 - cb.y0) > 0.5:
            bad.append({"page": i + 1, "mediabox": [mb.x0, mb.y0, mb.x1, mb.y1],
                        "cropbox": [cb.x0, cb.y0, cb.x1, cb.y1]})
    return {"pages_affected": len(bad), "samples": bad[:5],
            "verdict": "MISMATCH-TextWriter-needs-offset" if bad else "ok"}


def check_ctm(doc, sample=30):
    """内容流 q/Q 计数配平（启发式）。悬挂数与位移強相关。"""
    step = max(1, doc.page_count // sample)
    bad = []
    for i in range(0, doc.page_count, step):
        try:
            raw = doc[i].read_contents()
            q = len(re.findall(rb"(?:^|[\s>\]])q(?=[\s<\[]|$)", raw))
            Q = len(re.findall(rb"(?:^|[\s>\]])Q(?=[\s<\[]|$)", raw))
            if q != Q:
                bad.append({"page": i + 1, "q": q, "Q": Q, "dangling": q - Q})
        except Exception:
            pass
    return {"pages_affected": len(bad), "samples": bad[:5],
            "verdict": "DANGLING-CTM-clean_contents-required" if bad else "ok"}


def check_ligatures(doc, sample=60):
    step = max(1, doc.page_count // sample)
    cnt = Counter()
    for i in range(0, doc.page_count, step):
        for ch, _ in SUSPECT_LIG.items():
            n = doc[i].get_text().count(ch)
            if n:
                cnt[ch] += n
    hits = {f"U+{ord(k):04X} {k!r}->{v}": n for k, v, in
            [(k, SUSPECT_LIG[k], ) for k in cnt] for n in [cnt[k]]}
    return {"suspect_chars": {f"U+{ord(k):04X} {k!r}": c for k, c in cnt.most_common()},
            "verdict": "LIGATURE-SUBSTITUTION-normalization-required" if cnt else "ok"}


def check_logo_fonts(doc):
    """Type3 / 名字含 Logo·Symbol 的字体：常用于字形型徽标，脱字即毁。"""
    sus = set()
    for i in range(doc.page_count):
        for f in doc[i].get_fonts(full=True):
            xref, ext, ftype, name = f[0], f[1], f[2], f[3]
            if ftype == "Type3" or re.search(r"logo|brand|mark", name, re.I):
                sus.add(f"{name} ({ftype}, page {i+1})")
    return {"suspect_fonts": sorted(sus)[:10],
            "verdict": "GLYPH-LOGO-keep-blocks-untouched" if sus else "ok"}


def check_watermarks(doc, min_pages_frac=0.08):
    """水印候选：跨页高频短文本（URL/站点/口号类），含旋转文本带。"""
    occ = defaultdict(Counter)
    rot = Counter()
    for i, p in enumerate(doc):
        d = p.get_text("dict")
        for b in d["blocks"]:
            if b["type"] != 0:
                continue
            for l in b["lines"]:
                if l["dir"] not in ((1.0, 0.0),):
                    for s in l["spans"]:
                        if s["text"].strip():
                            rot[s["text"].strip()[:40]] += 1
                for s in l["spans"]:
                    t = s["text"].strip()
                    if 3 < len(t) < 80:
                        key = re.sub(r"\d+", "#", t)
                        occ[key][t] += 1
    total = doc.page_count
    cands = []
    for key, c in occ.items():
        rep, n = c.most_common(1)[0]
        if n >= max(5, total * min_pages_frac) and WM_HINT.search(rep):
            cands.append({"text": rep[:60], "pages": n,
                          "frac": round(n / total, 2)})
    cands.sort(key=lambda c: -c["pages"])
    rotc = [{"text": t, "count": n} for t, n in rot.most_common(5) if n >= 10]
    return {"candidates": cands[:10], "rotated_text_top": rotc,
            "verdict": "WATERMARK-CANDIDATES-FOUND" if cands else "ok"}


def run(pdf):
    doc = pymupdf.open(pdf)
    rep = {
        "file": os.path.basename(pdf),
        "pages": doc.page_count,
        "page_size": [round(doc[0].rect.width), round(doc[0].rect.height)],
        "rotation": doc[0].rotation,
        "text_layer": check_textlayer(doc),
        "boxes": check_boxes(doc),
        "ctm": check_ctm(doc),
        "ligatures": check_ligatures(doc),
        "logo_fonts": check_logo_fonts(doc),
        "watermarks": check_watermarks(doc),
    }
    doc.close()
    return rep


def summarize(rep):
    flags = []
    for k in ["text_layer", "boxes", "ctm", "ligatures", "logo_fonts", "watermarks"]:
        v = rep[k]["verdict"]
        if v != "ok":
            flags.append(f"{k}={v}")
    print(f"== {rep['file']}: {rep['pages']}p {rep['page_size'][0]}x{rep['page_size'][1]}"
          f" rot{rep['rotation']} | " + ("; ".join(flags) if flags else "ALL-CLEAR"))
    if rep["ligatures"]["suspect_chars"]:
        print("   连字置换:", rep["ligatures"]["suspect_chars"])
    if rep["watermarks"]["candidates"]:
        for c in rep["watermarks"]["candidates"][:5]:
            print(f"   水印候选: {c['pages']}p ({c['frac']:.0%}) {c['text']!r}")
    if rep["boxes"]["pages_affected"]:
        print(f"   MediaBox≠CropBox: {rep['boxes']['pages_affected']} 页 → Pen 需偏移补偿")
    if rep["ctm"]["pages_affected"]:
        print(f"   内容流悬挂 CTM: {rep['ctm']['pages_affected']} 页 → clean_contents 必需")


if __name__ == "__main__":
    args, workdir = [], ".work"
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--workdir":
            workdir = argv[i + 1]; i += 2
        else:
            args.append(argv[i]); i += 1
    os.makedirs(os.path.join(workdir, "preflight"), exist_ok=True)
    for pdf in args:
        rep = run(pdf)
        summarize(rep)
        out = os.path.join(workdir, "preflight",
                           os.path.splitext(os.path.basename(pdf))[0] + ".json")
        json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"   -> {out}")
