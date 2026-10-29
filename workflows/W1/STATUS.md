# W1 数据与证据 — STATUS

**状态：DRAFT_NOT_OWNER_RATIFIED / BOOTSTRAP_ONLY**  
**更新时间：2026-10-29 17:25 Asia/Shanghai**  
**主线只读基线：`main@bb43e5e9cb7a3727c4a0bf56494d534c2b63aecf`**  
**变更范围：`workflows/W1/`，非生产独立分支 `w1/governance-bootstrap-20261029`**

## 自上次以来的变化

- **VERIFIED**：本轮检查 `main` 的完整 Git tree（77 个路径），未见 `CHARTER.md`、`STATUS.md`、`DECISIONS.md`、`INTERFACES.md`；Google Drive/Library 的精确文件名检索亦未定位 W1 版；因此不能宣称本轮已经阅读过旧版治理文件。
- **VERIFIED**：在独立 W1 分支建立首次治理草案，保留 `DRAFT_NOT_OWNER_RATIFIED`；不修改 `main`。
- **VERIFIED**：2026-10-28 的只读预检状态为 `NON_LIVE`，授权 `FAIL_NOT_AUTHORIZED`、精确日期 manifest `MISSING`、31-session 日历计算 `PASS`、数据库覆盖与 same-day ingest `NOT_CHECKED`。该结果不得推广为 2026-10-29 已完成预检。[Issue #41](https://github.com/pkwoksam4-web/dao-gp-agent/issues/41)
- **VERIFIED**：权限 Issue #26 为 `PENDING_OWNER_DECISION`，原始 safety rule/error/blocked action 仍未取回。[Issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26)
- **VERIFIED**：只读观察器 PR #35 已合并；状态指针更新 PR #40 仍为 draft/open，不能等同主线文件已更新。[PR #35](https://github.com/pkwoksam4-web/dao-gp-agent/pull/35)、[PR #40](https://github.com/pkwoksam4-web/dao-gp-agent/pull/40)
- **INFERRED / STALE**：历史 DAO2-A `unresolved=16`、B `authoritative_pair_count=0`、C `admissible=42,783/43,084`、D `PASS/FROZEN` 为此前 checkpoint 摘要；本次未从对应完整原件重新核对，不能当作 10 月 29 日新进展。

## 本轮最小任务与完成标准

**Task W1-BOOT-001**：初始化可审查、不可误当作生效授权的 W1 治理文件。

验收测试事先写入 `tests/test_governance_contract.py`（先于本次四份治理文件提交）；标准：

1. `CHARTER.md`、`STATUS.md`、`DECISIONS.md`、`INTERFACES.md` 四文件可读取。
2. CHARTER 明确范围和 owner-only 禁止事项；DECISIONS 仅有 pending 项而不暗示已授权。
3. STATUS 有证据链接、`NOT_DONE`、`NEEDS_OWNER`、`INFERRED`、截止日；接口文件约束跨工作流只能走 interface issue。
4. 四文件保持 `DRAFT_NOT_OWNER_RATIFIED`，W1 分支与主线差异仅在 `workflows/W1/`；无生产库/凭据/合并/tag/访问限制绕过操作。
5. 回读 GitHub 文件及实际执行标准库测试，记录通过数与 commit SHA；未验证的条件保留 `NOT_DONE`。

**执行结果（2026-10-29 17:25 Asia/Shanghai）**：`PASS_SUBCOMPONENT / DRAFT_ONLY`。GitHub 已回读四份治理文件和一份预先提交的测试文件（5/5 可读）；基于回读字节的五类合同断言（文件、章程、状态、决策、接口）为 **5/5 PASS**。两端 Git tree 的 blob 对照仅新增 `workflows/W1/` 下五个文件，原 `main` 无任何 blob 变化。**NOT_DONE**：仓库中 Python unittest 未实际执行（当前容器无法解析 github.com，未触发任何 GitHub Actions）；不能把上述 JS 等价断言写成 Python CI 通过。治理文件尚未获负责人批准，故整体 `NOT_RATIFIED`。

## 未完成与阻塞

| 事项 | 状态 | 最小解除条件 |
| --- | --- | --- |
| W1 四文件正式归属与规则生效 | **NEEDS_OWNER** | 负责人确认路径/章程版本；不能由创建文件自动生效 |
| 2026-10-29 当日 PIT 原始状态核验 | **NOT_DONE** | 同日可审计 observer / manifest / run 原件；不得沿用前一日状态 |
| PIT 权限与安全原始证据 | **NEEDS_OWNER / NOT_DONE** | Issue #26 明示范围和原始 safety 记录；仅由负责人执行权限动作 |
| DAO2 A/B/C 最新原件复核 | **NOT_DONE / INFERRED** | 对应模块当前 HEAD、raw carrier、SHA 和 Guard；不接受历史摘要替代 |
| 跨工作流接口变更 | **NOT_DONE** | 真实变更需求后提单；不得自行修改其他工作流 |

## 需要负责人决定的事项及截止日

| 编号 | 决定 | 截止日 |
| --- | --- | --- |
| W1-D001 | W1 治理入口与职责边界确认（**NEEDS_OWNER**） | **2026-10-30，W1 提议** |
| W1-D002 | PIT 最小权限各项 `APPROVE/REJECT/REVISE`（**NEEDS_OWNER**；本文件不授权） | **2026-10-30，W1 提议** |
| W1-D003 | DAO2-B 权威历史 scorer 缺失时的路线选择（**NEEDS_OWNER**） | **2026-10-30，Issue #26 建议** |

本轮任何截止日都不作为自动批准或自动开启采集的条件。下一步仅在可验证的新证据出现后做 W1 内部增量核验。
