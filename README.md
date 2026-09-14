# ChineseInLA → Notion 自动抓取

自动抓取 ChineseInLA「工作求职」论坛，按洛杉矶自然日期保留最近 N 天，执行关键词筛选后覆盖更新到固定 Notion 页面。

## 当前设置

- `DAYS_TO_KEEP = 2`：今天 + 昨天
- 每 30 分钟由 GitHub Actions 自动运行
- 不使用浏览器，使用 `requests + BeautifulSoup`
- Notion Token 不写入代码，使用 GitHub Actions Secret `NOTION_TOKEN`

## 必须设置的 GitHub Secret

进入仓库：`Settings → Secrets and variables → Actions → New repository secret`

名称：`NOTION_TOKEN`

值：你的 `ntn_...` Notion Token。

Notion Page ID 已经写入 `main.py`，不需要另外配置。

## 手动测试

进入 `Actions → ChineseInLA Bot → Run workflow`。

## 修改保留天数

在 `main.py` 顶部修改：

```python
DAYS_TO_KEEP = 2
```

- `1` = 只保留今天
- `2` = 今天 + 昨天
- `3` = 最近 3 个自然日
