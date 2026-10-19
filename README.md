# pdf-t2s

把繁体中文 PDF 转换成简体中文 PDF，**保留原有排版**：颜色、字号、粗细、表格、图片和背景都不变。不是把文字提取出来重新排版，而是直接替换 PDF 里的文字层。

这是一个 [Claude Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)，也可以单独当命令行工具用。

## 原理

1. 用 PyMuPDF 读出每个字的位置、字号、颜色和粗细
2. 用 OpenCC 转换（默认 `hk2s` 港繁规则，只改字形，不换用词）
3. 有字需要转换的行，先删掉文字（不碰背景、线条和图片），再用思源黑体简体（Noto Sans SC）在原坐标逐字重绘
4. 字体子集化并转成 TrueType 轮廓后嵌入，输出文件大小和原文件接近
5. 重写 ToUnicode，保证转换后的文字能正常复制和搜索
6. 逐页校验：输出的文字必须和「原文转简体」一字不差

另外会修正 PDF 里常见的错误字符：CJK 兼容汉字、康熙部首（`⾧`→长）、笔画符号（`㇐`→一），以及被错位编码的标点（`˴`→、，`˹˼`→「」）。

## 安装为 Claude Skill

**Claude Code：**

```bash
git clone https://github.com/mousezyr/pdf-t2s ~/.claude/skills/pdf-t2s
```

**Claude 桌面版 / claude.ai：** 把仓库打包成 zip，在 Customize → Skills → Add → Upload skill 上传。

安装后，跟 Claude 说「把这个 PDF 转成简体」就会调用这个技能。

## 命令行用法

```bash
PY=$(bash scripts/setup.sh)          # 首次运行：venv 和依赖装在 ~/.cache/pdf-t2s
"$PY" -I scripts/batch.py OUTDIR a.pdf b.pdf ...
```

- 输出文件名为「原文件名转简体 + （简体）.pdf」，多个文件并行处理
- 台湾繁体：命令前加 `PDF_T2S_CONFIG=tw2s`；通用规则：`t2s`
- 单个文件：`scripts/convert.py src dst`，校验：`scripts/verify.py src dst`

依赖：Python 3.9+、`pymupdf`、`opencc-python-reimplemented`、`fonttools`（由 `setup.sh` 自动安装）。

## 限制

- 只能处理有文字层的 PDF；扫描件要先 OCR
- 图片和截图里的文字不会转换
- 竖排或旋转的文字暂不支持

## 许可

- 代码（`SKILL.md`、`scripts/` 等）：[MIT](LICENSE)，可以自由使用、修改和再分发
- `fonts/` 中的 Noto Sans SC 由 Google / Adobe 以 [SIL Open Font License 1.1](fonts/OFL.txt) 发布
