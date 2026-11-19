# Muse ↔ WorkBuddy 协作协议

本文件是双方的"共同契约"。Muse 与 WorkBuddy 都通过同一个 GitHub 仓库的 Issues 读写任务，
彼此不直接通信。任何一方接手任务前，先读本文件。

---

## 1. 分工原则

| 执行方 | 擅长 | 典型任务 |
|---|---|---|
| **Muse**（Meta，云端 VM） | 网页操作、消费级跨平台、后台长跑 | 比价购物、订票、填表、发邮件、整理收件箱、监控网页并异步推进 |
| **WorkBuddy**（腾讯，本地+云） | 文档表格、代码、企业系统、腾讯生态、定时自动化 | 写 Word/PPT/Excel、改代码、读写腾讯文档/会议/网盘、定时轮询、本地文件处理 |

派单原则：**谁擅长派给谁**。需要网页/外部消费服务的给 Muse，需要产出文档/代码/结构化数据的给 WorkBuddy。
跨界任务拆成两个 Issue 接力。

---

## 2. 标签体系（label）

任务流转完全靠标签驱动，标签名固定，不要自造。

### 状态标签（互斥，同时只能有一个 `status:*`）

| 标签 | 含义 |
|---|---|
| `status:new` | 新任务，待调度 |
| `status:muse` | 已派给 Muse |
| `status:workbuddy` | 已派给 WorkBuddy |
| `status:doing` | 执行方已接手，进行中 |
| `status:review` | 已完成，待用户验收 |
| `status:blocked` | 阻塞，需在评论说明原因 |
| `status:done` | 验收通过，归档 |

### 类型标签（可选，可多个）

`type:research`（调研）、`type:web`（网页操作）、`type:doc`（文档）、
`type:code`（代码）、`type:data`（表格/数据）、`type:schedule`（定时任务）

### 优先级标签（可选）

`priority:high`、`priority:low`。无标签视为普通。

---

## 3. Issue 模板

新建任务 Issue 必须包含以下四个小节，标题以 `[任务]` 开头：

```markdown
## 目标
一句话说清要达成什么结果。

## 背景
必要的上下文、链接、素材位置。

## 验收标准
- 可勾选的具体条件，执行方据此判断做完没有。

## 交接备注
跨方接力时填：前一方做到哪一步、产物在哪、下一步该谁接。无则写"无"。
```

---

## 4. 流转规则

1. **建单**：任何人（用户 / Muse / WorkBuddy）可建 Issue，打 `status:new` + 类型标签。
2. **派单**：把 `status:new` 换成 `status:muse` 或 `status:workbuddy`，或在评论里 @ 指派并改标签。
3. **接手**：执行方在该 Issue 评论一条"已接手"，把标签换成 `status:doing`。
4. **交接**：Muse 做完属于自己那段但需 WorkBuddy 续做 → 在"交接备注"写清产物位置与下一步，
   标签换成 `status:workbuddy`；反向同理换 `status:muse`。
5. **完成**：执行方在评论写结果（产物链接/关键结论），标签换成 `status:review`。
6. **验收**：用户确认后换成 `status:done`；不合格则打回 `status:doing` 并说明。
7. **阻塞**：遇权限/登录/支付等卡点，换 `status:blocked` 并在评论写明需要用户做什么。

---

## 5. 轮询机制

- **WorkBuddy**：配置了定时任务，定期扫描 `status:workbuddy` 和 `status:doing`（自己名下）的 Issue，
  发现新任务即按协议执行。
- **Muse**：在对话中设定"定期检查仓库里 `status:muse` 的 Issue"，或由用户转发任务时触发。
  Muse 具备后台持续运行与主动感知能力，可承担异步推进。
- 双方**只处理标签指向自己**的任务，不要动对方的，避免抢单。

---

## 6. 约定与禁忌

- 标签是唯一的任务状态来源，评论里的话不改状态。
- 敏感操作（付款、发外部邮件、删除）按各自平台的安全流程走，Muse 会请求确认，WorkBuddy 会记录日志。
- 凭证不写进 Issue 或本文件。
- 一方失败要显式换 `status:blocked`，不要静默搁置。
