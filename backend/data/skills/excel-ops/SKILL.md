---
name: excel-ops
description: Excel/CSV 文件操作技能 — 读取、写入、筛选、排序、公式计算
version: "1.0"
metadata:
  nanobot:
    emoji: "📊"
    always: false
    requires:
      bins: []
      env: []
---

# Excel / CSV 操作

你现在拥有处理 Excel 和 CSV 文件的能力。

## 能力范围

- 读取 `.xlsx`、`.xls`、`.csv` 文件内容
- 创建新的 Excel/CSV 文件
- 对数据进行筛选、排序、去重
- 执行基本公式计算（求和、平均、计数等）
- 数据透视和分组统计
- 合并多个表格
- 格式转换（Excel ↔ CSV）

## 使用方法

使用 `python_repl` 工具执行 Python 代码来操作 Excel 文件。可用的库：

```python
import openpyxl  # .xlsx 读写
import csv       # CSV 读写
```

## 注意事项

- 大文件（>10MB）处理时注意内存
- 始终先读取表头，确认结构后再操作
- 修改文件前先告知用户将要进行的操作
- 保存时使用新文件名，避免覆盖原文件
