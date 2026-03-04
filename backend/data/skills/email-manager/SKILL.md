---
name: email-manager
description: 邮件管理技能 — 读取、搜索、发送邮件（IMAP/SMTP）
version: "1.0"
metadata:
  nanobot:
    emoji: "📧"
    always: false
    requires:
      bins: []
      env:
        - IMAP_HOST
        - IMAP_USER
        - IMAP_PASSWORD
---

# 邮件管理

你现在拥有管理邮件的能力（通过 IMAP/SMTP 协议）。

## 能力范围

- 连接邮件服务器（IMAP）
- 读取收件箱邮件列表
- 搜索特定主题/发件人的邮件
- 读取邮件内容（文本和附件）
- 发送邮件（SMTP）
- 标记邮件（已读/未读/星标）
- 移动邮件到指定文件夹

## 环境变量要求

在使用此技能前，请确保以下环境变量已配置：

- `IMAP_HOST`: IMAP 服务器地址（如 imap.gmail.com）
- `IMAP_USER`: 邮箱地址
- `IMAP_PASSWORD`: 邮箱密码或应用专用密码
- `SMTP_HOST`（可选）: SMTP 服务器地址
- `SMTP_PORT`（可选）: SMTP 端口（默认 587）

## 使用方法

使用 `python_repl` 执行 Python 代码：

```python
import imaplib
import email

mail = imaplib.IMAP4_SSL(os.environ["IMAP_HOST"])
mail.login(os.environ["IMAP_USER"], os.environ["IMAP_PASSWORD"])
mail.select("inbox")
```

## 注意事项

- 发送邮件前必须经用户确认
- 不要在日志或输出中展示密码
- 注意邮件的隐私敏感性
- Gmail 用户需要使用应用专用密码
