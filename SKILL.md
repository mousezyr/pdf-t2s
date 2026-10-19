---
name: pdf-t2s
description: 把繁体中文 PDF 转换成简体中文 PDF，保留原有排版、颜色、字号、表格和图片（原位替换文字层，不是重新排版）。当用户要求“把 PDF 转成简体”“繁转简”“转换成简体中文 PDF”或给出繁体 PDF 要简体版时使用。
---

# PDF 繁体 → 简体（保留排版）

原理：用 PyMuPDF 读出每个字的位置；凡是有字需要转换的行，先删掉这一行的文字（只删文字，背景、线条和图片都不动），再用思源黑体简体（Noto Sans SC，常规/粗体对应原文粗细）在原坐标逐字重绘。转换用 OpenCC（默认 `hk2s` 港繁规则，只改字形，不换用词）。字体会子集化并转成 TrueType 轮廓后嵌入，文件体积和原文件接近。另外会重写 ToUnicode，保证转换后的文字能正常复制和搜索。

## 使用步骤

下文中的 `$SKILL` 指本技能所在目录（就是这个 SKILL.md 所在的文件夹），`$PY` 指 setup.sh 最后一行输出的 Python 路径。

1. **先执行 setup**：依赖装在 `~/.cache/pdf-t2s`，已经装好时会直接跳过：
   ```bash
   PY=$(bash "$SKILL/scripts/setup.sh")
   ```

2. **确认 PDF 有文字层**（扫描件没有文字层，这个技能处理不了，需要先 OCR）：
   ```bash
   "$PY" -I -c "import fitz,sys; d=fitz.open(sys.argv[1]); print(len(d), repr(d[min(1,len(d)-1)].get_text()[:200]))" "file.pdf"
   ```
   如果输出为空或乱码，告诉用户需要先做 OCR。

3. **批量转换并校验**。如果源文件在微信临时目录这类不受信任的位置，先复制到一个单独的新目录再处理：
   ```bash
   "$PY" -I "$SKILL/scripts/batch.py" OUTDIR a.pdf b.pdf ...
   ```
   - 输出文件名 = 原文件名转简体 + `（简体）.pdf`
   - 多个文件并行处理，100 页的文件大约十几秒
   - 台湾繁体在命令前加 `PDF_T2S_CONFIG=tw2s`，通用规则用 `t2s`
   - 单个文件可以直接用 `scripts/convert.py src dst` 和 `scripts/verify.py src dst`
   - stderr 里的 `MuPDF error: format error ...` 是原 PDF 内容流的小问题，可以忽略

4. **检查结果**：
   - 每个文件的校验结果都应该是 `mismatched 0`，且没有 `still traditional`。如果有 `lost/extra`，通常是同一个字形被映射到不同码位（比如 `•` 和 `・`），看一下是不是只影响复制出来的文字、视觉上没问题。
   - `missing glyphs` 指 Noto 字体里没有的字符。这种字符会被跳过，相当于丢字，需要在 `convert.py` 的 `FIX` 表里加一条映射。
   - **一定要渲染几页看一下**（封面、目录、正文、表格页），必要时放大到 200dpi 检查小字：
     ```bash
     "$PY" -I -c "import fitz,sys; d=fitz.open(sys.argv[1]); [d[i].get_pixmap(dpi=80).save(f'/tmp/t2s_{i}.png') for i in map(int, sys.argv[2:])]" out.pdf 0 3 10
     ```
     然后用 Read 查看 PNG。文字层校验通过不代表显示正确，以前就遇到过字体编号错位导致显示乱码、但文本校验照样通过的情况。

5. **交付**：把文件交付给用户（有 SendUserFile 工具就用它），并说明以下几点：
   - 图片和截图里的文字没有转换（需要 OCR 后重新做图）
   - 改动过的行换成了 Noto Sans SC；完全不含繁体字的行（纯英文、数字）保留原字体
   - 只做字形转换，没有把用词换成内地说法

## 已处理的原文问题

`convert.py` 中的 `norm()` / `FIX` 会处理 PDF 里常见的错误字符：CJK 兼容汉字（U+F900 起）、康熙部首（如 `⾧`→長）、笔画符号 `㇐`→一，以及被错位编码成修饰字母的标点（`˴ˑ`→、，`˹˼`→「」）。遇到新的错误字符时加到 `FIX` 里。

## 已知限制

- 竖排或旋转的文字没有单独处理（`line["dir"]` 不是 `(1,0)` 的行）。如果有，需要用 TextWriter 的 `morph` 参数补上。
- 转换结果和原文长度不一致时（极少见），会退回逐字转换。
