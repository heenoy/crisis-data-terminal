# Project Status / 项目状态

> This document records the **current state** of major Crisis Data Terminal project areas.
>
> 本文档记录 Crisis Data Terminal 主要模块的**当前状态**。
>
> It is not a changelog or development diary.
>
> 它不是 Changelog，也不是开发日志。
>
> Status should only change when supported by explicit project decisions or authoritative project documentation.
>
> 只有在项目已有明确决定或权威项目文档支持时，才修改状态。

---

# 1. Frozen / 已冻结

Frozen areas must not be modified, overwritten, or redefined unless the current task explicitly authorizes such changes.

Frozen 区域不得被修改、覆盖或重新定义，除非当前任务明确授权。

## Final Prediction Model / 最终预测模型

- Final Random Forest prediction pipeline
- 最终 Random Forest 预测 Pipeline

- Locked 15-feature definition
- 已锁定的 15 个预测特征定义

- Final preprocessing behavior associated with the frozen pipeline
- 与冻结 Pipeline 对应的最终预处理行为

- Target definition:
  - Low: 0–9 deaths
  - Moderate: 10–99 deaths
  - Severe: ≥100 deaths
- 目标类别定义：
  - Low：0–9 人死亡
  - Moderate：10–99 人死亡
  - Severe：≥100 人死亡

- Class order:
  - Low
  - Moderate
  - Severe
- 类别顺序：
  - Low
  - Moderate
  - Severe

- Strict temporal final evaluation strategy and final held-out test evaluation
- 严格时间划分的最终评估策略及最终留置测试结果

- Frozen model artifact and corresponding manifest/checksum
- 冻结模型产物及对应 Manifest / Checksum

Experimental model work must not overwrite these artifacts.

实验模型不得覆盖上述冻结产物。

---

# 2. Stable / 已稳定

Stable areas are established project behavior or architecture.

Stable 区域表示已经确认的项目行为或架构。

Ordinary tasks should preserve them unless the task explicitly requests a redesign or architectural change.

普通任务应保持这些内容，除非当前任务明确要求重新设计或修改架构。

## Technology Stack / 技术栈

- Vite + Vanilla JavaScript frontend
- Vite + Vanilla JavaScript 前端

- ECharts / Three.js visualization stack
- ECharts / Three.js 可视化技术栈

- Supabase + PostgreSQL backend/data layer
- Supabase + PostgreSQL 后端 / 数据层

- Python model-inference API
- Python 模型推理 API

- Vercel deployment
- Vercel 部署

## Routing / 路由

- Existing Hash Router strategy
- 当前 Hash Router 路由策略

## Impact Analysis Contracts / 影响等级分析契约

- Prediction input-option retrieval and prediction execution are separate responsibilities.
- 预测输入选项获取与预测执行保持职责分离。

- `GET /api/impact-options` is responsible for prediction input options.
- `GET /api/impact-options` 负责提供预测输入选项。

- Prediction requests use the established prediction API contract.
- 预测请求遵循已经建立的预测 API 契约。

- Prediction class order remains:
  `Low / Moderate / Severe`
- 预测类别顺序保持：
  `Low / Moderate / Severe`

## Production Authentication and Data Access / 生产认证与数据访问

- Production authentication uses Supabase Auth sessions. User-visible profile data remains separate from authorization claims.
- 生产认证使用 Supabase Auth Session。用户可编辑的资料信息与授权 Claim 保持分离。

- Administrator authorization is derived from trusted `app_metadata.role = "admin"`; forged browser storage does not grant administrator access.
- 管理员授权来自可信的 `app_metadata.role = "admin"`；伪造浏览器存储不能获得管理员权限。

- Production Data API access is protected by GRANT and RLS: authenticated users can read disaster data, while controlled writes require the administrator role.
- 生产 Data API 由 GRANT 与 RLS 共同保护：已认证用户可读取灾害数据，受控写入仅允许管理员角色。

- The legacy `app_users` table and credential fields are deprecated and retained only for audit. They have no active application-authentication path, client policies, or Data API grants; physical deletion requires separate approval.
- 旧 `app_users` 表及凭据字段已标记 Deprecated，仅为审计保留。当前不存在应用认证调用、客户端 Policy 或 Data API Grant；物理删除仍需单独批准。

## User-facing Navigation / 用户端导航

- User-facing pages follow the established project navigation strategy.
- 用户端页面遵循当前已经确立的项目导航策略。

- Main navigation should remain consistent across user-facing routes unless explicitly redesigned.
- 除非明确重新设计，否则用户端各路由的主要导航逻辑应保持一致。

## Product Identity / 产品身份

- CRT / terminal-inspired visual identity is an established project direction.
- CRT / Terminal 风格是已经确定的项目视觉方向。

- VAULT-0 is an established system identity and AI interaction concept.
- VAULT-0 是已经确定的系统身份和 AI 交互概念。

These identities are stable even when their individual UI implementations remain experimental.

即使具体 UI 实现仍处于实验阶段，这些产品身份本身仍属于稳定方向。

---

# 3. Experimental / 实验中

Experimental areas may undergo larger refactoring, redesign, replacement, or evaluation changes when justified.

实验区域在有充分理由时允许进行较大范围的重构、重新设计、替换或评估调整。

Experimental status does not override Frozen boundaries.

实验状态不能覆盖 Frozen 边界。

## Admin UI / 管理端 UI

Admin UI and visual design remain experimental.

管理端 UI 和视觉设计仍处于实验阶段。

Stage 4.3-A of the administrator model archive is completed and deployed. It provides a read-only view of the sole Production RF-T2 model and traceable experiment results. Model switching, upload, training, deletion, and deployment controls are not implemented; the page does not change the frozen model-governance boundary, and the broader Admin UI remains Experimental.

管理员模型档案4.3-A已完成并发布：页面只读呈现唯一Production的RF-T2与可追溯实验结果。模型切换、上传、训练、删除和部署控制均未实现；该页面不改变冻结模型治理边界，管理端UI整体仍为Experimental。

Stage 4.4 of the administrator system-status page is completed and deployed. It provides on-demand, read-only checks for the Data API, prediction API, and manually triggered AI generation verification; it does not provide continuous monitoring, alerting, historical status storage, or runtime-resource telemetry. The broader Admin UI remains Experimental.

管理员系统状态页4.4已完成并发布：页面提供Data API、预测API及管理员手动触发AI生成验证的按需只读检查；不提供持续监控、告警、历史状态存储或运行时资源遥测。管理端UI整体仍为Experimental。

Possible changes include:

- layout;
- visual hierarchy;
- typography;
- panel design;
- interaction details;
- responsive behavior.

允许继续调整：

- 布局；
- 视觉层级；
- 字体；
- 面板设计；
- 交互细节；
- 响应式行为。

## Prediction Model Testing and Evaluation / 预测模型测试与评估

Model testing and evaluation remain open to experimentation.

模型测试和评估仍允许继续实验。

Possible experimental work includes:

- additional model comparisons;
- evaluation visualization;
- error analysis;
- validation methodology analysis;
- thesis-oriented comparative experiments.

可继续进行：

- 额外模型比较；
- 评估可视化；
- 错误分析；
- 验证方法分析；
- 面向论文的比较实验。

This does not authorize modification of the Frozen final prediction pipeline or final held-out test results.

这不代表允许修改 Frozen 的最终预测 Pipeline 或最终留置测试结果。

## Cross-page VAULT-0 Integration / VAULT-0 跨页面整合

The overall VAULT-0 identity is Stable.

VAULT-0 的整体角色身份属于 Stable。

However, its cross-page implementation remains Experimental.

但 VAULT-0 的跨页面具体实现仍处于 Experimental。

Experimental areas include:

- placement;
- shared component behavior;
- route-transition behavior;
- message presentation;
- interaction timing;
- page-specific integration.

仍可调整：

- 位置；
- 共享组件行为；
- 路由切换行为；
- 消息呈现方式；
- 交互时机；
- 不同页面中的整合方式。

Avoid introducing multiple conflicting VAULT-0 instances.

避免产生多个互相冲突的 VAULT-0 实例。

## Visualization Performance / 可视化性能

Three.js and ECharts remain established technologies.

Three.js 和 ECharts 仍属于既定技术。

Their performance optimization strategy remains Experimental.

但具体性能优化方案仍处于 Experimental。

Possible work includes:

- bundle optimization;
- lazy loading;
- rendering optimization;
- data-processing optimization;
- reducing unnecessary redraws;
- evaluating whether expensive visual effects are justified.

可继续探索：

- Bundle 优化；
- Lazy Loading；
- 渲染优化；
- 数据处理优化；
- 减少无意义重复绘制；
- 评估高开销视觉效果是否值得保留。

Optimization should not automatically remove established product identity.

性能优化不能默认以删除既定产品视觉身份为代价。

---

# 4. Project-wide Constraints / 项目级约束

The following constraints apply across module boundaries.

以下约束跨模块生效。

## Model Integrity / 模型完整性

- Do not use post-event outcomes as prediction inputs.
- 不使用灾害发生后的结果变量作为预测输入。

- Do not use the final held-out test set for tuning.
- 不使用最终留置测试集调参。

- Experimental models must use separate artifacts.
- 实验模型必须使用独立产物。

## Verification Integrity / 验证真实性

- Verification claims must come from actual execution.
- 验证结论必须来自真实执行。

- Do not report expected behavior as verified behavior.
- 不把“理论上应该工作”描述成“已经验证”。

## UI Identity / UI 身份

- Preserve the CRT / terminal-inspired product identity.
- 保留 CRT / Terminal 产品视觉身份。

- Preserve VAULT-0's intentional system character.
- 保留 VAULT-0 有意设计的系统角色感。

- Usability improvements should refine these identities rather than automatically remove them.
- 可用性优化应优先改善这些设计，而不是默认删除它们。

## Error Transparency / 错误透明性

- Do not fabricate successful states.
- 不伪造成功状态。

- Graceful degradation must remain honest and diagnosable.
- 合理降级必须真实，并且不能妨碍错误诊断。

---

# 5. Status Maintenance Rules / 状态维护规则

This document should remain concise.

本文档应保持简洁。

Update it only when a major project area's status actually changes.

只有主要项目区域的状态真正发生变化时才更新。

Do not update it for:

- ordinary bug fixes;
- small UI adjustments;
- copy changes;
- routine refactoring.

以下情况不更新：

- 普通 Bug 修复；
- 小型 UI 修改；
- 文案修改；
- 常规重构。

Do not automatically move an Experimental area to Stable merely because one task was completed successfully.

不能因为某一次任务完成并验证通过，就自动将整个 Experimental 模块移动到 Stable。

Do not automatically mark an artifact Frozen merely because it currently works.

不能因为某个产物当前能够工作，就自动将其标记为 Frozen。

When status changes:

- move the relevant item to the correct section;
- remove outdated status descriptions;
- describe the resulting current state;
- do not accumulate historical entries.

状态发生变化时：

- 将对应项目移动到正确分类；
- 删除已经过时的状态描述；
- 描述修改后的当前状态；
- 不在这里不断累积历史记录。

Detailed development history belongs in thesis/stage documentation, not here.

详细开发历史应放入论文 / 阶段文档，而不是本状态文件。
