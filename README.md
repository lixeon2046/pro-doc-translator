# pro-doc-translator · 专业文档翻译师

**Any-industry, any-format professional document translation skill for ZCode** — auto-builds domain glossaries, restores PDF layout 1:1, translates Office files in place, and ships with a four-fold QA + visual-acceptance loop.

**任意行业、任意格式的专业文档翻译技能**：自动构建领域专业词汇表，PDF 1:1 版式还原，Office 原位翻译保格式，内置四重自动 QA 与视觉验收闭环。由 DNV 2.7 系列标准（260 页）全自动中文化项目实战淬炼而来。

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ 截图预览 Screenshots

| 免责声明注入 Disclaimer Injection | 复杂表格 Complex Tables |
|---|---|
| ![cover](docs/screenshots/01_cover_disclaimer.png) | ![table](docs/screenshots/02_complex_table.png) |

**旋转表头矩阵 Rotated Matrix Headers**
![matrix](docs/screenshots/03_matrix_rotated.png)

> 左：英文原版 Left: English original · 右：中文参考译本 Right: Chinese translation（内页右侧红竖排水印已裁切，internal watermark cropped for demo）

---

## 🎯 核心能力 Features

| | 中文 | English |
|---|---|---|
| 📖 | **任意领域词汇表自动构建**：领域判定 → 术语挖掘（词频/缩写/定义句式/表头）→ 权威查证（标准组织/术语审定委员会/官方双语文件）→ 三层定稿（verified / consistent / keep-original） | **Auto domain glossary**: domain detection → term mining (n-gram, acronyms, definition patterns, table headers) → authoritative lookup (standards bodies, official bilingual docs) → 3-tier consolidation |
| 📐 | **PDF 1:1 版式还原**：TextWriter 度量一致绘制、表格列合并块行×列拆分、行级锚定、旋转表头、目录点线、红色修订保留、封面免责声明 | **PDF 1:1 layout restore**: TextWriter metric-consistent drawing, row×column splitting of column-merged blocks, per-line anchoring, rotated headers, TOC dot leaders, cover disclaimer |
| 📁 | **多格式路由**：原生 PDF / 扫描 PDF(OCR) / DOCX / PPTX / XLSX / Markdown / 纯文本，Office 原位翻译保样式 | **Format routing**: native/scanned PDF, Office in-place translation preserving styles |
| 🔗 | **链式翻译流水线**：文档内块间串行共享实际译文衔接与术语决策日志，文档间并行 | **Chained pipelines**: serial within a document (real-translation handoff + term decision log), parallel across documents |
| ✅ | **四重自动 QA + 视觉验收**：完整性/术语漂移/残留源语言/表格覆盖率 + 越界/微字/页脚/叠印扫描 + 视觉代理逐页裁决闭环 | **Four-fold QA + visual acceptance**: completeness/terminology drift/source-language residue/table coverage + overflow/tiny-font/footer/overlap scans + per-page visual judge loop |
| 🔁 | **无人值守**：全中间产物落盘、断点续跑、配额中断自动定时恢复 | **Unattended**: everything persisted, resumable, auto-retry timer on quota interruption |

## 📊 实战战绩 Proven Track Record

DNV 2.7 系列标准中文化：**260 页 / 6,457 文本块 / 5,140 条译文**，术语漂移 0、占位符残留 0、微字 0、书签 533 条全中文化，视觉验收终审全部通过。

## 🚀 快速开始 Quick Start

### 作为 ZCode 技能使用 As a ZCode skill

```bash
# 克隆到技能目录 Clone into your skills directory
git clone https://github.com/lixeon2046/pro-doc-translator.git ~/.agents/skills/pro-doc-translator
# 重启 ZCode 后，直接说：
# After restarting ZCode, just say:
“把 ./report.pdf 翻译成中文”          → 自动触发技能
“Translate ./manual.docx to English” → auto-triggers
```

或使用通用任务启动提示词模板：[`assets/task-prompt-template.md`](assets/task-prompt-template.md)

### 依赖 Dependencies

```
PyMuPDF (fitz) >= 1.24    # PDF 提取与版式回填 extraction & layout
Pillow                    # 截图与质检图像（可选 optional）
# Office 路线 Office route: python-docx / python-pptx / openpyxl
```

### 脚本速查 Scripts

| 脚本 | 用途 Purpose |
|---|---|
| `scripts/extract_pdf.py` | 结构化提取（行级几何/旋转/跨页表格检测）Structured extraction |
| `scripts/chunk_safe.py` | 表感知安全分块 Table-aware safe chunking |
| `scripts/canonical.py` | 高频重复文本规范译文表 Canonical recurring translations |
| `scripts/patch_columns.py` | 列合并块拆分 Column-merged block splitting |
| `scripts/engine_tw.py` | TextWriter 版式回填引擎 Layout restoration engine |
| `scripts/validate_trans.py` / `qa_scan.py` / `tables_coverage.py` | QA 套件 QA suite |

## 🏗️ 工作流 Workflow

```
解析 Extract → 词汇表 Glossary → 分块 Chunk → 链式翻译 Chained translation
→ 校验 Validate → 版式回填 Layout restore → 成品QA Output QA → 视觉验收 Visual loop → 交付 Deliver
```

详细方法论文档：[`references/`](references/)（词汇表构建协议 / PDF 引擎规范 / Office 路线 / QA 协议）

## ⚠️ 免责声明 Disclaimer

本工具用于翻译你拥有合法使用权的文档。标准原文的版权归属原发布机构（如 DNV、ISO）；译文仅供参考，任何技术要求的解读与执行均须以官方原版文件为准。本仓库不包含任何受版权保护的文档内容。

Use this tool only on documents you are legally entitled to translate. Copyright of source standards remains with their publishers. Translations are for reference only. This repository contains no copyrighted document content.

## 📄 许可证 License

[MIT](LICENSE) © 2026 lixeon2046
