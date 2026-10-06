"""构建驱动 v2（BUILD_FIX 声明式修复 + 规范译文/分块译文/伪块译文合并 + 免责声明）

职责（pdf-layout-engine.md「BUILD_FIX 声明式修复清单」的参考实现）：
  1. 合并四路译文：规范译文表(canonical.recurring) + 分块译文(_cNN) + 列拆分伪块译文(_cZZ)
     + 断点续译保底层(_c00，见 SKILL.md「增量续译」)
  2. 行序修复映射(lys_fixmap)：分块按旧行序翻译、提取件已按 y 重排时，构建期做
     行序重排 + ⟦N⟧ 索引重映射（R3：占位符作用域=解析基准；全局只应用一次）
  3. 应用 BUILD_FIX（.work/build_fix.json，声明式、逐项经视觉验收核实后登记）：
       drop_ids        徽标/Logo 字形块等不可重绘元素 → 整块保留原样（不脱字）
       drop_prefixes   水印前缀 → 只脱字不回填
       line_splits     混合块拆行（支持 size/color/dy 覆盖，用于封面标题分层、徽标保留）
       trans_overrides 定点译文（含 "__DROP__"）与伪块 id（"pNNbM#K"）补译
       lys_shift       整块行 y 偏移（重排设计）
  4. 免责声明：style="yellow"（默认，亮黄底红框醒目）/"plain"（米色低调）

用法（命令行）:
  python build_doc.py <doc_name> [--workdir .work] [--out "输出名 中文.pdf"]
  python build_doc.py <doc_name> --list-fix          # 打印已登记修复
文档名 = 提取件键（.work/extract/<doc_name>.json）。输出名默认 "<显示名> 中文.pdf"，
显示名 = doc_name 去除内部历史键差异（见 build_fix.json 的 display_name 字段）。
"""
import sys, os, re, json, glob, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canonical as C
import engine_tw

PH = re.compile(r"⟦N(\d+)⟧")


class Builder:
    def __init__(self, workdir=".work"):
        self.work = workdir
        fix_path = os.path.join(workdir, "build_fix.json")
        self.fix = json.load(open(fix_path, encoding="utf-8")) if os.path.exists(fix_path) else {}
        fxp = os.path.join(workdir, "lys_fixmap.json")
        self.fixmap = json.load(open(fxp, encoding="utf-8")) if os.path.exists(fxp) else {}

    # ---------- 译文合并 ----------
    def _fix_zh(self, dn, bid, zh):
        fm = self.fixmap.get(dn, {}).get(bid)
        if not fm or not isinstance(zh, str):
            return zh
        order, ph = fm.get("order") or [], fm.get("ph") or {}
        if "\n" in zh and order:
            zl = zh.split("\n")
            if len(zl) == len(order):
                zh = "\n".join(zl[i] for i in order)
        if ph:
            zh = PH.sub(lambda m: f"⟦N{ph.get(int(m.group(1)), int(m.group(1)))}⟧", zh)
        return zh

    def merge_trans(self, dn):
        C.WORK = self.work
        data = json.load(open(f"{self.work}/extract/{dn}.json", encoding="utf-8"))
        trans = {}
        for k, v in C.apply_recurring(dn, data).items():
            trans[k] = self._fix_zh(dn, k, v)
        for f in sorted(glob.glob(f"{self.work}/trans/{dn}_c*.json")):
            if "_cZZ" in f:
                continue
            d = json.load(open(f, encoding="utf-8"))
            for k, v in d.items():
                if v:
                    trans[k] = self._fix_zh(dn, k, v)
        zz = f"{self.work}/trans/{dn}_cZZ.json"
        if os.path.exists(zz):
            d = json.load(open(zz, encoding="utf-8"))
            trans.update({k: v for k, v in d.items() if v})
        return trans

    # ---------- BUILD_FIX ----------
    def prepare_extract(self, dn, drop_prefixes=()):
        fix = self.fix.get(dn) or {}
        drops = set(fix.get("drop_ids") or [])
        wm = set(fix.get("drop_prefixes") or ()) | set(drop_prefixes or ())
        splits = fix.get("line_splits") or {}
        shifts = fix.get("lys_shift") or {}
        if not drops and not wm and not splits and not shifts:
            return os.path.join(self.work, "extract", f"{dn}.json")
        src = os.path.join(self.work, "extract", f"{dn}.json")
        data = json.load(open(src, encoding="utf-8"))
        for p in data["pages"]:
            keep = []
            for b in p["blocks"]:
                if b["id"] in drops:
                    continue                      # 整块保留原样：不脱字、不重绘
                sh = shifts.get(b["id"])
                if sh and b.get("line_ys"):
                    b["line_ys"] = [y + d for y, d in zip(b["line_ys"], sh)]
                    b["bbox"] = [b["bbox"][0], b["bbox"][1] + min(0, min(sh)),
                                 b["bbox"][2], b["bbox"][3] + max(0, max(sh))]
                sp = splits.get(b["id"])
                if sp:
                    entries = sp if isinstance(sp, list) else [sp]
                    lys = b.get("line_ys") or []
                    for e in entries:
                        i = e.get("line", 0)
                        if lys and len(lys) > i:
                            lh = (b.get("line_hs") or [b["size"] * 1.2])[min(i, len(b.get("line_hs") or [0]) - 1)]
                            dy = e.get("dy", 0)
                            ny = lys[i] + dy
                            nb = dict(b)
                            nb["id"] = e["new_id"]
                            nb["text"] = b["text"].split("\n")[i]
                            if e.get("size"):
                                nb["size"] = e["size"]
                                lh = e["size"] * 1.2
                            if e.get("color") is not None:
                                nb["color"] = e["color"]
                            nb["bbox"] = [b["bbox"][0], ny - 1, b["bbox"][2], ny + lh + 1]
                            nb["nlines"] = 1
                            nb["line_ys"] = [ny]
                            nb["line_x0s"] = [(b.get("line_x0s") or [b["bbox"][0]])[i]]
                            nb["line_ws"] = [(b.get("line_ws") or [b["bbox"][2] - b["bbox"][0]])[i]]
                            nb["line_hs"] = [lh]
                            keep.append(nb)
                    continue
                keep.append(b)
            p["blocks"] = keep
        out = os.path.join(self.work, "extract", f"{dn}.build.json")
        json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False)
        return out

    def apply_overrides(self, dn, trans, drop_prefixes=()):
        fix = self.fix.get(dn) or {}
        for bid, ov in (fix.get("trans_overrides") or {}).items():
            if isinstance(ov, str):
                trans[bid] = ov
            elif isinstance(ov, dict) and "append" in ov:
                base = trans.get(bid)
                if isinstance(base, str) and base:
                    trans[bid] = base.rstrip() + ov["append"]
                elif base is not None:
                    trans[bid] = ov["append"]
        return trans

    # ---------- 构建 ----------
    def build(self, dn, out_pdf=None, drop_prefixes=(), disclaimer=None,
              disclaimer_rect=None, disclaimer_style="yellow"):
        os.chdir(os.path.dirname(os.path.abspath(self.work)) or ".")
        trans = self.merge_trans(dn)
        self.apply_overrides(dn, trans, drop_prefixes)
        ext = self.prepare_extract(dn, drop_prefixes)
        fixd = self.fix.get(dn) or {}
        display = fixd.get("display_name", dn)
        out_pdf = out_pdf or f"{display} 中文.pdf"
        src_pdf = fixd.get("source_pdf") or f"{display}.pdf"
        if not os.path.exists(src_pdf):
            src_pdf = f"{dn}.pdf"
        stats = engine_tw.build(dn, trans, out_pdf, extract_path=ext, pdf_path=src_pdf,
                                drop_prefixes=drop_prefixes or tuple(fixd.get("drop_prefixes") or ()))
        print(f"chunks merged; build stats: {stats}")
        if disclaimer:
            engine_tw.add_disclaimer(out_pdf, text=disclaimer, rect=disclaimer_rect,
                                     style=disclaimer_style)
            print(f"disclaimer ({disclaimer_style}) added")
        return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--workdir", default=".work")
    ap.add_argument("--out", default=None)
    ap.add_argument("--disclaimer", default=None)
    ap.add_argument("--disclaimer-rect", default=None, help="X0,Y0,X1,Y1")
    ap.add_argument("--style", default="yellow", choices=["yellow", "plain"])
    ap.add_argument("--list-fix", action="store_true")
    ns = ap.parse_args()
    b = Builder(ns.workdir)
    if ns.list_fix:
        print(json.dumps(b.fix.get(ns.doc, {}), ensure_ascii=False, indent=1))
        return
    rect = tuple(float(x) for x in ns.disclaimer_rect.split(",")) if ns.disclaimer_rect else None
    b.build(ns.doc, ns.out, disclaimer=ns.disclaimer, disclaimer_rect=rect,
            disclaimer_style=ns.style)


if __name__ == "__main__":
    main()
