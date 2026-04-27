<p align="right"><a href="SECURITY.md">English</a> · <b>简体中文</b></p>

# 安全策略

## 漏洞上报

**请不要**在 GitHub 上直接提 issue 汇报安全漏洞。

请使用 [GitHub Private Vulnerability Reporting](https://github.com/zhengbowenai-cmd/caliper/security/advisories/new)，
或者直接联系仓库维护者（邮箱见 `CODEOWNERS`）。

我们会在 **72 小时内** 回复确认，高严重级别漏洞目标在 **14 天内**
发布补丁。

## 覆盖范围

本策略覆盖：

- 通过畸形 SKILL.md / eval JSONL 输入触发的远程代码执行或命令注入
- 日志、run 目录、错误信息中泄露的密钥 / API key
- 绕过预算治理（`caliper.governance.budget`）导致 API 费用失控
- Prompt injection —— eval case 或 judge 返回能越过角色边界

纯粹的"质量不满意""准确率不够"这类问题，请走普通 issue 流程，
不属于本策略范围。

## 支持版本

只有 `main` 分支和最近一个 tag 过的 release 会接受安全修复。
更早的版本不做回溯，除非发现高危 RCE。

## 披露时间线

补丁发布后，我们会公开一份 GitHub Security Advisory，包含：

- CVE（如果已分配）
- 受影响版本 / 已修复版本
- 漏洞报告人（除非报告人希望保持匿名）
