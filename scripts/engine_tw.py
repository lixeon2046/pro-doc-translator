"""专业文档 PDF 版式还原引擎 v2（TextWriter 绘制层）
v2 关键变更：绘制统一走 TextWriter（与 Font.text_length 度量完全一致），
修复 v1 中 insert_text 渲染宽度 ≈1.39× 预测值导致的系统性越界。
"""
import fitz, json, re, os
from collections import Counter

F = fitz.Font("china-s")
ASC, DESC = F.ascender, F.descender

def to_rgb(c):
    if isinstance(c, (tuple, list)):
        return c
    return ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255)

def tw(s, fs):
    return F.text_length(s, fontsize=fs)

def wrap(paras, width, fs):
    """CJK 按字、拉丁按词的贪心折行（宽度度量与 TextWriter 一致）+ 行首禁则回退"""
    lines = []
    for para in paras:
        if not para.strip():
            lines.append(""); continue
        cur = ""
        for tok in re.split(r"(\s+)", para):
            i = 0
            while i < len(tok):
                ch = tok[i]
                if re.match(r"[A-Za-z0-9@./%°§\[\]()\-+–—':;,_^<>«»×·≥≤=≈]", ch):
                    j = i
                    while j < len(tok) and re.match(r"[A-Za-z0-9@./%°§\[\]()\-+–—':;,_^<>«»×·≥≤=≈]", tok[j]):
                        j += 1
                    word = tok[i:j]; i = j
                    if tw(cur + word, fs) > width and cur:
                        lines.append(cur.rstrip()); cur = word.lstrip()
                    else:
                        cur += word
                else:
                    seg = ch; i += 1
                    if tw(cur + seg, fs) > width and cur.strip():
                        lines.append(cur.rstrip()); cur = seg
                    else:
                        cur += seg
        lines.append(cur.rstrip())
    # CJK 行首禁则：闭式标点不得起行 → 回退到上一行行尾（允许 ~1 字宽越界）
    NO_START = "，。、；：？！”’』」〉》】〕〕·…—–-．％‰℃°×"
    for i in range(1, len(lines)):
        ln = lines[i]
        while ln and ln[0] in NO_START and lines[i-1]:
            lines[i-1] += ln[0]
            ln = ln[1:]
        lines[i] = ln
    return [ln for ln in lines if ln != "" or True]

def restore_digits(zh, orig):
    runs = re.findall(r"\d+", orig)
    def sub(m):
        i = int(m.group(1))
        return runs[i] if i < len(runs) else m.group(0)
    return re.sub(r"⟦N(\d+)⟧", sub, zh)

def layout_lines(zh, b, pad=1.2):
    """返回 (lines, fontsize, lineheight)"""
    x0, y0, x1, y1 = b["bbox"]
    width = x1 - x0 - 2 * pad
    orig_h = y1 - y0
    lh0 = orig_h / b["nlines"] if b["nlines"] > 1 else b["size"] * 1.30
    fs = b["size"]
    minfs = max(4.6, b["size"] * 0.55)
    while True:
        lines = wrap(zh.split("\n"), width, fs)
        # 单行源块：适度缩字号排成一行（下限4.7，再放不下转两行）
        if b["nlines"] == 1 and len(lines) > 1 and len(zh) <= 60:
            trial = fs
            if width > 300:
                floor1 = max(4.7, b["size"] * 0.78)
            elif width < 60:
                floor1 = 4.2        # 微型表格单元格：宁可缩至 4.2pt 也要保单行
            else:
                floor1 = 4.7
            while trial > floor1 and len(wrap(zh.split("\n"), width, trial)) > 1:
                trial -= 0.25
            if len(wrap(zh.split("\n"), width, trial)) == 1:
                return wrap(zh.split("\n"), width, trial), trial, max(trial * 1.22, min(lh0, trial * 1.45))
        lh = max(fs * 1.22, min(lh0, fs * 1.45))
        if b["nlines"] >= 3 and len(lines) < b["nlines"] and len(lines) > 1 and not _para_like(b):
            lh = min(max(lh, orig_h / len(lines)), fs * 2.2)
        total = len(lines) * lh
        tol = 2.0 if (b["nlines"] == 1 and len(lines) == 1) else 0.0
        if total <= orig_h + tol or fs <= minfs:
            return lines, fs, lh
        fs -= 0.25
        if fs < minfs: fs = minfs

def _para_like(b):
    lws = b.get("line_ws")
    if not lws or len(lws) < 3:
        return False
    bw = b["bbox"][2] - b["bbox"][0]
    full = sum(1 for w in lws[:-1] if w > bw * 0.82)
    return full >= max(1, int((len(lws) - 1) * 0.7))

class Pen:
    """按块缓存 TextWriter；页内按颜色分组落色；含 CropBox 偏移补偿"""
    def __init__(self, page):
        self.page = page
        self.writers = {}   # color_key -> [TextWriter, n]
        self.rot = []       # (text, point, fs, morph_matrix, color)
        off = page.cropbox_position
        self.ox, self.oy = float(off.x or 0), float(off.y or 0)
        # TextWriter 以 MediaBox 空间解释坐标，渲染/取文以 CropBox 空间：
        # 当 MediaBox 高于 CropBox（如 CD-ROM 方形封面 612x612 裁自 612x792），需减去差值
        self.ox += float(page.mediabox.x0 - page.cropbox.x0)
        self.oy += float(page.mediabox.y1 - page.cropbox.y1)
    def _key(self, color):
        return tuple(round(c, 3) for c in to_rgb(color))
    def add(self, x, y, s, fs, bold=False, color=(0, 0, 0)):
        if not s: return
        key = self._key(color)
        if key not in self.writers:
            self.writers[key] = [fitz.TextWriter(self.page.rect), 0]
        w = self.writers[key][0]
        w.append((x - self.ox, y - self.oy), s, font=F, fontsize=fs)
        if bold:
            w.append((x - self.ox + 0.28, y - self.oy + 0.05), s, font=F, fontsize=fs)
        self.writers[key][1] += 1
    def add_rot(self, x, y, s, fs, rot, bold=False, color=(0, 0, 0)):
        if not s: return
        m = fitz.Matrix(rot)
        self.rot.append((s, fitz.Point(x - self.ox, y - self.oy), fs, m, color))
    def flush(self, color=None):
        for key, (w, n) in self.writers.items():
            if n:
                w.write_text(self.page, color=key)
        for s, p, fs, m, c in self.rot:
            w = fitz.TextWriter(self.page.rect)
            w.append(p, s, font=F, fontsize=fs)
            w.write_text(self.page, color=to_rgb(c), morph=(p, m))

def bc(b):
    return to_rgb(b.get("color", 0))

def insert_normal(page, b, zh, pen):
    x0, y0, x1, y1 = b["bbox"]
    lines, fs, lh = layout_lines(zh, b)
    pad = 1.2
    width = x1 - x0 - 2 * pad
    boxh = y1 - y0
    total = len(lines) * lh
    lys = b.get("line_ys")
    lws = b.get("line_ws")
    nsrc = b["nlines"]

    if lys and len(lines) == nsrc:
        hs = b.get("line_hs") or [fs * 1.2] * nsrc
        lx0s = b.get("line_x0s")
        for i, ln in enumerate(lines):
            if not ln: continue
            w = tw(ln, fs)
            row_h = (lys[i+1] - lys[i]) if i + 1 < nsrc else max(hs[min(i, len(hs)-1)], fs * 1.2)
            if row_h < fs * 0.9:
                # 同行多列碎块（相邻行 y 相同/近，如分数上下片、表格双列）：用行自身高度，
                # 避免被 (row_h-fs)/2 项垂直抬升成假上标
                row_h = max(hs[min(i, len(hs)-1)], fs * 1.2)
            if b["align"] == "r":
                x = x1 - pad - w
            elif b["align"] == "c":
                src_c = x0 + (lws[i] / 2 if lws and i < len(lws) else width / 2)
                x = src_c - w / 2
            else:
                # 行级 x0：源行可能位于块内不同列（表格列合并块），从各自列起点起画
                x = (lx0s[i] if lx0s and i < len(lx0s) else x0) + pad
            pen.add(x, lys[i] + (row_h - fs) / 2 + ASC * fs, ln, fs, b["bold"], bc(b))
        return

    if lys and nsrc >= 3 and 1 < len(lines) < nsrc and not _para_like(b):
        lx0s = b.get("line_x0s") or []
        draw_x0 = Counter(lx0s).most_common(1)[0][0] if lx0s else x0
        if draw_x0 + 20 > x1:  # 众数异常时回退块 x0
            draw_x0 = x0
        span0, span1 = lys[0], lys[-1] + (b.get("line_hs") or [boxh / nsrc])[-1]
        # 从 draw_x0 起排：按收窄后的宽度重排并按高度收缩
        w2 = x1 - draw_x0 - 2 * pad
        minfs = max(4.6, b["size"] * 0.55)
        while True:
            lines = wrap(zh.split("\n"), w2, fs)
            lh2 = min(max(fs * 1.22, (span1 - span0) / max(1, len(lines))), fs * 2.4)
            if len(lines) * lh2 <= (span1 - span0) + 3 or fs <= minfs:
                break
            fs -= 0.25
        lh2 = min(max(fs * 1.22, (span1 - span0) / max(1, len(lines))), fs * 2.4)
        yy = span0 + (lh2 - fs) / 2 + ASC * fs
        for ln in lines:
            if not ln: yy += lh2; continue
            w = tw(ln, fs)
            if b["align"] == "c":
                x = draw_x0 + pad + max(0, (width - w) / 2)
            elif b["align"] == "r":
                x = x1 - pad - w
            else:
                x = draw_x0 + pad
            pen.add(x, yy, ln, fs, b["bold"], bc(b))
            yy += lh2
        return

    lx0s = b.get("line_x0s") or []
    draw_x0 = x0
    if lx0s and len(lines) < nsrc:
        cand = Counter(lx0s).most_common(1)[0][0]
        if cand > x0 + 4 and cand + 20 < x1:
            draw_x0 = cand
            w2 = x1 - draw_x0 - 2 * pad
            minfs = max(4.6, b["size"] * 0.55)
            while True:
                lines = wrap(zh.split("\n"), w2, fs)
                if len(lines) * lh <= boxh + 2 or fs <= minfs:
                    break
                fs -= 0.25
            lh = fs * 1.24
    if nsrc == 1 and len(lines) == 1:
        top = y0 + (boxh - total) / 2
    else:
        top = y0 + max(0, min(1.0, (boxh - total) / 2))
    y = top + (lh - fs) / 2 + ASC * fs
    for ln in lines:
        if not ln: y += lh; continue
        w = tw(ln, fs)
        if b["align"] == "c":
            x = draw_x0 + pad + max(0, (width - w) / 2)
        elif b["align"] == "r":
            x = x1 - pad - w
        else:
            x = draw_x0 + pad
        pen.add(x, y, ln, fs, b["bold"], bc(b))
        y += lh

def insert_rot(page, b, zh, pen):
    x0, y0, x1, y1 = b["bbox"]
    lys = b.get("line_ys") or []
    lhs = b.get("line_hs") or []
    x0s = b.get("line_x0s") or []
    zh_lines = zh.split("\n")
    rot = b["rot"]

    # 逐行锚定模式：旋转表格的行=竖排单元格，各有独立起点与跨度（line_ys/line_hs/line_x0s）。
    # 短标签（表头词组）在源行跨度内【居中】——中文更短时底锚会产生阶梯漂移；
    # 长文本（L ≥ 72% 跨度，如通栏表题/整段注释）保持端部锚定（原版排布）；
    # 跨行溢出（厚度范围行等）随之对称分布。
    if len(lys) == len(zh_lines) and len(lys) >= 1:
        for i, raw in enumerate(zh_lines):
            if not raw.strip():
                continue
            span = lhs[i] if i < len(lhs) else (y1 - y0)
            strip_x = x0s[i] if i < len(x0s) else x0
            strip_w = max(4.0, (x1 - x0) - (strip_x - x0))
            fs = max(4.6, min(b["size"], strip_w * 0.95))
            L = tw(raw, fs)
            if rot == 90:
                anchor = (lys[i] + span - 1.0) if L >= span * 0.72 else \
                         (lys[i] + span / 2 + L / 2 - fs * 0.18)
                xc = strip_x + strip_w / 2 - fs * 0.4
                pen.add_rot(xc, anchor, raw, fs, 90, b["bold"], bc(b))
            else:
                anchor = (lys[i] + 1.0) if L >= span * 0.72 else \
                         (lys[i] + span / 2 - L / 2 + fs * 0.85)
                xc = strip_x + strip_w / 2 - fs * 0.4
                pen.add_rot(xc, anchor, raw, fs, 270, b["bold"], bc(b))
        return

    # 堆叠模式（散文段/行数不匹配）：真折行多行——行沿 x 推进，装回块宽
    lines = wrap(zh_lines, (y1 - y0) - 2, min(b["size"], max(5.0, (x1 - x0) * 0.72)))
    fs0 = min(b["size"], max(5.0, (x1 - x0) * 0.72))
    lh = fs0 * 1.22
    if len(lines) > 1:
        fit_fs = (x1 - x0) / len(lines) * 0.95
        if fit_fs < fs0:
            fs0 = max(4.6, fit_fs)
        lh = min(lh, (x1 - x0) / len(lines))
    for i, ln in enumerate(lines):
        if rot == 90:
            pen.add_rot(x1 - 0.8 - i * lh, y1 - 1.0, ln, fs0, 90, b["bold"], bc(b))
        else:
            pen.add_rot(x0 + 0.8 + i * lh, y0 + 1.0, ln, fs0, 270, b["bold"], bc(b))

PMARK = re.compile(r"⟦P(\d+)⟧")

SYMBOL_RE = re.compile(r"[\d\s.,\-–—°×/%≥≤<>+=()^\[\]{}|±·∙∕'\"^~:;?!*&#$_A-Za-zÅÄÅÉÈÑÖÜαβγδεθλμπσΔΩ≈≡—–‘’“”]*")

def is_symbolic(t):
    """方程碎块/纯符号块（无>=4字母拉丁词、无CJK）→ 无译文时保留原样重绘"""
    s = t.strip()
    if not s or re.search(r"[\u4e00-\u9fff]", s):
        return False
    if re.search(r"[A-Za-z]{4,}", s):
        return False
    return bool(SYMBOL_RE.fullmatch(s))

def insert_toc(page, b, zh, pen):
    x0, y0, x1, y1 = b["bbox"]
    fs = b["size"]
    lh = (y1 - y0) / max(1, b["nlines"])
    y = y0 + (lh - fs) / 2 + ASC * fs
    for raw in zh.split("\n"):
        m = PMARK.search(raw)
        num = None
        if m:
            num = m.group(1)
            raw = raw[:m.start()].rstrip()
        segs = wrap([raw], x1 - x0 - 4, fs) if raw else [""]
        for si, seg in enumerate(segs):
            last = (si == len(segs) - 1)
            pen.add(x0, y, seg, fs, b["bold"], bc(b))
            if last and num is not None:
                nw = tw(num, fs)
                nx = x1 - nw
                sx = min(x0 + tw(seg, fs) + 3, nx - 2)
                n = max(0, int((nx - 3 - sx) / tw(".", fs)))
                dots = "." * n
                if dots:
                    pen.add(sx, y, dots, fs, False, bc(b))
                pen.add(nx, y, num, fs, b["bold"], bc(b))
            y += lh

def is_toc(b, zh):
    return bool(PMARK.search(zh))

def build(doc_name, trans, out_path, keep_prefix="This copy of the document", extract_path=None, pdf_path=None, drop_prefixes=()):
    """trans: {block_id: 中文 or None}
    keep_prefix:   命中前缀的块保留原文不译（内部标记/水印保留类）
    drop_prefixes: 命中前缀的块只脱字不回填（去除必要的水印）"""
    data = json.load(open(extract_path or f".work/extract/{doc_name}.json"))
    doc = fitz.open(pdf_path or (doc_name + ".pdf"))
    stats = {"redrawn": 0, "kept": 0, "hl": 0, "shrunk": 0}
    for p in data["pages"]:
        page = doc[p["page"] - 1]
        # 内容流平衡化：老 PDF（如 CD-ROM 封面）可能悬挂 CTM，追加文本会继承残留变换而整体错位
        try:
            page.clean_contents()
        except Exception:
            pass
        blocks = p["blocks"]
        # 表格单元格边界：用于将窄块 bbox 扩展到所在单元格全宽
        try:
            cell_rects = []
            for t in page.find_tables().tables:
                for row in t.rows:
                    for c in row.cells:
                        if c is not None and c.width > 20 and c.height > 6:
                            cell_rects.append(fitz.Rect(c))
        except Exception:
            cell_rects = []
        todo = []
        for b in blocks:
            if b["text"].strip().startswith(keep_prefix):
                stats["kept"] += 1
                continue
            if drop_prefixes and b["text"].strip().startswith(tuple(drop_prefixes)):
                r = fitz.Rect(b["bbox"]) + (-0.5, -0.5, 0.5, 0.5)
                page.add_redact_annot(r, fill=False)
                stats["redrawn"] += 1
                continue
            zh = trans.get(b["id"], None)
            if zh is None and (re.fullmatch(r"[\d\s.,\-–—°×/%≥≤<>+=()^\[\]]+", b["text"].strip() or "x")
                               or is_symbolic(b["text"])):
                zh = b["text"].strip()   # 纯数字/方程符号碎块：原样绘制
            if zh is None:
                stats["hl"] += 1
                continue
            if zh == "__DROP__":
                r = fitz.Rect(b["bbox"]) + (-0.5, -0.5, 0.5, 0.5)
                page.add_redact_annot(r, fill=False)
                stats["redrawn"] += 1
                continue
            zh = restore_digits(zh, b["text"])
            if re.search(r"⟦N\d", zh):
                stats["hl"] += 1
                continue
            if b["nlines"] == 1 and "\n" in zh:
                zh = " ".join(zh.split("\n"))   # 单行源块：展平译文强制换行
            # 宽单行块且译文放不下：向下借 9pt 走两行，避免缩到不可辨
            if b["nlines"] == 1 and (b["bbox"][2] - b["bbox"][0]) > 300:
                w = b["bbox"][2] - b["bbox"][0] - 2.4
                if tw(zh, b["size"]) > w * 1.03:
                    b["bbox"][3] += 9
            b["_zh"] = zh
            # 窄块扩展到所在单元格全宽（仅单行块，避免误扩展段落）
            if b["nlines"] == 1 and cell_rects:
                bb = fitz.Rect(b["bbox"])
                for cr in cell_rects:
                    if cr.x0 - 2 <= bb.x0 and bb.x1 <= cr.x1 + 2 and cr.y0 - 2 <= bb.y0 and bb.y1 <= cr.y1 + 2:
                        if cr.x1 - 2 > bb.x1 + 3 or cr.x0 + 2 < bb.x0 - 3:
                            b["bbox"] = [cr.x0 + 2, bb.y0, cr.x1 - 2, bb.y1]
                        break
            todo.append(b)

        for b in todo:
            r = fitz.Rect(b["bbox"]) + (-0.5, -0.5, 0.5, 0.5)
            page.add_redact_annot(r, fill=False)
        if todo:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                                  graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                                  text=fitz.PDF_REDACT_TEXT_REMOVE)
        pen = Pen(page)
        for b in todo:
            if b.get("rot"):
                insert_rot(page, b, b["_zh"], pen)
            elif is_toc(b, b["_zh"]):
                insert_toc(page, b, b["_zh"], pen)
            else:
                insert_normal(page, b, b["_zh"], pen)
            stats["redrawn"] += 1
            fs_used = layout_lines(b["_zh"], b)[1] if not b.get("rot") else b["size"]
            if fs_used < b["size"] - 0.3: stats["shrunk"] += 1
        pen.flush((0, 0, 0))
        for b in blocks:
            for k in ("_zh",): b.pop(k, None)
    doc.save(out_path, garbage=3, deflate=True)
    doc.close()
    return stats

def add_disclaimer(pdf_path, text=None, rect=None, title="版 权 声 明", style="yellow"):
    """封面免责/版权声明。style:
      yellow（默认）— 亮黄底 + 深红边框 + 深红标题，醒目声明（用户可指定文案）
      plain         — 米色低调样式（适合封面留白紧张的文档）"""
    TEXT = text or ("声明：本翻译版本仅供参考与学习交流使用，任何针对技术标准、工程规范及合规要求的解读与执行，"
                    "均须以原发布机构的官方原版文件为准。原文件及相关内容的所有版权均归原作者/机构所有。")
    doc = fitz.open(pdf_path)
    page = doc[0]
    x0d, y0d, x1d, y1d = rect or (55, 630, 557, 772)
    x0, y0, x1, y1 = x0d, y0d, x1d, y1d
    if style == "yellow":
        edge, fill, tcol, bcol = (0.55, 0, 0), (1, 1, 0), (0.55, 0, 0), (0.05, 0.05, 0.05)
        tfs, bfs, bw = 13.5, 9.6, 2.6
    else:
        edge, fill, tcol, bcol = (0.06, 0.13, 0.29), (0.99, 0.98, 0.94), (0.06, 0.13, 0.29), (0.06, 0.13, 0.29)
        tfs, bfs, bw = 11.5, 9.6, 1.4
    page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=edge, fill=fill, width=bw, radius=0.025)
    pen = Pen(page)
    inner = x1 - x0 - 44
    ty = y0 + 16 + tfs
    tw_len = tw(title, tfs)
    pen.add(x0 + (x1 - x0 - tw_len) / 2, ty, title, tfs, True, tcol)
    ty += tfs * 1.55
    for ln in wrap([TEXT], inner, bfs):
        pen.add(x0 + 22, ty, ln, bfs, False, bcol)
        ty += bfs * 1.5
    pen.flush()
    doc.saveIncr()
    doc.close()

if __name__ == "__main__":
    print("engine_tw ready: build(pdf_path, extract_path, trans, out_path) / add_disclaimer(pdf, text=..., rect=...)")
