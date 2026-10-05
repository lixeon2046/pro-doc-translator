"""改进版分块器 v2：
- 分块边界只落在"安全页边界"：非跨页表格延续页、非跨页段落延续处，优先章节标题页
- 跨页表格（find_tables 列签名延续检测）所在页永不作为边界
- 缩写首现映射（按全文档顺序，供子代理准确执行"首次出现展开"规则）
- 更大的前后文衔接窗口
"""
import fitz, json, os, re, glob
from collections import Counter, defaultdict

import sys as _sys
DOCS = _sys.argv[1:-1] if len(_sys.argv) > 2 else ["DOC"]
MAXCH = 14000      # 目标块大小
HARDMAX = 21000    # 找不到安全边界时的硬上限
KEEP_PREFIX = os.environ.get("KEEP_PREFIX", "This copy of the document")  # 水印/内部标记前缀，按文档设置

def norm_key(t):
    return re.sub(r"\d+", "", t.replace("\xa0", " "))[:60]

# 线性正则：单一字符类吃掉点线，避免灾难性回溯（长目录点线曾致 CPU 爆转）
TOC_LINE = re.compile(r"^(.*\S)[\s.]{6,}(\d{1,4})\s*$")
TOC_ONLY = re.compile(r"^[\s.]{6,}(\d{1,4})\s*$")

def preprocess(t):
    out = []
    for ln in t.split("\n"):
        m = TOC_LINE.match(ln.strip())
        if m and m.group(1).strip():
            out.append(f"{m.group(1).strip()} ⟦P{m.group(2)}⟧")
        else:
            m2 = TOC_ONLY.match(ln.strip())
            out.append(f"⟦P{m2.group(1)}⟧" if m2 else ln)
    return "\n".join(out)

SYMBOL_RE = re.compile(r"[\d\s.,\-–—°×/%≥≤<>+=()^\[\]{}|±·∙∕'\"^~:;?!*&#$_A-Za-zÅÄÅÉÈÑÖÜαβγδεθλμπσΔΩ≈≡—–‘’“”]*")

def is_symbolic(t):
    """方程碎块/纯符号块：无长度>=4的拉丁词、无 CJK → 构建时保留原样，不入翻译分块"""
    s = t.strip()
    if not s or re.search(r"[\u4e00-\u9fff]", s):
        return False
    if re.search(r"[A-Za-z]{4,}", s):
        return False
    return bool(SYMBOL_RE.fullmatch(s))

def is_heading(b):
    t = b["text"].strip()
    if not b["bold"] and b["size"] < 11: return False
    return bool(re.match(r"^(SECTION [A-Z0-9]|Section \d|Appendix [A-Z]|APPENDIX [A-Z]|\d+\.\d+\s+\S|CHANGES|FOREWORD|CONTENTS|Contents|PART \d|Part [A-Z]{1,4}\b|ARTICLE [A-Z]{1,4}-|MANDATORY|NONMANDATORY|Annex \d|Chapter \d|[A-Z]{1,4}-\d+[A-Z]?\b)", t))

def body_blocks(page):
    """过滤页眉页脚/水印后的正文块"""
    out = []
    for b in page["blocks"]:
        t = b["text"]
        if t.strip().startswith(KEEP_PREFIX): continue
        if b["size"] <= 7.6: continue                      # 页眉页脚 7pt
        if re.match(r"^(Standard\s+—|Page\s+\d+|\d+/\d+|Changes|Contents$)", t.strip()): continue  # 页眉页脚模式按文档调整
        out.append(b)
    return out

def table_continuations(dn):
    """返回因跨页表格而不能作为边界的页码集合（1-based）
    快速通道：extract 阶段已做表格延续页检测（table_cont_pages），此处直接复用，
    避免对上千页重复跑 find_tables（译文按块独立回填，页边界对表格翻译无害）。"""
    ext = json.load(open(f".work/extract/{dn}.json"))
    return set(ext.get("table_cont_pages") or [])

def safe_boundaries(data, cont_pages):
    """页 p 可作为块起点（p 从 2 开始）"""
    safe = {}
    pages = data["pages"]
    for i in range(1, len(pages)):
        p = pages[i]["page"]
        reasons = []
        if p in cont_pages:
            safe[p] = (False, "跨页表格延续")
            continue
        prevb = body_blocks(pages[i-1])
        curb = body_blocks(pages[i])
        pl = prevb[-1] if prevb else None
        nf = curb[0] if curb else None
        if pl and nf:
            term = bool(re.search(r"[.!?:;”’)°]$", pl["text"].strip()))
            head_next = is_heading(nf) or (nf["bold"] and nf["size"] >= 11)
            short_line = pl["nlines"] >= 1
            # 上一块最后一行未写满（非折行）视为结束
            filled = pl["bbox"][2] >= (pl["bbox"][2])  # 占位
            full = pl["bbox"][2] - pl["bbox"][0] > 260  # 块较宽=正文段落
            if not term and not head_next and full:
                # 段落疑似跨页延续 → 不安全
                safe[p] = (False, "段落跨页延续")
                continue
        safe[p] = (True, "")
    return safe

# 受控缩写清单（术语库）：仅对这些跟踪"全文档首次出现"的分块位置
KNOWN_ABBREVS = os.environ.get("KNOWN_ABBREVS", "WLL,ISO,NDT,ITP,WPS,HVAC").split(",")
# ⚠️ 按你的领域设置受控缩写清单（逗号分隔环境变量，或直接编辑此行）

def scan_abbrevs(items):
    """items: [(chunk_idx, text)] -> {abbrev: chunk_idx首次}（仅受控清单）"""
    first = {}
    for ci, txt in items:
        for a in KNOWN_ABBREVS:
            if re.search(r"\b" + re.escape(a) + r"\b", txt) and a not in first:
                first[a] = ci
    return first

def main():
  for dn in DOCS:
      data = json.load(open(f".work/extract/{dn}.json"))
      cont = table_continuations(dn)
      sb = safe_boundaries(data, cont)
      # 重复项占位
      occ = defaultdict(list)
      for p in data["pages"]:
          for b in p["blocks"]:
              if len(b["text"]) < 90:
                  occ[norm_key(b["text"])].append(b["text"])
      repkeys = {k for k, v in occ.items() if len(v) >= 3}
      vary = {}
      for k in repkeys:
          runs = [re.findall(r"\d+", t) for t in occ[k]]
          maxlen = min(len(r) for r in runs)
          vset = {i for i in range(maxlen) if len({r[i] for r in runs if len(r) > i}) > 1}
          if vset: vary[k] = vset
      # 预处理全部块
      for p in data["pages"]:
          for b in p["blocks"]:
              b["text"] = b["text"].replace("\xa0", " ")
      # 页组装
      pagechars = {}
      for p in data["pages"]:
          c = 0
          for b in p["blocks"]:
              if b["text"].strip().startswith(KEEP_PREFIX): continue
              if is_symbolic(b["text"]): continue   # 方程碎块不入分块（构建时保留原样）
              t = preprocess(b["text"])
              k = norm_key(b["text"])
              c += len(t)
          pagechars[p["page"]] = c
      # 贪心分块：目标 MAXCH，边界优先取安全页；超过 HARDMAX 强制切分并记录
      pages = [p["page"] for p in data["pages"]]
      chunks = []
      forced_bounds = []
      cur_pages = [pages[0]]
      cur_c = pagechars[pages[0]]
      for p in pages[1:]:
          if cur_c >= MAXCH and sb.get(p, (True, ""))[0]:
              chunks.append(cur_pages); cur_pages = [p]; cur_c = pagechars[p]
          else:
              cur_pages.append(p); cur_c += pagechars[p]
              # 硬上限：无条件强切（段落连续性由 context_before/after 兜底），避免块超限膨胀
              if cur_c >= HARDMAX:
                  forced_bounds.append(p)
                  chunks.append(cur_pages); cur_pages = []; cur_c = 0
      if cur_pages: chunks.append(cur_pages)
      chunks = [c for c in chunks if c]
      # 清理旧块文件
      for f in glob.glob(f".work/chunks/{dn}_c*.json"): os.remove(f)
      # 生成 chunk 文件
      items_by_page = defaultdict(list)
      for p in data["pages"]:
          for b in p["blocks"]:
              if b["text"].strip().startswith(KEEP_PREFIX): continue
              if is_symbolic(b["text"]): continue   # 方程碎块：构建时自动保留原样
              t = preprocess(b["text"])
              k = norm_key(b["text"])
              if k in vary:
                  holder = {"idx": -1}
                  def sub(m, holder=holder, k=k):
                      holder["idx"] += 1
                      return f"⟦N{holder['idx']}⟧" if holder["idx"] in vary[k] else m.group(0)
                  t = re.sub(r"\d+", sub, t)
              items_by_page[p["page"]].append({"id": b["id"], "page": p["page"], "text": t})
      # 标题上下文
      all_head = []
      for p in data["pages"]:
          for b in p["blocks"]:
              if is_heading(b): all_head.append((p["page"], b["text"][:60].replace("\n", " ")))
      # 缩写首现（按 chunk 顺序）
      seq = []
      for ci, pglist in enumerate(chunks):
          for p in pglist:
              for it in items_by_page[p]:
                  seq.append((ci, it["text"]))
      ab_first = scan_abbrevs(seq)
      for ci, pglist in enumerate(chunks):
          items = [it for p in pglist for it in items_by_page[p]]
          head = "文档起始"
          for hp, ht in all_head:
              if hp >= pglist[0]: break
              head = ht
          before_ids = [it for p in chunks[ci-1] for it in items_by_page[p]] if ci > 0 else []
          after_ids = [it for p in chunks[ci+1] for it in items_by_page[p]] if ci < len(chunks)-1 else []
          bb = " ⏎ ".join(it["text"] for it in before_ids[-2:])[-900:]
          aa = " ⏎ ".join(it["text"] for it in after_ids[:1])[:400]
          abbrs = sorted(a for a, c in ab_first.items() if c == ci)
          out = {"doc": dn, "chunk": ci+1, "title": head,
                 "pages": [pglist[0], pglist[-1]],
                 "context_before": bb, "context_after": aa,
                 "first_abbrevs": abbrs, "items": items}
          json.dump(out, open(f".work/chunks/{dn}_c{ci+1:02d}.json", "w"), ensure_ascii=False)
      nb = sum(len([it for p in c for it in items_by_page[p]]) for c in chunks)
      print(f"{dn}: {len(chunks)} chunks, {nb} items, 跨页表格保护页={sorted(cont)}, 强制切分页={forced_bounds}, 平均块字符={sum(pagechars.values())//max(1,len(chunks))}")


if __name__ == "__main__":
    main()


# 用法: python3 chunk_safe.py <doc1> [doc2 ...] <workdir>  （需先运行 extract_pdf.py 与分块前处理）
