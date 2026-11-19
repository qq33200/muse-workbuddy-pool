# PikPak 资源检索器 v1.1.1（本地版）

只做技术聚合：提取、去重、排除已有、导出。不做任何内容筛选，搜到什么就显示什么，资源由使用者自己判断。

## 文件
- `PikPakRetriever.py`：源码，751 行，Python 标准库 only（tkinter GUI），不用 pip 装任何库。VERSION = "1.1.1"
- EXE 本体不在 GitHub 里（二进制 12.8 MB，GitHub 推送只支持 UTF-8 文本）：`PikPakRetriever-v1.1.1.exe`，MD5 `7e6834ba7750c6c6d265695731c41574`，12,882,416 字节。用户本地 Downloads 里有这个文件，窗口标题栏应显示 v1.1.1。

## 在 Windows 上跑
1. 装 Python 3.10 以上（python.org，安装时勾选 Add Python to PATH，官方包自带 tkinter）。
2. 双击 `PikPakRetriever.py` 打开窗口。
3. 输入关键词 -> 点“聚合搜索” -> 勾选想要的 -> 点“导出已选为 CSV”。
4. 命令行：`python PikPakRetriever.py --cli 蜘蛛侠`，加 `--out 结果.csv` 直接导出。

导出 CSV 列：序号、资源名称、分类、PikPak分享链接、搜索关键词

## 来源（全部直接请求，不走中转代理）
- Bing RSS：最稳，结构化标题+链接，但每 site: 查询最多返回 10 条
- Bing 网页：备用
- DuckDuckGo：解析 html 版结果页，v1.1.1 已修标题缺失（按结果块切分，标题空了用摘要补）；若过半结果仍无标题，程序会在 EXE 旁边生成 `ddg_debug.html`，把那个文件发回 Muse 诊断
- Google：经常 429，通了就有，不通不影响其他来源
- PakSeek：有 Cloudflare 验证，只能在程序里点按钮在浏览器打开，不能直连抓取

## v1.1.1 已修
- DDG 标题缺失：旧版按位置配对标题和链接，每个结果有两条链接导致错位；v1.1.0 改成同锚点取标题+链接，v1.1.1 再修了 href 在 class 前面的情况。
- 继续加载：无上限，每点一次“聚合搜索”/“继续加载”抓满约 100 条新结果（按页取整），本批 0 条新结果就提示“没有更多了”。

## 打包成 EXE（需要时）
`PyInstaller --onefile --windowed PikPakRetriever.py`，未签名，首次运行 Windows 可能弹 SmartScreen，点“更多信息”再点“仍要运行”。

## 分工
- WorkBuddy：本地运行、验证、抓日志/报错；小修可直接改源码，改完在 Issue 评论里写清楚。
- Muse：远程改代码、修解析逻辑；需要 Muse 改的，在 Issue 交接备注里写清现象+报错，标签改回 status:muse。
