# AgentTypeTest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个可运行的 skill，用渐进式披露的方法给 AI 做 MBTI / xxTI 风格测试，并支持本地题库、在线题源和可插拔 transport。

**Architecture:** 采用“skill 文档 + 通用 bank schema + runner + source adapter + transport adapter”的结构。主流程只做 deterministic orchestration，不做人格推理；被测 AI 只接收当前批次题目，结果由本地 scorer 聚合。

**Tech Stack:** Python 3 标准库、Markdown 文档、JSON bank 文件

---

### Task 1: Write the Docs

**Files:**
- Create: `docs/superpowers/specs/2026-04-22-agent-type-test-design.md`
- Create: `docs/superpowers/plans/2026-04-22-agent-type-test.md`

- [ ] 写设计文档，锁定目标、边界、架构、方法学和 MVP 范围。
- [ ] 写实现计划，明确 skill 路径、脚本职责和验证方式。

### Task 2: Scaffold the Skill

**Files:**
- Create: `skills/agent-type-test/SKILL.md`
- Create: `skills/agent-type-test/agents/openai.yaml`
- Create: `skills/agent-type-test/references/*.md`
- Create: `skills/agent-type-test/scripts/*.py`

- [ ] 用 `init_skill.py` 初始化 skill 目录。
- [ ] 把 `SKILL.md` 改成可执行的工作流说明。
- [ ] 补参考文档，明确 bank schema、transport contract、内置题源和方法学。

### Task 3: Implement Generic Bank + Runner

**Files:**
- Create: `skills/agent-type-test/scripts/agent_type_test_core.py`
- Create: `skills/agent-type-test/scripts/agent_type_test_sources.py`
- Create: `skills/agent-type-test/scripts/agent_type_test_runner.py`

- [ ] 定义 bank 的统一数据结构。
- [ ] 实现本地/远程 bank 加载。
- [ ] 实现 blind staged packet 生成。
- [ ] 实现 score aggregation 和 rounds stability 计算。
- [ ] 实现 JSON / Markdown 报告输出。

### Task 4: Add Built-in Banks and Test Helpers

**Files:**
- Create: `skills/agent-type-test/scripts/seed_mbti_bank.py`
- Create: `skills/agent-type-test/scripts/sample_target_adapter.py`
- Create: `skills/agent-type-test/scripts/selftest.py`
- Create: `skills/agent-type-test/assets/banks/xxti-template.json`
- Generate: `skills/agent-type-test/assets/banks/mbti93-cn.json`

- [ ] 写 MBTI bank 导入脚本。
- [ ] 写一个最小 sample adapter，模拟外部 AI。
- [ ] 写自检脚本，用 subprocess transport 跑完整流程。

### Task 5: Verify

**Files:**
- Use: `skills/agent-type-test/scripts/selftest.py`
- Generate: `skills/agent-type-test/tmp/*`

- [ ] 运行 bank 导入脚本，生成本地 MBTI bank。
- [ ] 运行自检脚本，确认 report 落盘。
- [ ] 跑 quick validator，确认 skill 结构有效。

### Task 6: Forward Test with a Mini Subagent

**Files:**
- Use: `skills/agent-type-test/*`

- [ ] 启动一个 mini 子 agent。
- [ ] 让子 agent 用这个 skill 做一次受限试跑。
- [ ] 看它是否能按文档正确发现 bank、执行脚本并给出结果。

