# PikPak 资源检索器 v1.1.2（本地版）

只做技术聚合：提取、去重、排除已有、导出。不做任何内容筛选，搜到什么就显示什么，资源由使用者自己判断。

## 文件
- `PikPakRetriever.py`：源码，Python 标准库 only（tkinter GUI），不用 pip 装任何库。VERSION = "1.1.2"
- EXE：Windows 本地 `E:\磁力搜索\PIKPAK资源检索\PikPakRetriever-v1.1.2.exe`（约 13.3 MB，窗口标题栏显示 v1.1.2）。EXE 二进制不放在 GitHub（推送只支持 UTF-8 文本）。
- 旧版 v1.1.1 EXE 仍保留在同目录（MD5 `7e6834ba7750c6c6d265695731c41574`，12,882,416 字节），但**没有代理修复**，建议用 v1.1.2。

## 在 Windows 上跑
1. 直接双击 `PikPakRetriever-v1.1.2.exe`（无需装 Python，自带 tkinter）。
2. 或源码方式：装 Python 3.10+（官方包自带 tkinter），双击 `PikPakRetriever.py`。
3. 输入关键词 -> 点“聚合搜索” -> 勾选想要的 -> 点“导出已选为 CSV”。
4. 命令行：`python PikPakRetriever.py --cli 蜘蛛侠`，加 `--out 结果.csv` 直接导出。

导出 CSV 列：序号、资源名称、分类、PikPak分享链接、搜索关键词

## 来源
- DuckDuckGo：主力来源。**v1.1.2 修复了翻页**：改用页面真实偏移（每页 10 条），交错 202 反爬页会自动重试/跳过，不再误判“到底”。
- Bing RSS / Bing 网页：备用（Bing 对 `site:` 查询常不给 PikPak 直链）。
- Google：可选，多数网络下会触发 CAPTCHA，通了就有结果，不影响其他来源。

## v1.1.2 变更（WorkBuddy 本地实测修复）
1. **本地代理自动探测**：启动时探测 7890/7897/10809/1080/2080/10808，用 bing.com 验证，找到可用代理（如 Clash / FlClash）就走它，找不到则直连。解决了“系统代理通不了境外搜索源导致 0 条”的问题。**通用做法，不硬编码端口，别人机器照常工作。**
2. **DDG 翻页重写**：改用页面 `<input name="s" value="N">` 的真实偏移（每页 10 条），不再用 `page*30` 的错误步长；交错 202 限流页重试并跳过，不当成到底。
3. **“滚动到底”式加载**：一批不足 100 条不再提前报 0，会持续翻页直到来源确实没有更多（连续多轮无进展才停）。

## 关于 Chrome 检索（已评估，本环境不适用）
测试过 Chrome headless + 代理抓取 Google/DDG：DDG 仍返回 202 验证页，Google 跳转 google.com.hk 并触发 CAPTCHA。这是搜索引擎对代理出口 IP 的反爬，换浏览器 UA 无法绕过，且会破坏程序“零依赖”设计，故未采用。

## 打包成 EXE
`pyinstaller --onefile --windowed PikPakRetriever.py`（未签名，首次运行 Windows 可能弹 SmartScreen，点“更多信息”再点“仍要运行”）。

## 分工
- WorkBuddy：本地运行、验证、抓日志/报错；小修直接改源码（如 v1.1.2）。
- Muse：远程改代码、修解析逻辑；需要 Muse 改的在 Issue 交接备注写清现象+报错，标签改回 status:muse。
