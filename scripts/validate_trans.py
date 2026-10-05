"""校验所有分块译文质量：六项检查
  1. id 覆盖（missing/extra 必须为空）
  2. JSON 合法
  3. ⟦⟧ 占位符与源一一对应（R3）
  4. 字面转义污染（译文含字面 "\\n" "\\t" 等——会原样印入成品）
  5. 截断嫌疑（译文长度 < 源文阈值比例，需人工裁决；宽限符号块）
  6. null（乱码）统计
用法: python validate_trans.py <workdir>
退出码: 0=必须项通过, 1=存在必须修复项；WARN 项需逐条裁决后放行或修复
"""
import json, glob, os, re, sys

BS = chr(92)
LIT_ESC = re.compile(BS + r"[ntrfv0]")          # 字面 \n \t \r 等
SYMBOL_OK = re.compile(r"^[\d\s.,\-–—°×/%≥≤<>+=()^\[\]{}|±·∙∕'\"^~:;?!*&#$_A-Za-zÅÄÅÉÈÑÖÜαβγδεθλμπσΔΩ≈≡—–‘’“”]*$")


def main():
    work = sys.argv[1] if len(sys.argv) > 1 else ".work"
    problems, warns, total = [], [], 0
    for cf in sorted(glob.glob(os.path.join(work, "chunks", "*_c*.json"))):
        name = os.path.basename(cf).replace(".json", "")
        tf = os.path.join(work, "trans", name + ".json")
        if not os.path.exists(tf):
            problems.append(f"{name}: 输出文件缺失"); continue
        try:
            tr = json.load(open(tf, encoding="utf-8"))
        except Exception as e:
            problems.append(f"{name}: JSON 解析失败 {e}"); continue
        ch = json.load(open(cf, encoding="utf-8"))
        ids = {it["id"] for it in ch["items"]}
        miss = ids - set(tr.keys())
        extra = set(tr.keys()) - ids
        nnull = sum(1 for v in tr.values() if v is None)
        ph_bad, esc_bad, trunc = [], [], []
        for it in ch["items"]:
            v = tr.get(it["id"])
            if v is None:
                continue
            src_ph = re.findall(r"⟦[PN]\d+⟧", it["text"])
            out_ph = re.findall(r"⟦[PN]\d+⟧", str(v))
            if sorted(src_ph) != sorted(out_ph):
                ph_bad.append(it["id"])
            src, out = it["text"].strip(), str(v).strip()
            if LIT_ESC.search(out) and not LIT_ESC.search(src):
                esc_bad.append(it["id"])
            sl, ol = len(src), len(out)
            if (sl > 80 and ol > 0 and ol < sl * 0.12
                    and re.search(r"[A-Za-z]{3}", src) and not SYMBOL_OK.fullmatch(src)):
                trunc.append((it["id"], sl, ol))
        total += len(ids)
        stat = f"{name}: items={len(ids)} translated={len(tr)-nnull} null={nnull}"
        if miss: stat += f" MISSING={len(miss)}"
        if extra: stat += f" EXTRA={len(extra)}"
        if ph_bad: stat += f" PH_BAD={ph_bad[:5]}"
        if miss or extra or ph_bad:
            problems.append(stat)
        else:
            print(stat)
        if esc_bad:
            warns.append(f"{name}: 字面转义污染 {len(esc_bad)} 条: {esc_bad[:8]}")
        if trunc:
            warns.append(f"{name}: 截断嫌疑 {len(trunc)} 条（译文<源文12%）: " +
                         ", ".join(f"{i}({s}->{o})" for i, s, o in trunc[:8]))

    print(f"\n总条目: {total}")
    if warns:
        print("WARN 需裁决:")
        for w in warns:
            print("  ~", w)
    if problems:
        print("必须修复:")
        for p in problems:
            print("  !", p)
        sys.exit(1)
    print("必须项全部通过 ✔（WARN 项对照源文逐条裁决后放行或修复）")


if __name__ == "__main__":
    main()
