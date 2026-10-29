# W1 — DECISIONS

**状态：DRAFT_NOT_OWNER_RATIFIED**  
本文件记录待决项，不构成授权。所有日期为北京时间（Asia/Shanghai）。

| ID | 决策与最小可验证输出 | 当前状态 | 截止日 | 依据 |
| --- | --- | --- | --- | --- |
| W1-D001 | 确认 W1 职责边界及 `workflows/W1/` 四文件是否作为正式治理入口；只认可路径/边界，不自动批准运行或写入 | **PENDING_OWNER_DECISION / NEEDS_OWNER** | **2026-10-30（W1 提议）** | 用户 2026-10-29 指令；本分支首次初始化 |
| W1-D002 | 对 PIT 最小权限分别选 `APPROVE / REJECT / REVISE`，并写明合法载体、表/日期边界、失效条件；不得在此记录凭据值 | **PENDING_OWNER_DECISION / NEEDS_OWNER** | **2026-10-30（W1 提议，并非既定授权期限）** | [Issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26) |
| W1-D003 | DAO2-B 历史 scorer 权威载体若仍缺失，确认结束历史身份恢复路径或仅启动严格独立的 successor contract；不得拟合历史公式 | **PENDING_OWNER_DECISION / NEEDS_OWNER** | **2026-10-30（#26 中建议）** | [Issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26) |
| W1-D004 | 若后续需改动非 W1 合同/执行面，由对应工作流负责人以 `interface issue` 协商；本分支不跨界修改 | **PENDING_INTERFACE_NEED / NOT_DONE** | **触发时（尚无具体跨工作流请求）** | [INTERFACES.md](INTERFACES.md) |

## 决策日志规则

1. 仅有负责人明确指令及对应原始记录时才能将 `PENDING_OWNER_DECISION` 改为 `APPROVED` / `REJECTED` / `REVISE`。
2. 时间到期但没有签署决定，标 `EXPIRED_UNDECIDED` 或继续 `NEEDS_OWNER`，不得默认批准。
3. 本文件的草案提交不是生产写入授权；已知 Issue #26 中 `rule_id`、`error_message`、`blocked_action` 仍需取回原件。
