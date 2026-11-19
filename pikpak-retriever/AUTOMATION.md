# 自动化闭环：WorkBuddy 跑测试 → 出问题自动派给 Muse

目标：不用用户当传话人。WorkBuddy 定时在本地真机跑测试，发现问题就
自动在仓库里建一个 `status:muse` 的 Issue，Muse 每小时轮询到就接手修，
修完把标签改成 `status:workbuddy` 等 WorkBuddy 复测，形成闭环。

## 闭环图

```
WorkBuddy 定时任务（每小时 / 每天）
  1. git pull muse-workbuddy-pool
  2. cd pikpak-retriever && python test_pikpak.py --live 蜘蛛侠
     -> 生成 TEST_REPORT.md（离线 PASS/FAIL + 真网各来源条数 + DDG 无标题比例）
  3. 离线全过 + 真网没崩 -> 在 Issue #3 评论“本地实机测试通过 …”，标签改 status:review
  4. 离线有失败 / 真网崩了 / DDG 无标题 > 50%
     -> 新建 Issue，标签 status:muse + type:code，标题：
        [任务] PikPak 测试失败：<失败的测试名 / 现象>
        正文按 PROTOCOL.md 的四节写，附上 TEST_REPORT.md 全文，
        有 ddg_debug.html 就说明文件在程序旁边，贴出前 20 行关键结构
     -> 标签不用改成 doing，等 Muse 接手
Muse 定时任务（每小时，cron muse-workbuddy-pool-check）
  1. 查 status:muse 的 Issue
  2. 评论“已接手”，标签改 status:doing
  3. 修代码，把新版 PikPakRetriever.py 推到 pikpak-retriever/
  4. 评论修了什么、怎么验证，标签改 status:workbuddy（等复测）
     或问题已解决且不用复测时改 status:review
WorkBuddy 下一次定时跑
  1. git pull 拿到新版代码，重新跑 test_pikpak.py --live 蜘蛛侠
  2. 通过 -> 原 Issue 评论通过，标签改 status:review；不通过 -> 再建 status:muse Issue
```

## WorkBuddy 那边怎么设定时任务

在 WorkBuddy 里新建一个定时任务，频率每小时（高频期）或每天一次，
命令（Windows，仓库已 clone 到本地，比如 `D:\muse-workbuddy-pool`）：

```bat
cd /d D:\muse-workbuddy-pool
git pull
cd pikpak-retriever
python test_pikpak.py --live 蜘蛛侠
```

跑完不要只看退出码，要读 `TEST_REPORT.md`：
- 离线测试有“失败/出错” -> 按上面第 4 步建 Issue
- 真网冒烟里 DDG 无标题比例 > 50% -> 建 Issue，附 ddg_debug.html
- 全过 -> 在 Issue #3 评论通过并改 status:review

WorkBuddy 建 Issue 时必须用 PROTOCOL.md 的模板：
标题以 `[任务]` 开头，正文含 目标 / 背景 / 验收标准 / 交接备注，
标签只能有一个 `status:*`，这里是 `status:muse`。

## Muse 这边

- 定时任务 `muse-workbuddy-pool-check` 每小时查一次 `status:muse`，
  无新任务时静默，有任务时按 PROTOCOL 接手、修、交回。
- 修代码只改 `pikpak-retriever/PikPakRetriever.py`，同时更新
  `test_pikpak.py` 里对应的回归用例（失败的场景要变成一个新测试，
  下次跑测试就能拦住，不许修完不补测试）。
- 敏感操作（付款、发外部邮件、删除）不自动做，按审批流程走。

## 一键脚本

Windows 双击 `run_tests.bat` 就等于上面第 2 步，跑完打开 TEST_REPORT.md。
