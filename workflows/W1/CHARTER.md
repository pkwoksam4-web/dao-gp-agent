# W1 数据与证据 — CHARTER

**治理状态：DRAFT_NOT_OWNER_RATIFIED**  
**创建日期：2026-10-29（Asia/Shanghai）**  
**存放路径：workflows/W1/**（暂定；需负责人确认）

## 使命与范围

W1 是数据与证据工作流：负责原始数据来源、采集/查询证据、时间戳、交易日历、PIT (point-in-time)、数据准入及其 provenance / hash / 版本链。当前工作对象包括 Agent Brain 的 PIT/采集证据、DAO2 A/B/C 历史数据缺口、DAO2-D Label/Status 冻结合同，以及 A 股历史成交数据证据。此范围依据负责人本轮指令及既有研究分工暂拟，**INFERRED**，不是独立授权。

W1 只负责本工作流内的数据身份、来源、覆盖与证据可复验，不对策略 Alpha、交易决策、模型权重、Shadow 结算做跨工作流修改。跨工作流数据合同变化仅提交 **interface issue** 并等待相关负责人决定。

## 可执行范围

- 读取公开或已合法授权且可访问的仓库、审计记录和数据说明；复核 source/UTC、交易日历、PIT、hash、manifest、admission gate。
- 在 W1 独立非生产分支编写最小测试、资料、只读核验与验收记录；不触发生产工作流。
- 先定义验收测试与完成标准，再实施一个可证伪的小任务；结束前更新 `STATUS.md`。
- 将 `PASS_SUBCOMPONENT`、`NON_LIVE`、`NOT_CHECKED`、`BLOCKED` 和 `PASS` 严格区分；只有当日可核验原件支持时升级状态。

## 负责人独占的动作 — W1 禁止执行

- **生产写入**（包括 Neon/正式库、LIVE PIT、结算及任何实际交易相关写路径）
- **凭据操作**（创建、读取、修改、传输密钥、Secret、数据库角色授权）
- **合并 PR**
- **创建 tag**
- **绕过访问限制**或使用未经许可的数据入口

上述动作只由用户本人执行；Issue、草案、CI、只读观察或文档不构成授权。

## 证据分级

- **VERIFIED**：有原件、UTC/时区、不可变定位符、原始哈希或 Git commit、可重复核验的合同与来源。
- **INFERRED**：来自历史摘要或尚未当日重新读取的状态；不可用作新的准入证明。
- **NOT_DONE**：测试/取证或核验尚未执行。
- **NEEDS_OWNER**：需要用户做权限、路径、冻结规则或合并等决定。

每次 W1 汇报第一行固定为“自上次以来的变化”。若四份治理文件任何一份不可读，先记录异常，不假称治理已通过。

## 当前控制依据

- [PIT owner authorization issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26)
- [2026-10-28 observe-only status #41](https://github.com/pkwoksam4-web/dao-gp-agent/issues/41)
- [main status pointer](https://github.com/pkwoksam4-web/dao-gp-agent/blob/main/docs/PROJECT_STATUS_POINTER.md)
- [W1 当前状态](STATUS.md)、[决策](DECISIONS.md)、[接口](INTERFACES.md)

**冻结声明：本文件是建议章程，非旧项目章程的已验证替代品；待负责人确认。**
