# AgentTypeTest Design

**Goal:** 做一个可复用的 skill，用分批渐进式披露的方法给 AI 做 MBTI / xxTI 风格的人格测试；题库和通信方式都可插拔，默认不把完整题库、计分规则和 skill 代码暴露给被测 AI。

## Product Position

- 这是一个 `skill`，不是一个独立 AI 产品。
- skill 本身不负责“人格判断推理”，而是负责：
  - 装载题库
  - 分批发题
  - 记录会话状态
  - 收集答案
  - 聚合结果
  - 输出报告
- 测试定位偏娱乐，但执行方法要尽量专业、可重复、可审计。

## Requirements

### Functional

- 支持 MBTI 风格的二选一题、Likert 量表题，以及其他 `xxTI` 家族题库。
- 支持本地题库和在线题源。
- 一次只向被测 AI 暴露少量题目。
- 支持多轮重复测试，输出稳定性指标。
- 支持至少三种被测 AI 接入方式：
  - `manual`：人工转发问题、粘贴答案
  - `subprocess`：通过标准输入/输出和外部适配器通信
  - `openai-compatible`：直接调在线聊天接口

### Non-Functional

- 不把完整题库和计分规则直接塞进 prompt。
- 所有中间产物可落盘，便于复盘。
- 题库格式统一，新增一个新测试家族时不需要改主流程。
- 主流程尽量不依赖任何第三方 SDK，用 Python 标准库即可运行。

## Architecture

### 1. Skill Layer

`SKILL.md` 负责告诉未来的 agent：

- 什么时候该用这个 skill
- 怎么选题库来源
- 怎么选 transport
- 怎样保证 blind / staged / repeatable
- 该调用哪些脚本

### 2. Bank Layer

统一题库格式，核心对象：

- `dimensions`
- `questions`
- `choices`
- `effects`
- `report_mode`

这样 MBTI、SBTI、DTTI 之类都能映射成“题目 + 选项效果 + 维度聚合”的同一模型。

### 3. Source Layer

题源分成两类：

- `local`
  - 直接读取 skill 自带的 JSON bank
- `online`
  - 读取远程 JSON bank URL
  - 或用导入脚本把外部开源 bank 拉成本地 bank

MVP 先内置一套本地 MBTI bank，并支持远程 JSON bank。

### 4. Transport Layer

runner 不假设被测 AI 一定有某种官方协议，而是提供三类 transport：

- `manual`
  - 最稳，适合任何聊天产品
- `subprocess`
  - 推荐给 MCP wrapper、CLI agent、桥接器使用
- `openai-compatible`
  - 适合在线模型测试

这里不直接实现“通用 MCP 聊天标准”，因为 MCP 标准化的是工具/资源，不是统一的“对模型提问”接口。MVP 用 `subprocess` 作为协议桥接点更实际。

## Methodology

### Blindness

- 默认不在 prompt 中出现 `MBTI`、`人格测试`、完整维度名。
- 默认只告诉被测 AI：这是一个简短问卷，请按 JSON 回答。

### Staged Disclosure

- 默认每批 3-5 题。
- 每批单独保存 packet 和 response。
- 被测 AI 只看到当前批次。

### Repeatability

- 支持 `rounds > 1`
- 每轮可使用不同 shuffle seed
- 输出：
  - 每轮结果
  - 聚合结果
  - 维度一致率
  - 整体代码一致率

### Refusal Handling

- 如果输出不是合法 JSON，runner 直接报错，不默默猜测。
- 每批次 raw response 都会保存，方便排查。

## MVP Scope

### Included

- `agent-type-test` skill
- 通用 bank schema
- 本地 MBTI 93 题 bank
- `manual` / `subprocess` / `openai-compatible` 三种 transport
- JSON + Markdown 报告
- 内置自检脚本
- 一个示例目标适配器，方便本地试跑

### Deferred

- 浏览器自动化聊天产品接入
- 通用 MCP chat bridge
- 大量现成 xxTI bank 目录
- UI 页面或排行榜

## Local Bank Choice

MVP 的本地题库选择：

- 来源：`karminski/llm-mbti-arena`
- 形式：93 道 MBTI 题
- 用法：通过导入脚本转换成 skill 自己的统一 bank schema

这么做的原因：

- 开源仓库、结构清晰
- 适合 blind staged run
- 不把整个实现绑死在第三方评分接口上

## Risks

- 不同 AI 的输出格式差异很大，JSON 解析会是第一风险点。
- “xxTI” 家族很多并没有统一公开标准，MVP 只能先做通用框架 + MBTI 样例。
- 在线题源可能失效，所以主流程不能依赖在线源。

## Acceptance Criteria

- 能用本地 bank 完整跑完一轮 staged test。
- 能输出最终 JSON / Markdown 报告。
- 能通过 `subprocess` transport 跑通一次独立试跑。
- skill 文档能指导另一个 agent 正确调用脚本完成测试。

