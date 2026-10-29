# W1 — INTERFACES

**状态：DRAFT_NOT_OWNER_RATIFIED**  
本工作流只发布数据与证据合同，不修改其他工作流。

## 输出接口（提案，INFERRED）

| 接口 | W1 提供 | 下游使用条件 | 当前边界 |
| --- | --- | --- | --- |
| PIT 原始证据 | `trade_date`、source/ref、UTC 时间、`manifest_sha256`、commit/run ref、原始资料及 provenance | 当日 exact manifest、权限/安全、31-session、ingest 四门依序全部满足 | 2026-10-28 `NON_LIVE`；不可向下游声明 `LIVE_PIT` |
| DAO2 A/B/C 准入 | symbol-date 键集、原始载体、字段/单位、SHA-256、source permission、准入/缺口原因 | 各模块冻结身份合同通过才可出具 `PASS` | 缺口不得由近似值、反演、derived-close 升格 |
| DAO2-D 状态 | label/status 冻结合同 checkpoint 与代码/测试证据 | 上游验收方只读消费冻结 checkpoint | 不在 W1 修改其他模块或扩大 D 语义 |
| W1 变更事件 | changed-since-last、evidence ref、测试结果、`NOT_DONE` / `NEEDS_OWNER` / `INFERRED` | 其他工作流自行决定是否消费 | 报告不是授权，不是模型晋级 |

## 跨界交付协议

发现会影响其他工作流时，只创建或提议 **interface issue**，包含：
- `producer=W1`、`consumer=<具体工作流>`、`contract_version`；
- frozen 输入/输出 schema、时区、source、`provenance`、hash、不可变定位；
- 破坏性变化清单、失败时的 fail-closed 状态、最小验收测试；
- 需要哪个负责人批准、明确截止日。

未经双方负责人书面确认，**不修改其他工作流** 的模型、策略、settlement、运行工作流、生产数据库或其治理文件。无法确定 consumer 的接口先标 `INFERRED/NEEDS_OWNER`，不得自行指定其负责人。

## 已知待接口事项

- Agent Brain 的 PIT writer/reader 授权与生产执行属于 owner-only；[Issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26) 是权限请求而非授权。
- Shadow/settlement 的变更由独立 draft [PR #32](https://github.com/pkwoksam4-web/dao-gp-agent/pull/32) 承载；W1 不更改其执行面。
- W1 尚未提交独立的跨工作流 interface issue：`NOT_DONE`，仅在真实的合同变更请求出现后创建。
