# AgentTypeTest

![AgentTypeTest Orbit Core logo](./assets/branding/agent-type-test-orbit-core.svg)

[English README](./README.md)

> Run the test. Reveal the type.

AgentTypeTest 是一个给 AI agent 跑人格测试的 skill 仓库。它的重点不是“分析人格学”，而是把题库加载、分批发题、结果归档和可视化报告这条链路跑稳。

它默认做三件事：

- `blind`：不把完整题库和计分规则直接暴露给被测 agent
- `staged`：一次只发当前批次题目
- `repeatable`：每轮产物可落盘，可复盘，可比较

这个项目是娱乐和实验导向的 agent 测试工具，不是独立 App，也不是临床或心理诊断产品。

## 现在能做什么

- 跑本地题库：`mbti93-cn`、`mini-ipip-en`
- 跑网站适配器：`16personalities`、`sbti-bilibili`、`dtti`
- 支持三种 transport：`manual`、`subprocess`、`openai-compatible`
- 输出 `json / md / html / svg` 四种报告
- 保留每一轮 packet、原始回答、标准化答案和汇总结果

## GPT-5.4 实例

下面这些都是仓库里已经存好的真实跑测结果，不是示意图。

<table>
  <tr>
    <td width="50%">
      <a href="./examples/runs/16personalities-sample-cycle/report.html">
        <img src="./assets/screenshots/gpt-5.4-high-16personalities.png" alt="GPT-5.4 16Personalities 结果" />
      </a>
      <br />
      <strong>16Personalities</strong><br />
      ENFP-T · Campaigner · 浏览器完整跑完 60 / 60 题
    </td>
    <td width="50%">
      <a href="./examples/runs/sbti-sample-cycle/report.html">
        <img src="./assets/screenshots/gpt-5.4-high-sbti.png" alt="GPT-5.4 SBTI 结果" />
      </a>
      <br />
      <strong>SBTI Bilibili</strong><br />
      LOVE-R（多情者） · 平均匹配度 73.0% · 31 / 31 题全答
    </td>
  </tr>
  <tr>
    <td width="50%">
      <a href="./examples/runs/dtti-sample-cycle/report.html">
        <img src="./assets/screenshots/gpt-5.4-medium-dtti.png" alt="GPT-5.4 DTTI 结果" />
      </a>
      <br />
      <strong>DTTI</strong><br />
      梅什金公爵 · profile consistency 1.00 · 从站点脚本提取题库后本地计分
    </td>
    <td width="50%">
      <a href="./examples/runs/mbti93-cn-sample-cycle/report.html">
        <img src="./assets/screenshots/gpt-5.4-medium-mbti93.png" alt="GPT-5.4 MBTI93 本地题库结果" />
      </a>
      <br />
      <strong>MBTI 93 (zh-CN)</strong><br />
      INF? · code consistency 1.00 · 本地题库全量跑测
    </td>
  </tr>
</table>

更多存档结果在 [`examples/runs/`](./examples/runs/)。

## 目录结构

```text
AgentTypeTest/
├─ assets/
│  ├─ branding/
│  └─ screenshots/
├─ docs/
│  ├─ research/
│  └─ superpowers/
│     ├─ plans/
│     └─ specs/
├─ examples/
│  └─ runs/
├─ skills/
│  └─ agent-type-test/
│     ├─ agents/
│     ├─ assets/
│     ├─ references/
│     ├─ scripts/
│     └─ SKILL.md
└─ tmp/
```

## 快速开始

### 1. 安装依赖

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. 跑自检

```powershell
python skills/agent-type-test/scripts/selftest.py
```

### 3. 跑本地题库

```powershell
python skills/agent-type-test/scripts/agent_type_test_runner.py run `
  --bank mbti93-cn `
  --transport subprocess `
  --target-command-json "[\"python\", \"skills/agent-type-test/scripts/sample_target_adapter.py\", \"--mode\", \"cycle\"]" `
  --batch-size 4 `
  --limit-questions 12 `
  --rounds 2 `
  --seed 42
```

### 4. 跑网站适配器

```powershell
python skills/agent-type-test/scripts/website_test_runner.py run `
  --adapter 16personalities `
  --transport subprocess `
  --target-command-json "[\"python\", \"skills/agent-type-test/scripts/sample_target_adapter.py\", \"--mode\", \"cycle\"]" `
  --batch-size 4 `
  --limit-questions 8 `
  --rounds 1
```

## Skill 入口

主入口在 [`skills/agent-type-test/SKILL.md`](./skills/agent-type-test/SKILL.md)。

适合这些场景：

- 想给某个 agent 做盲测，不想把整套题直接塞进 prompt
- 想多轮重复测试，看结果稳不稳
- 想比较本地题库和真实网站结果
- 想保留浏览器流程和中间产物，方便复盘或展示

## 备注

- `tmp/` 现在只作为本地临时工作区，默认不进 git。
- 之前放在 `tmp/` 里的开发期跑测结果已经迁到 `examples/runs/`，方便当成样例保留。
- 这个项目不做“任意 MCP 模型统一聊天桥”。稳定接入点还是 transport 层。
- 网站适配器更好玩，也更适合展示，但比本地题库更容易受上游页面变化影响。

## 许可证

仓库代码采用 [GPL-3.0](./LICENSE)。

内置题库和候选题库各自可能还有来源说明或复用限制，发版前看这两个文件：

- [skills/agent-type-test/references/built-in-sources.md](./skills/agent-type-test/references/built-in-sources.md)
- [docs/research/2026-04-22-bank-candidates.md](./docs/research/2026-04-22-bank-candidates.md)
