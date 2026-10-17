# 四项目验收与自主推进记录

核验时间：2026-10-17 13:54 CST  
仓库：`pkwoksam4-web/dao-gp-agent`  
用途：保存本轮只读核验和下一步执行条件。状态只按可复核的分支、workflow、artifact、PR 和 checkpoint 判定。

## 总体结论

四条线均未产生能证明原研究假设的新结果。当前唯一实质新增研究准备证据是 DAO2-A 的 16-key D-status 诊断；它排除了通过状态/生命周期理由剔除残项的路线，但没有恢复任何 moneyflow 数值。运行次数、CI/Guard 成功和旧采集片段均不计作研究进展。

本记录不代表 production PASS、模型有效或交易授权。没有实施 production 写入、settlement、模型晋级、交易或 PR 合并。

## 项目验收

### 1. Agent 大脑

- 目标：以当时可见的 PIT 数据生成不可变的排名/观察，按精确交易日历成熟期核验判断价值。
- 当前基础证据：main 最新有关工作流仍为 2026-10-09（Ranking Shadow Settlement run `37909632595`；Runtime Bridge Static Check run `37910157945`）。2026-10-17 为周六，不是 A 股交易日；未找到 `runtime/pit-2026-10-17` 分支，也不应生成当日 manifest。
- 10-09 已有排名候选及 Core13 观察，不应说“没有任何判断输出”；但同一审计明确 `probability-v1.6` 未生成，原因是可执行定义缺失。排名是否达到研究问题要求，仍缺已冻结的基线、最低有效增益及完整结算口径。
- 10-16 的 5D 目标虽到期，但 PR #21 仍未合并；late-capture 规则未实施/复审，现有证据不足以将其报告为已结算结果。
- 方向：基础设施准备继续受门槛限制；研究合同仍未冻结，当前没有可确认的判断价值结论。
- 下步：下一正式交易日先按既有 preflight/16:18/16:30 门槛核验；未全部满足则当日 NON_LIVE。独立准备一页“冻结输出字段—精确目标日期—基线—最低有效增益—功效/样本规则”，所有数值门槛先验冻结后才开始确认性比较。概率公式不可猜。
- 可测验收：交易日 manifest 及13标的 PIT/ingest/观察 attestation 均可追溯；forecast 表不被伪造或改变；精确5D/20D成熟事件可分别复核。未冻结基线/门槛时结论标 UNFROZEN/INCONCLUSIVE。

### 2. BTC Shadow2 连续采样

- 目标：分别验证 Bridge、BID_DEPTH、QH、Crash、Funding 的前瞻信号，不因一个来源失败而把其他支路视为已评估。
- 当前证据：branch `btc-shadow2-rest-rescue-20261009` 最近 funding 实采为 run `38710415197`（2026-10-15），官方 endpoint 返回 HTTP 451，无 funding rows；原始响应与 SHA256 已归档。单元测试 5/5 通过只证明采集逻辑，不证明覆盖。检查到 2026-10-17 没有新运行。
- 方向：Funding 保持 `UNVERIFIED / NOT_PROMOTED`；不能重试同一受限 runner 或规避 provider 限制。其他支路必须单独按冻结 prereg/ledger 和各自数据质量 gate 验收。
- 下步与可测触发：
  - Bridge：取得合规运行实例、health/status、worker 与真实采样持久化引用；全部 gate PASS 才计有效输入。
  - BID_DEPTH：取到冻结 manifest、raw bookDepth、ledger/hash；精确应用已冻结决策桶和60m目标，只计合格 post-freeze 决策及已成熟目标。
  - QH：读取既有 prospective ledger、aggTrades archive/checksum，严守原假设/窗口；只报告独立成熟数，不为历史 pilot 扩样救结果。
  - Crash：metrics、fundingRate、premium、mark、index 五类原始源同一 PIT/连续性 gate 全通过才允许后续研究；否则维持 DATA_AUDIT_ONLY。
  - Funding：仅在出现预先批准且合规的官方源访问环境/载体后，保存原始请求、响应、UTC、哈希并对照冻结 expected events。
- 结论：没有新的支路研究结果；所有 promotion 和 PAPER 交易门保持关闭。样本不足或源缺失记 UNVERIFIED/INCONCLUSIVE，不记 0 或 PASS。

### 3. BTC Successor-B 重建

- 目标：以 canonical preregistration/ledger 定义 expected events，逐项证明多源历史数据覆盖、时间对齐和字段语义。
- 当前证据：`btc-successor-b-okx-gap-20261009` 最近采集仍为 10-09；10-14 offline grid audit 为局部采集质量证据：Binance nested archive 22/22 hash verified、无5m网格缺口；OKX 17页/1700原始行，目标区间1679行且无重复/网格缺口。
- 完整分支树仍未见 canonical preregistration、expected-event ledger、archive/worker 绑定引用。audit 自己也标出 `dataset_coverage_proven=false`，basis/OI semantics 未选定。
- 方向：局部完整性审计与起初目标一致；不能把它扩大解释为全数据集覆盖或重建完成。
- 下步：只接纳真实 canonical prereg/ledger/archive/worker refs；对每项记录 ref、commit/artifact、immutable hash，再将现有片段与 canonical expected events 做 exact coverage。没有规范 denominator 时，不报全量样本数。
- 可测验收：expected keys 全部来自 canonical ledger；逐键 source/hash/time/semantic checks 通过；basis/OI 使用已冻结定义。缺任一即保持 BLOCKED，不建替代 ledger、不跑 alpha/PnL/OOS/trading。

### 4. DAO2 主控 Agent 2

- 目标：在冻结 V4.82 Formal 合同下判断候选是否值得继续评估；缺失敏感性比较须在 scorer 身份及缺失处理规则权威、事前冻结后才可执行。
- 当前模块：
  - A / PR #15 HEAD `9790adcba73975575937a217dd2ab8e299d4ac7d`：16-key D-status audit run `38880076711`，artifact `12036928006`；ZIP SHA256 `a11d971bd13d1ed1d637429361f8b241ea34c9236da5760182ce72e168d52730`。诊断为 16/16 valid/tradable、11 ST、0 axis conflicts。moneyflow 仍 16 行 unresolved；期望/已解/未解保持 1,011,607/1,011,591/16。不得据此 N/A。
  - B / PR #16 HEAD `ddeddd1332fa785744006b28bdc75cece59802fb`：000985/raw breadth 为 PASS_SUBCOMPONENT；历史 final scorer 缺失，authoritative I/O 对仍为0。
  - C / PR #17 HEAD `aa6afc749f57efaaaaa4a43c22a9a86cfb3ed2ae`：42,783/43,084 authoritative rows admitted，301 缺失；298 derived-close 仍不准入，3 个 direct raw 801020.SI 日期未解。
  - D / PR #18 HEAD `2a7056ffd61885046e34dc1494bc668143d96793`：模块分支 PASS/FROZEN，Guard run `35499069982` 成功；未并入 main。
  - E / PR #19 等 A-D verified checkpoints；F / PR #20 等 E。两者继续 WAITING。
- PR #21 HEAD `2c5437c09269fccd223cccc9addb7a6454f95d73`，open/unmerged。日历成熟日修复的 CI run `38873186776` 14项通过；但最新 review `5545478529` 仍要求：（1）特征 lookback 按交易日历键验证完整连续性；（2）exact-target 的事后结果若补采，须单独冻结来源/价格口径/哈希和报告分类。不得自动合并。若由本任务承担实现，需在隔离分支修复、加针对性回归并提交 re-review 后再等人工合并。
- 方向：A 的状态诊断缩小了一个错误排除路径；其他模块没有新的权威数据或 scorer。当前不能回答缺失是否改变 E/F 结论，也不能自行静默排除或进入 OOS。
- 下步：A 使用 pinned known-value carrier 做残项所涉 ST 场景控制，然后仅在新 raw moneyflow carrier 通过已冻结 identity gate 后检查/准入目标值；B 仅等 final scorer 或唯一确定的权威同日 I/O；C 仅等覆盖精确冻结 301-key scope 的权威 raw export；D 冻结；E/F 不越级。
- 决策门：没有 authority-bound scorer 和事前 missingness policy 时，缺失敏感性问题标 BLOCKED/UNANSWERABLE，不猜公式、不造排除规则。

## 最小研究结论与样本规则

| 线 | 最小可回答问题 | 样本单位 | 当前是否可作否定性结论 |
|---|---|---|---|
| Agent Brain | 冻结排名对精确5D结果是否优于预先冻结基线；20D独立报告 | 预注册判断日/事件；相关标的不能当独立样本 | 否；基线、最低有效增益、功效合同未冻结 |
| Shadow2 | 每条支路的冻结信号能否提高各自预注册目标的区分/预测价值 | 分支独立的合格决策/事件及完整成熟目标 | 否；除历史 pilot 已有既定结果外，新 prospective 样本需按分支审核 |
| Successor-B | 现有数据是否覆盖 canonical ledger 的 expected events 且语义一致 | canonical expected key | 是/否必须逐键核验；当前 denominator 不可核验 |
| DAO2 | 冻结 V4.82 下候选是否达到继续评估门槛，缺失敏感性是否改变决策 | Formal trading-day/cohort，考虑面板依赖 | 否；权威 scorer 或缺失政策仍不完整 |

凡数值门槛未冻结，标 UNFROZEN；样本不足标 INCONCLUSIVE。不得在看新结果后调门槛或功效。

## 复评节点和唯一重启输入

**2026-10-23（北京时间）复评**：Agent Brain 看预测/排序合同与当日门槛证据；Shadow2 看各支路的新合规 raw carrier；Successor-B 看 canonical refs；DAO2 看 A raw carrier、B scorer/I-O、C vendor raw export。没有指定输入则将相应支线标为 WAITING_FOR_SPECIFIED_INPUT 或 PAUSED，停止重复失败探测。B 的历史 scorer 另保留 2026-10-31 recovery decision date，不延后10-23全项目复评。
