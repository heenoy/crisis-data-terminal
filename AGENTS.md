# AGENTS.md

> **Language / 语言说明**
>
> English is the primary instruction language for coding agents.  
> Chinese translations are provided for the project owner and should be interpreted as equivalent explanations of the English rules.
>
> 英文是面向 Codex 等编码代理的主要规则语言。  
> 中文用于项目负责人阅读理解，与对应英文规则表达相同意图。
>
> If the English and Chinese wording ever appears inconsistent, follow the project owner's explicit current-task instruction first, then use the English rule as the operational interpretation.
>
> 如果中英文表述出现歧义，优先遵循项目负责人在当前任务中的明确要求；其次以英文规则作为代理执行时的操作性解释。

---

# 1. Project Purpose and Priorities
# 1. 项目目标与优先级

This repository contains **Crisis Data Terminal**, a graduation project focused on:

- disaster-event data management;
- data visualization and analysis;
- AI-assisted inquiry;
- disaster impact-level analysis.

本仓库包含毕业设计项目 **Crisis Data Terminal**，主要功能包括：

- 灾害事件数据管理；
- 数据可视化与分析；
- AI 辅助问询；
- 灾害影响等级分析。

The established technology stack is:

- Frontend: Vite + Vanilla JavaScript
- Visualization: ECharts + Three.js
- Backend / Database: Supabase + PostgreSQL
- Model inference: Python API
- AI capabilities: external LLM API
- Deployment: Vercel

当前既定技术栈为：

- 前端：Vite + Vanilla JavaScript
- 可视化：ECharts + Three.js
- 后端 / 数据库：Supabase + PostgreSQL
- 模型推理：Python API
- AI 能力：外部 LLM API
- 部署：Vercel

When making engineering decisions, prioritize:

1. Correctness
2. Maintainability
3. Reproducibility
4. UI and interaction consistency
5. Thesis explainability
6. Simplicity

进行工程决策时，按照以下顺序考虑：

1. 正确性
2. 可维护性
3. 可复现性
4. UI 与交互一致性
5. 毕业论文中的可解释性
6. 简洁性

Do not introduce unnecessary architecture, dependencies, abstractions, or infrastructure merely to make the project appear more sophisticated.

不要仅仅为了让项目显得更加复杂或“高级”，而引入不必要的架构、依赖、抽象层或基础设施。

Do not migrate frameworks or replace the established technology stack unless explicitly requested.

除非当前任务明确要求，否则不要迁移框架或替换既定技术栈。

---

# 2. Sources of Truth and Module Status
# 2. 项目状态与事实来源

The current status of major project areas is recorded in:

`docs/project-status.md`

项目主要模块的当前状态记录在：

`docs/project-status.md`

This file distinguishes project areas that are:

- Frozen
- Stable
- Experimental

该文件用于区分：

- Frozen：冻结
- Stable：稳定
- Experimental：实验中

Read `docs/project-status.md` before making changes that may affect:

- architecture;
- frozen artifacts;
- stable behavior;
- major interfaces or contracts;
- experimental modules.

如果任务可能影响以下内容，应先读取 `docs/project-status.md`：

- 系统架构；
- 冻结产物；
- 已稳定行为；
- 重要接口或数据契约；
- 实验性模块。

Do not infer a module's status solely from:

- unfinished code;
- TODO comments;
- visual inconsistency;
- temporary implementations;
- incomplete documentation.

不要仅仅因为以下现象就自行判断模块状态：

- 代码尚未完成；
- 存在 TODO；
- UI 不一致；
- 存在临时实现；
- 文档尚未完善。

A module may be experimental even when it already works.

即使一个模块已经能够正常运行，它仍然可能处于实验阶段。

A module may also contain frozen components while the broader module remains experimental.

一个整体仍处于实验阶段的模块，也可能包含已经冻结、不能随意修改的内部内容。

Experimental status permits broader iteration, refactoring, replacement, or redesign when justified.

实验状态意味着在有充分理由时，可以进行更大范围的迭代、重构、替换或重新设计。

Experimental status does **not** override explicitly frozen artifacts, interfaces, data contracts, confirmed requirements, or final deliverables.

实验状态**不能覆盖**明确冻结的产物、接口、数据契约、已确认需求或最终交付结果。

---

# 3. Architecture and Technology Boundaries
# 3. 架构与技术边界

Understand the existing implementation before introducing a new solution.

在引入新方案之前，先理解现有实现。

Do not create parallel implementations of the same responsibility unless explicitly required.

除非明确需要，否则不要为同一职责建立两套并行实现。

Respect the existing architecture and responsibility boundaries.

尊重当前已经建立的架构和职责边界。

## Frontend / 前端

Frontend responsibilities include:

- UI rendering;
- user interaction;
- routing;
- visualization integration.

前端主要负责：

- UI 渲染；
- 用户交互；
- 路由；
- 可视化集成。

Do not introduce another frontend framework unless explicitly requested.

除非明确要求，否则不要引入新的前端框架。

## Backend and API / 后端与 API

Backend responsibilities include:

- server-side operations;
- secure operations;
- model inference communication;
- API behavior.

后端主要负责：

- 服务端操作；
- 需要安全边界的操作；
- 模型推理通信；
- API 行为。

Do not move server-side responsibilities or secrets into frontend code.

不要把服务端职责或服务端密钥转移到前端代码中。

## Database / 数据库

Supabase / PostgreSQL remain responsible for persistent relational data and access control.

Supabase / PostgreSQL 继续负责持久化关系数据与访问控制。

## Visualization / 可视化

ECharts and Three.js are established visualization technologies in this project.

ECharts 和 Three.js 是本项目已经采用的可视化技术。

Do not replace them without a clear technical reason or explicit instruction.

没有明确技术理由或当前任务要求时，不要随意替换。

---

# 4. Engineering Rules and Change Scope
# 4. 工程规则与修改范围

Before modifying code:

1. Locate the existing implementation.
2. Understand current behavior.
3. Identify the actual requirement or root cause.
4. Identify affected modules and dependencies.
5. Determine whether the affected area is Stable, Experimental, or Frozen.
6. Choose the smallest coherent change that solves the problem.

修改代码之前：

1. 找到现有实现；
2. 理解当前行为；
3. 确认真实需求或问题根因；
4. 确认受影响模块和依赖；
5. 判断涉及区域属于 Stable、Experimental 还是 Frozen；
6. 选择能够完整解决问题的最小合理修改。

Prefer the simplest implementation that fully satisfies the current requirement.

优先选择能够完整满足当前需求的最简单实现。

Fix root causes instead of layering temporary patches.

优先修复根因，而不是不断叠加临时补丁。

Avoid:

- duplicate logic;
- speculative abstractions;
- premature generalization;
- unrelated refactoring;
- unnecessary dependencies;
- silent changes to unrelated behavior.

避免：

- 重复逻辑；
- 为未来可能需求提前设计抽象；
- 过早泛化；
- 与当前任务无关的重构；
- 不必要的依赖；
- 静默改变无关功能。

## Simplicity and Defensive-Code Budget / 简洁性与防御性代码预算

This is a student graduation project, not a large-scale commercial or high-availability production system.

这是一个学生毕业设计，不是大型商业系统或高可用生产系统。

Prefer concise, direct, readable implementations over defensive code designed for unlikely edge cases.

与为低概率边缘情况设计的防御性代码相比，优先选择简洁、直接、易读的实现。

Code should earn its complexity. Do not add defensive logic merely because a failure is theoretically possible.

代码复杂度必须有实际价值作为理由。不要仅因为某种失败在理论上可能发生，就添加防御性逻辑。

Every fallback, retry path, compatibility layer, wrapper, state branch, or abstraction must solve a realistic problem in this project.

每一个 fallback、重试路径、兼容层、包装器、状态分支或抽象层，都必须解决本项目中真实存在或合理可能出现的问题。

For non-critical failures, prefer a clear failure state over multiple layers of fallback behavior.

对于非关键失败，优先使用清晰的失败状态，而不是叠加多层 fallback 行为。

When a simpler implementation is sufficient, prefer fewer branches, fewer files, fewer layers, and fewer lines of code. Do not optimize for physical line count at the expense of readability. Treat unnecessary code as technical debt.

当更简单的实现已经足够时，优先减少分支、文件、层级和代码。不要为了减少物理代码行数而牺牲可读性。将不必要的代码视为技术债务。

Before adding a fallback or defensive branch, ask:

1. Has this failure actually occurred or is it reasonably likely in this project?
2. Does it affect a core user flow?
3. Can the failure be handled more simply by showing an explicit error?
4. Is the added complexity larger than the value it provides?

添加 fallback 或防御性分支之前，应先问：

1. 这种失败是否已经发生，或者在本项目中是否合理可能发生？
2. 它是否影响核心用户流程？
3. 是否可以通过显示明确错误，以更简单的方式处理？
4. 新增复杂度是否大于它带来的价值？

Do not introduce:

- speculative fallback data;
- multiple retry mechanisms for the same request;
- compatibility code for obsolete implementations;
- redundant null or undefined checks when upstream contracts already guarantee the value;
- wrappers that only forward arguments without adding meaningful behavior;
- duplicated state machines for rare failure conditions;
- abstractions used only once without a clear readability benefit;
- defensive branches added only for theoretical edge cases;
- silent recovery paths that make failures harder to diagnose.

不要引入：

- 为未经证实的情况猜测并生成的 fallback 数据；
- 针对同一请求的多套重试机制；
- 为已废弃实现保留的兼容代码；
- 在上游契约已保证值存在时，重复添加 null 或 undefined 检查；
- 仅转发参数、不增加有意义行为的包装器；
- 为罕见失败情况复制状态机；
- 没有明确可读性收益、且只使用一次的抽象；
- 仅针对理论边缘情况添加的防御性分支；
- 使失败更难诊断的静默恢复路径。

Prefer the control flow:

`request -> validate -> success / clear error`

over:

`request -> retry -> fallback -> compatibility path -> placeholder -> silent recovery`

优先使用以下控制流：

`请求 -> 验证 -> 成功 / 明确错误`

而不是：

`请求 -> 重试 -> fallback -> 兼容路径 -> 占位 -> 静默恢复`

Reducing complexity does not override essential security or correctness. It must not expose API keys, service-role keys, tokens, or passwords; move server-only secrets into frontend code; disable or weaken RLS for convenience; compromise data integrity; alter Frozen models or prediction contracts; remove model rules that prevent data leakage; or fabricate successful API results.

降低复杂度不能覆盖必要的安全性或正确性。不得暴露 API Key、Service Role Key、Token 或密码；不得将仅限服务端使用的密钥移入前端；不得为了省事关闭或弱化 RLS；不得损害数据完整性；不得改变 Frozen 模型或预测契约；不得移除防止数据泄漏的模型规则；不得将 API 失败伪造成成功结果。

The principle is: reduce unnecessary defensive complexity, not essential security or correctness.

原则是：减少不必要的防御性复杂度，而不是削弱必要的安全性或正确性。

## Graceful degradation / 合理降级

Graceful degradation is optional, not mandatory. Do not implement degradation paths for every possible failure.

合理降级是可选方案，不是强制要求。不要为每一种可能的失败都实现降级路径。

Add degradation logic only when it protects a core user flow or solves a failure that is known to occur or reasonably likely.

只有当降级逻辑能保护核心用户流程，或者能解决已知发生或合理可能发生的失败时，才应添加。

For this project, a clear and recoverable error state is often preferable to a complex attempt to keep every feature partially operational.

对本项目而言，清晰且可恢复的错误状态，通常比试图让每个功能都保持部分运行的复杂方案更合适。

Do not use fallback behavior to:

- disguise defects;
- hide failures;
- fabricate successful results;
- return misleading data.

不要使用 fallback 来：

- 掩盖缺陷；
- 隐藏失败；
- 伪造成功结果；
- 返回具有误导性的数据。

Graceful degradation is allowed when it:

- is visible and honest;
- preserves core functionality where possible;
- does not return fake data;
- does not prevent the underlying error from being diagnosed.

允许合理降级，但必须满足：

- 对用户真实、透明；
- 尽可能保留核心功能；
- 不返回假数据；
- 不妨碍开发者继续定位真实错误。

For example, disabling an unsupported visual effect or displaying a static placeholder when an optional visualization fails may be acceptable.

例如，当浏览器不支持某种视觉效果时关闭该效果，或者可选可视化失败时显示静态占位，可以属于合理降级。

Pretending an API request succeeded when it actually failed is not acceptable.

API 实际失败却伪装成成功，不属于合理降级。

## Removing obsolete code / 删除废弃代码

When replacing an implementation:

1. Verify the replacement.
2. Update relevant references.
3. Confirm that the old implementation is no longer required.
4. Remove obsolete paths when safe.

替换实现时：

1. 验证新实现；
2. 更新相关引用；
3. 确认旧实现已经不再需要；
4. 在安全的前提下删除旧路径。

Before removing obsolete code, check whether it is referenced by:

- routes;
- imports;
- tests;
- build scripts;
- runtime configuration.

删除旧代码前，应检查它是否仍被以下内容引用：

- 路由；
- import；
- 测试；
- 构建脚本；
- 运行时配置。

Do not perform broad repository cleanup outside the current task merely because obsolete code is discovered.

不要因为在当前任务中发现旧代码，就顺便对整个仓库进行与任务无关的大规模清理。

---

# 5. UI and VAULT-0 Rules
# 5. UI 与 VAULT-0 规则

## Product identity / 产品视觉身份

Crisis Data Terminal has an established CRT / terminal-inspired visual identity.

Crisis Data Terminal 已经建立了明确的 CRT / Terminal 视觉身份。

The following may be intentional parts of the product identity:

- CRT / terminal aesthetic;
- terminal or pixel-style typography;
- scanlines;
- restrained glow;
- system-status presentation;
- terminal-like transitions and motion.

以下内容可以属于产品核心视觉语言：

- CRT / Terminal 美学；
- Terminal / 像素风字体；
- 扫描线；
- 克制的发光效果；
- 系统状态式信息展示；
- Terminal 风格的过渡和动画。

Established stylistic identity is **not** considered unnecessary decorative complexity by default.

已经确立的风格身份**不能默认被视为无意义的装饰性复杂度**。

Do not remove established stylistic elements merely because they do not provide direct functional value.

不要仅仅因为某个视觉元素没有直接功能价值，就擅自删除已经确立的风格元素。

However:

- visual effects must not materially harm usability;
- visual effects must not obscure important information;
- readability remains important;
- serious performance problems should be optimized.

但是：

- 视觉效果不能明显损害可用性；
- 不能遮挡重要信息；
- 必须保证基本可读性；
- 如果造成明显性能问题，应进行优化。

The principle is:

> **Preserve the style. Control the excess.**

原则是：

> **保留风格，克制滥用。**

## UI consistency / UI 一致性

Unless explicitly redesigned:

- maintain a consistent typography hierarchy;
- maintain consistent navigation patterns;
- maintain consistent spacing and panel structures;
- avoid introducing an unrelated visual language on a single page.

除非当前任务明确进行重新设计，否则：

- 保持统一的字体层级；
- 保持统一的导航逻辑；
- 保持相对统一的间距和面板结构；
- 不要让单个页面突然采用完全无关的视觉语言。

Terminal or pixel fonts are mainly intended for:

- system labels;
- status text;
- compact controls;
- numeric or technical displays.

Terminal / 像素字体主要用于：

- 系统标签；
- 状态信息；
- 紧凑控件；
- 数字或技术信息。

Long-form Chinese body text should prioritize readability.

较长的中文正文应优先保证阅读体验。

Shared fixed-height layouts must explicitly define scrolling responsibility.

使用固定高度的共享布局时，必须明确由哪个容器承担纵向滚动。

Do not allow:

- important content to become unreachable;
- bottom status/navigation areas to cover content;
- accidental double-scroll layouts;
- layouts that only work at one viewport size.

不要出现：

- 重要内容无法滚动访问；
- 底部状态栏或导航遮挡正文；
- 意外的双滚动区域；
- 只能在某一个分辨率正常工作的布局。

## VAULT-0

VAULT-0 is:

- a recurring system identity;
- an AI interaction element;
- an intentional part of the Crisis Data Terminal narrative experience.

VAULT-0 是：

- 持续存在的系统身份；
- AI 交互元素；
- Crisis Data Terminal 整体叙事体验的一部分。

Preserve VAULT-0's established system character and terminal-style narrative voice where appropriate.

在合适的场景下，保留 VAULT-0 已建立的系统角色感和 Terminal 式叙事语气。

Do not weaken VAULT-0 into a generic assistant solely for conventional UI neutrality.

不要仅仅为了追求传统、普通的 UI 中立性，而把 VAULT-0 弱化成一个没有角色感的通用助手。

Narrative or in-universe terminology is allowed when it contributes to the established VAULT-0 experience.

如果有助于 VAULT-0 已确立的体验，可以使用世界观内、系统化或角色化术语。

However, do not expose internal technical error information or debugging details to ordinary users.

但是，不要向普通用户暴露内部技术错误信息或调试细节。

Do not expose:

- raw API errors;
- stack traces;
- database errors;
- debugging output;
- developer-oriented diagnostics.

不要直接展示：

- 原始 API 错误；
- 堆栈；
- 数据库错误；
- Debug 输出；
- 面向开发者的诊断信息。

Technical failures should be translated into concise user-facing system messages consistent with the VAULT-0 style.

技术失败应该转换成简洁、用户可理解、同时符合 VAULT-0 风格的系统提示。

Unless explicitly redesigned:

- use one coherent VAULT-0 strategy across user-facing routes;
- avoid duplicated VAULT-0 / AI instances on the same page;
- route transitions must not accidentally duplicate, remove, or orphan shared VAULT-0 UI;
- do not add AI-generated text merely to fill interface space.

除非明确重新设计：

- 用户端各路由采用统一的 VAULT-0 策略；
- 避免同一页面重复出现多个 VAULT-0 / AI 实例；
- 路由切换不能意外复制、删除或遗留共享 VAULT-0 UI；
- 不要为了填充界面空间而添加无意义 AI 文案。

---

# 6. Data, API, Database and Security Rules
# 6. 数据、API、数据库与安全规则

## Data and API / 数据与 API

Treat APIs and data structures as explicit contracts.

将 API 和数据结构视为明确的数据契约。

Do not silently change request or response formats.

不要静默修改请求或响应格式。

Validate:

- response Content-Type when relevant;
- expected response structure;
- required fields.

根据需要验证：

- 响应 Content-Type；
- 响应结构；
- 必需字段。

Do not hide API failures behind fabricated successful responses.

不要使用伪造成功响应来隐藏 API 失败。

When changing a contract, identify and update all consumers.

修改接口契约时，必须找到并更新所有调用方。

For the impact-analysis workflow:

- input-option retrieval and prediction are separate responsibilities;
- option-loading failures must not be disguised as successful empty data;
- prediction failures must produce recoverable and understandable UI states.

对于影响等级分析流程：

- 输入选项获取和预测属于不同职责；
- 选项加载失败不能伪装成“成功但没有数据”；
- 预测失败应进入可恢复、用户能够理解的错误状态。

## Database / 数据库

Before database-related changes, inspect relevant:

- schema;
- migrations;
- constraints;
- indexes;
- RLS policies.

修改数据库相关内容前，应检查相关：

- Schema；
- Migration；
- Constraint；
- Index；
- RLS Policy。

Database changes should be reproducible through versioned SQL or the project's established migration mechanism.

数据库结构修改应该通过版本化 SQL 或项目既有 Migration 机制实现，以保证可复现。

Do not manually modify production data as part of ordinary code changes.

普通代码修改过程中，不要直接手工修改生产数据。

Do not weaken RLS merely to make a failing request succeed.

不要为了让某个失败请求“先跑起来”，就降低或关闭 RLS。

Preserve existing data unless destructive changes are explicitly authorized.

除非明确授权破坏性修改，否则应保护已有数据。

## Security and Secrets / 安全与密钥

Never commit or expose:

- API keys;
- service-role keys;
- tokens;
- passwords;
- private credentials.

绝不能提交或暴露：

- API Key；
- Service Role Key；
- Token；
- 密码；
- 私有凭据。

Do not expose server-only secrets to frontend code or client-visible environment variables.

不要将仅限服务端使用的密钥暴露到前端代码或客户端可见环境变量中。

Treat Supabase service-role access as server-side only.

Supabase Service Role 权限只能用于服务端。

Do not place real credentials in:

- examples;
- tests;
- logs;
- screenshots;
- documentation.

不要在以下内容中使用真实凭据：

- 示例；
- 测试；
- 日志；
- 截图；
- 文档。

Preserve existing authentication, authorization, and RLS behavior unless explicitly requested to change them.

除非明确要求，否则不要改变现有认证、授权和 RLS 行为。

---

# 7. Machine Learning and Frozen Boundaries
# 7. 机器学习与冻结边界

Machine-learning work must prioritize:

- reproducibility;
- data integrity;
- leakage prevention;
- thesis explainability.

机器学习工作优先保证：

- 可复现性；
- 数据完整性；
- 防止数据泄漏；
- 论文可解释性。

Do not use post-event outcome variables as prediction features.

不要使用灾害发生后的结果变量作为预测特征。

Do not use the final held-out test set for model selection or hyperparameter tuning.

禁止使用最终留置测试集进行模型选择或超参数调优。

Preserve the defined target class order:

1. Low
2. Moderate
3. Severe

保持目标类别顺序：

1. Low
2. Moderate
3. Severe

## Frozen Prediction Boundary / 冻结预测边界

Unless the current task explicitly authorizes changes to the frozen prediction system, do not modify or overwrite:

- the final frozen Random Forest pipeline;
- the final preprocessing behavior;
- the locked 15-feature definition;
- the Low / Moderate / Severe target definition and ordering;
- final held-out test results;
- prediction request and response contracts;
- frozen model manifests or checksums.

除非当前任务明确授权修改冻结预测系统，否则不得修改或覆盖：

- 最终冻结的 Random Forest Pipeline；
- 最终预处理行为；
- 已锁定的 15 个特征定义；
- Low / Moderate / Severe 目标定义及顺序；
- 最终留置测试结果；
- 预测请求与响应契约；
- 冻结模型 Manifest 或校验值。

Prediction-model testing and evaluation may remain experimental even while the final production/frozen model is protected.

即使最终生产 / 冻结模型受到保护，预测模型测试与评估本身仍可以继续处于实验阶段。

Experimental model work must use separate:

- names;
- output files;
- artifacts;
- reports.

实验模型必须使用独立的：

- 名称；
- 输出文件；
- 模型产物；
- 报告。

Never silently replace a frozen artifact with an experimental result.

绝不能用实验结果静默覆盖冻结产物。

Do not silently change:

- preprocessing;
- feature definitions;
- target definitions;
- evaluation methodology;
- dataset split logic.

不要静默修改：

- 预处理；
- 特征定义；
- 目标定义；
- 评估方法；
- 数据集划分逻辑。

---

# 8. Testing and Verification
# 8. 测试与验证

Verification statements must reflect actual execution.

所有“已验证”的结论必须来自真实执行。

Do not claim:

- a test passed unless it was actually executed;
- a bug is fixed without appropriate verification;
- a build succeeded unless the build was actually run;
- expected behavior as verified behavior.

不要声称：

- 没运行的测试“已经通过”；
- 没有验证的 Bug“已经修复”；
- 没运行 Build 就说“构建成功”；
- 把理论上应该工作的行为描述成“已经验证”。

Clearly distinguish:

- implemented;
- tested;
- expected;
- not verified.

报告中应明确区分：

- 已实现；
- 已测试；
- 预期行为；
- 尚未验证。

For UI changes, perform browser-level verification when the issue depends on actual layout, routing, interaction, or runtime behavior.

如果 UI 问题与真实布局、路由、交互或运行时行为有关，应尽可能进行真实浏览器级验证。

For API changes, verify actual request/response behavior when possible.

API 修改应尽可能验证真实请求 / 响应行为。

For model changes, preserve reproducibility and record the actual evaluation procedure.

模型修改必须保持可复现，并记录真实评估流程。

Do not modify tests merely to make an incorrect implementation pass.

不要为了让错误实现“通过测试”而修改测试本身。

---

# 9. Documentation and Thesis Traceability
# 9. 文档与论文可追溯性

This repository supports a graduation thesis.

本仓库同时服务于毕业论文。

Important technical decisions should remain explainable and traceable.

重要技术决策应保持可解释、可追溯。

For a completed major development stage, update or create the corresponding Markdown report under the established thesis documentation directory:

`docs/thesis/`

完成一个主要开发阶段后，应在既定论文文档目录中更新或创建对应 Markdown 报告：

`docs/thesis/`

Major-stage documentation should record when relevant:

- the problem;
- the chosen approach;
- important alternatives;
- implementation changes;
- verification or experimental results;
- known limitations.

主要阶段文档根据实际情况记录：

- 问题；
- 选择的方案；
- 重要备选方案；
- 实现变化；
- 验证或实验结果；
- 已知限制。

Do not create a new thesis report for every minor UI adjustment or ordinary bug fix unless explicitly requested.

除非明确要求，不要为每一个小 UI 修改或普通 Bug 修复都新建论文阶段报告。

Prefer updating the relevant existing stage report when appropriate.

适合时优先更新已有阶段报告。

Do not fabricate:

- experimental results;
- test results;
- performance measurements;
- implementation details.

禁止伪造：

- 实验结果；
- 测试结果；
- 性能数据；
- 实现细节。

---

# 10. Project Commands and Important Paths
# 10. 项目命令与重要路径

Use the repository's existing scripts.

使用仓库已经存在的脚本。

Before adding, changing, or assuming commands, inspect:

- `package.json`
- `scripts/`
- `vite.config.js`

在新增、修改或假设项目命令之前，应先检查：

- `package.json`
- `scripts/`
- `vite.config.js`

Typical dependency installation:

```bash
npm install
```

典型依赖安装命令：

```bash
npm install
```

Use the repository-defined development and build scripts rather than inventing alternative workflows.

开发和构建应使用仓库中已有的脚本，不要擅自建立另一套工作流。

Do not start Vite alone when verifying functionality that depends on:

- the local Python inference API;
- `/api` proxy behavior;
- prediction endpoints.

如果功能依赖以下内容，不要只启动 Vite 就进行验证：

- 本地 Python 推理 API；
- `/api` Proxy；
- 预测接口。

Prediction-related local verification requires the complete relevant local environment.

预测相关功能的本地验证需要启动对应的完整开发环境。

Important project areas include:

- `src/`
- `api/`
- `scripts/`
- `docs/`
- `vite.config.js`
- `package.json`

重要项目区域包括：

- `src/`
- `api/`
- `scripts/`
- `docs/`
- `vite.config.js`
- `package.json`

Do not assume optional directories exist. Inspect the repository before referencing or creating new paths.

不要假设某个可选目录一定存在。引用或创建新路径前，应先检查真实仓库结构。

---

# 11. Project Status Maintenance
# 11. 项目状态维护

The current project status is recorded in:

`docs/project-status.md`

当前项目状态记录在：

`docs/project-status.md`

At the end of each task, determine whether the task changed the status of any major project area.

每次任务结束后，应判断本次任务是否改变了某个主要项目区域的状态。

Update `docs/project-status.md` only when:

- an Experimental area becomes Stable;
- a Stable area explicitly returns to Experimental;
- an artifact, interface, model, or behavior becomes explicitly Frozen;
- a Frozen boundary is explicitly changed or released;
- a new major Experimental area is introduced;
- a major project-wide constraint becomes established or removed.

仅在以下情况下更新 `docs/project-status.md`：

- Experimental 区域正式变为 Stable；
- Stable 区域被明确重新定义为 Experimental；
- 某个产物、接口、模型或行为被明确冻结；
- Frozen 边界被明确修改或解除；
- 新增重要实验性区域；
- 新增或取消重要项目级约束。

Do **not** update `docs/project-status.md` for:

- ordinary bug fixes;
- minor UI adjustments;
- copy changes;
- routine refactoring;
- implementation details that do not change project-level status.

以下情况**不要**更新 `docs/project-status.md`：

- 普通 Bug 修复；
- 小型 UI 调整；
- 文案修改；
- 常规重构；
- 不改变项目级状态的实现细节。

`docs/project-status.md` is a **current-state reference**, not a changelog.

`docs/project-status.md` 是**当前状态表**，不是开发日志。

When updating it:

- describe the resulting current state;
- move or remove outdated entries instead of accumulating history;
- keep it concise;
- do not duplicate detailed implementation reports already stored elsewhere.

更新时：

- 描述修改后的当前状态；
- 移动或删除已经过时的状态，而不是不断追加历史；
- 保持简洁；
- 不要重复其他文档中已有的详细开发报告。

Do **not** mark an area Stable or Frozen merely because one task was completed successfully.

**不能**因为某一次任务完成并测试通过，就自动把整个模块标记为 Stable 或 Frozen。

A status change requires explicit evidence from:

- the current task;
- the project owner;
- existing authoritative project documentation.

状态变化必须有明确依据，例如：

- 当前任务明确说明；
- 项目负责人明确决定；
- 已有权威项目文档明确记录。

When uncertain, preserve the existing status.

如果无法确定，保持原有状态，不要自行升级或冻结。

---

# 12. Decision Priority
# 12. 冲突规则优先级

When rules or goals conflict, use the following priority:

1. Explicit instructions from the current task
2. Explicitly Frozen artifacts, contracts, and confirmed requirements
3. Correctness, essential security, and data integrity
4. Simplicity and thesis explainability
5. Existing Stable behavior
6. Maintainability
7. UI and interaction consistency
8. Performance optimization
9. Optional architectural elegance

当规则或目标发生冲突时，按以下顺序处理：

1. 当前任务中的明确要求
2. 明确 Frozen 的产物、契约和已确认需求
3. 正确性、必要的安全性和数据完整性
4. 简洁性和毕业论文可解释性
5. 已有 Stable 行为
6. 可维护性
7. UI 与交互一致性
8. 性能优化
9. 可选的架构优雅程度

Experimental status permits broader changes but does not override higher-priority constraints.

Experimental 状态允许更大范围修改，但不能覆盖更高优先级约束。

When a major decision remains genuinely ambiguous, do not silently make an irreversible architectural, data, or model change.

如果重大决策确实存在歧义，不要静默进行不可逆的架构、数据或模型修改。

---

# 13. Final Principle
# 13. 最终原则

The goal is not to build the most sophisticated implementation.

目标不是构建最复杂、最炫技的实现。

The goal is to build the simplest system that is:

- correct;
- maintainable;
- reproducible;
- verifiable;
- academically explainable;
- consistent with its established product identity.

目标是在满足需求的前提下，构建尽可能简单，同时具备以下特征的系统：

- 正确；
- 可维护；
- 可复现；
- 可验证；
- 适合毕业论文解释；
- 与既定产品身份一致。

Prefer a smaller system that works end-to-end over a more complex system that is only partially correct.

宁可选择规模更小但能够完整运行的系统，也不要选择复杂但只能部分正确工作的系统。

Maximize functionality per unit of necessary complexity.

在必要复杂度尽可能低的前提下，实现尽可能完整的功能。

The goal is the least necessary complexity, not the fewest physical lines of code. Readability, correctness, maintainability, reproducibility, verifiability, thesis explainability, and product identity must remain intact.

目标是最少的必要复杂度，而不是最少的物理代码行数。必须继续保证可读性、正确性、可维护性、可复现性、可验证性、毕业论文可解释性和产品身份。

> **Preserve the product identity. Improve the engineering quality. Do not sacrifice one for the other.**
>
> **保留产品身份，提高工程质量，不要为了其中一个牺牲另一个。**
