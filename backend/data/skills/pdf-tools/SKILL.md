---
name: pdf-tools
description: PDF 处理技能 — 读取、合并、拆分、文字提取、格式转换
version: "1.0"
metadata:
  nanobot:
    emoji: "📄"
    always: false
    requires:
      bins: []
      env: []
---

# PDF 处理

你现在拥有处理 PDF 文件的能力。

## 能力范围

- 读取 PDF 文件内容（文字提取）
- 合并多个 PDF 文件
- 拆分 PDF（按页码范围）
- PDF 页面旋转
- 提取 PDF 中的图片
- PDF 元数据读取和编辑
- 简单的 PDF 生成（从文本或 Markdown）

## 使用方法

使用 `python_repl` 执行 Python 代码：

```python
import PyPDF2

# 读取 PDF
reader = PyPDF2.PdfReader("document.pdf")
for page in reader.pages:
    text = page.extract_text()
```

## 注意事项

- 扫描版 PDF 的文字提取准确度有限
- 合并/拆分操作前确认文件名和页码范围
- 处理加密 PDF 需要用户提供密码
- 保存时使用新文件名，避免覆盖原文件
