# ChineseInLA → Notion 自动抓取

自动抓取 ChineseInLA「工作求职」论坛，按洛杉矶自然日期保留最近 N 天，执行关键词筛选后覆盖更新到固定 Notion 页面。

## 当前设置

- `DAYS_TO_KEEP = 2`：今天 + 昨天
- GitHub Actions 每 2 小时自动运行一次
- 不使用浏览器，使用 `requests + BeautifulSoup`
- Notion Token 不写入代码，使用 GitHub Actions Secret `NOTION_TOKEN`

## 文件结构

- `main.py`：抓取、筛选、写入 Notion
- `runner.py`：稳定运行入口，增加重试与安全清理
- `requirements.txt`：Python 依赖
- `tests/fixed_test.py`：开发测试，仅手动运行
- `output/`：运行时生成 CSV 备份，不提交到仓库

## 手动运行

进入 GitHub：`Actions → ChineseInLA → Notion → Run workflow`。

## 修改保留天数

在 `main.py` 顶部修改：

```python
DAYS_TO_KEEP = 2
```

- `1` = 只保留今天
- `2` = 今天 + 昨天
- `3` = 最近 3 个自然日
