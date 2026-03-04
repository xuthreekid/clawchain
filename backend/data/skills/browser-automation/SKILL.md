---
name: browser-automation
description: 浏览器自动化技能 — 网页操作、表单填写、数据采集、截图
version: "1.0"
metadata:
  nanobot:
    emoji: "🌐"
    always: false
    requires:
      bins: []
      env: []
---

# 浏览器自动化

你现在拥有控制浏览器的能力，可以帮助用户完成网页操作。

## 能力范围

- 打开网页并导航
- 点击按钮、链接
- 填写表单、输入文本
- 读取网页内容和文本
- 截取网页截图
- 等待页面加载
- 处理下拉菜单和复选框
- 从网页提取结构化数据

## 使用方法

使用 `python_repl` 执行 Playwright 操作：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com")
    content = page.content()
    browser.close()
```

## 注意事项

- 默认使用无头模式（headless），可通过配置切换
- 需要等待页面加载完成后再操作
- 尊重网站的 robots.txt
- 采集数据时注意隐私和法律法规
- 操作前告知用户将要访问的网址
