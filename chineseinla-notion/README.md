# ChineseInLA → Notion 自动抓取

自动抓取 ChineseInLA「工作求职」论坛当天刷新帖子，按既定规则筛选后覆盖更新到固定 Notion 页面。

## 当前设置

- 只保留洛杉矶自然日“今天”刷新、以 `am/pm` 显示的帖子
- GitHub Actions 每 2 小时自动运行一次，也可以手动触发
- 使用 `requests + BeautifulSoup`，不依赖浏览器
- 按帖子 URL 全局去重，重复置顶帖子只记录一次
- 分页停止采用安全判断：连续 2 页没有今天帖子、至少 5 条旧日期帖子、旧帖比例至少 50%、页面日期都不晚于昨天、且没有首次出现的未知时间帖子，才停止继续翻页
- 运行跨越洛杉矶午夜时停止写入，避免混入两个自然日
- 未抓到任何今天帖子时不清空 Notion
- 不生成 CSV、HTML 备份或 GitHub Actions Artifact；生产任务只把结果写入 Notion
- Notion Token 使用 GitHub Actions Secret `NOTION_TOKEN`，不写入代码

## 筛选规则

优先保留：幼儿园/学校前台、设备维保/设备维修/机修等明确要求保留的招聘。

排除：个人求职、保险/理财、Uber/大黑/Lyft、牙科/医疗/医美、按摩/美容/SPA、律师/律所、培训/办证/招生、个人接活/服务广告、车主/加盟/合伙、明显营销引流。

标题过短、信息不足时不误删，标为“待核对”。普通仓库、物流、一般司机、销售、装修技工等正常招聘继续保留。

## 文件结构

- `main.py`：抓取、去重、筛选、Notion 同步逻辑
- `runner.py`：生产运行入口，处理临时网络失败、关闭文件输出、清理临时文件并保证 Notion 重复清理安全
- `requirements.txt`：Python 依赖

## 手动运行

进入 GitHub：`Actions → ChineseInLA → Notion → Run workflow`。
