# pro-doc-translator · 专业文档翻译师

**Any-industry, any-format professional document translation for AI agents** — auto-builds domain glossaries, restores PDF layout 1:1, translates Office files in place, and ships with a four-fold QA + visual-acceptance loop. Works as a portable skill or as a plain prompt + toolkit with **any AI agent**, on **Windows / macOS / Linux**.

**任意行业、任意格式的专业文档翻译**：自动构建领域专业词汇表，PDF 1:1 版式还原，Office 原位翻译保格式，内置四重自动 QA 与视觉验收闭环。以可移植技能或「提示词 + 工具箱」形式适配**任何 AI agent**，支持 **Windows / macOS / Linux** 全平台。由一个 260 页工业标准全自动翻译项目实战淬炼而来。

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey) ![Agents](https://img.shields.io/badge/agents-any%20AI%20agent-8A2BE2) ![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ 截图预览 Screenshots

| 免责声明注入 Disclaimer Injection | 复杂表格 Complex Tables |
|---|---|
| ![cover](docs/screenshots/01_cover_disclaimer.png) | ![table](docs/screenshots/02_complex_table.png) |

**旋转表头矩阵 Rotated Matrix Headers**
![matrix](docs/screenshots/03_matrix_rotated.png)

> 左：英文原版 Left: English original · 右：中文参考译本 Right: Chinese translation（样例文档，页内右侧内部水印已裁切 internal watermark cropped for demo）

---

## 🎯 核心能力 Features

| | 中文 | English |
|---|---|---|
| 📖 | **任意领域词汇表自动构建**：领域判定 → 术语挖掘（词频/缩写/定义句式/表头）→ 权威查证（标准组织/术语审定机构/官方双语文件，逐条记录来源与置信级）→ 三层定稿（verified / consistent / keep-original） | **Auto domain glossary**: domain detection → term mining (n-gram, acronyms, definition patterns, table headers) → authoritative lookup (standards bodies, terminology councils, official bilingual docs, with sources & confidence) → 3-tier consolidation |
| 📐 | **PDF 1:1 版式还原**：TextWriter 度量一致绘制、表格列合并块行×列拆分、行级锚定、旋转表头、目录点线、封面免责声明 | **PDF 1:1 layout restore**: TextWriter metric-consistent drawing, row×column splitting of column-merged blocks, per-line anchoring, rotated headers, TOC dot leaders, cover disclaimer |
| 📁 | **多格式路由**：原生 PDF / 扫描 PDF(OCR) / DOCX / PPTX / XLSX / Markdown / 纯文本，Office 原位翻译保样式 | **Format routing**: native/scanned PDF, Office in-place translation preserving styles |
| 🔗 | **链式翻译流水线**：文档内块间串行共享实际译文衔接与术语决策日志，文档间并行 | **Chained pipelines**: serial within a document (real-translation handoff + term decision log), parallel across documents |
| ✅ | **四重自动 QA + 视觉验收**：完整性/术语漂移/残留源语言/表格覆盖率 + 越界/微字/页脚/叠印扫描 + 渲染页面逐页裁决闭环 | **Four-fold QA + visual acceptance**: completeness/terminology drift/source-language residue/table coverage + overflow/tiny-font/footer/overlap scans + rendered-page review loop |
| 🔁 | **无人值守**：全中间产物落盘、断点续跑、配额中断自动定时恢复 | **Unattended**: everything persisted, resumable, auto-retry timer on quota interruption |

## 📊 实战战绩 Proven Track Record

一个 260 页工业标准全自动翻译项目：**6,457 文本块 / 5,140 条译文**，术语漂移 0、占位符残留 0、微字 0、书签 533 条全中文化，视觉验收终审全部通过。

A 260-page industrial-standard project: **6,457 blocks / 5,140 translations**, zero terminology drift, zero placeholder leaks, zero sub-4.5pt text, 533 bookmarks localized, full visual acceptance.

## 🚀 快速开始 Quick Start

### 方式一 · 作为可移植技能 Portable skill（支持 Agent Skills 规范的 agent）

遵循开放 `SKILL.md` 规范，适用于 Claude Code、ZCode 及其他支持该规范的 coding agent：

```bash
# macOS / Linux
git clone https://github.com/lixeon2046/pro-doc-translator.git ~/.agents/skills/pro-doc-translator
# Windows (PowerShell)
git clone https://github.com/lixeon2046/pro-doc-translator.git "$env:USERPROFILE\.agents\skills\pro-doc-translator"
```

各 agent 的技能目录不同（如 Claude Code 为 `~/.claude/skills/`）——把克隆目录放到你的 agent 对应位置即可。重启后直接说：

> “把 ./report.pdf 翻译成中文” / “Translate ./manual.docx to English”

### 方式二 · 任何 AI agent + 工具箱 Any agent + toolkit

不需要技能机制也能用：把 [`assets/task-prompt-template.md`](assets/task-prompt-template.md)（通用启动提示词）发给任意能读写文件、执行 Python 的 AI agent（Claude / GPT / GLM / Cursor / …），并让它使用 [`scripts/`](scripts/) 下的独立命令行工具。所有脚本仅依赖 `PyMuPDF`，全平台可运行：

```bash
pip install pymupdf
python scripts/extract_pdf.py ./report.pdf --workdir .work   # 1) 结构化提取
python scripts/chunk_safe.py report --workdir .work          # 2) 表感知安全分块
python scripts/engine_tw.py                                  # 3) TextWriter 版式回填（库调用）
python scripts/qa_scan.py ./report_zh.pdf --cjk-only         # 4) 成品扫描
```

完整工作流与各阶段规则见 [`SKILL.md`](SKILL.md) 与 [`references/`](references/)。

## 🏗️ 工作流 Workflow

```
解析 Extract → 词汇表 Glossary → 分块 Chunk → 链式翻译 Chained translation
→ 校验 Validate → 版式回填 Layout restore → 成品QA Output QA → 视觉验收 Visual loop → 交付 Deliver
```

| 脚本 Script | 用途 Purpose |
|---|---|
| `scripts/extract_pdf.py` | 结构化提取（行级几何/旋转/跨页表格检测）Structured extraction |
| `scripts/chunk_safe.py` | 表感知安全分块 Table-aware safe chunking |
| `scripts/canonical.py` | 高频重复文本规范译文表 Canonical recurring translations |
| `scripts/patch_columns.py` | 列合并块拆分 Column-merged block splitting |
| `scripts/engine_tw.py` | TextWriter 版式回填引擎 Layout restoration engine |
| `scripts/validate_trans.py` / `qa_scan.py` / `tables_coverage.py` | QA 套件 QA suite |

方法论文档：[`references/`](references/)（词汇表构建协议 / PDF 引擎规范 / Office 路线 / QA 协议）

## ⚠️ 免责声明 Disclaimer

本工具用于翻译你拥有合法使用权的文档。原文档的版权归属其发布机构；译文仅供参考，任何技术要求的解读与执行均须以官方原版文件为准。本仓库不包含任何受版权保护的文档内容。

Use this tool only on documents you are legally entitled to translate. Copyright of source documents remains with their publishers. Translations are for reference only. This repository contains no copyrighted document content.

## 📄 许可证 License

[MIT](LICENSE) © 2026 lixeon2046
