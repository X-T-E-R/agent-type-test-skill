# AgentTypeTest

<img src="./assets/branding/agent-type-test-orbit-core.svg" alt="AgentTypeTest Orbit Core logo" width="220" />

[English README](./README.md)

> Run the test. Reveal the type.

现在 SBTI 很火，MBTI 也一直热度不减：俗话说“养虾养虾”，很多人还会让 AI 去 roleplay、扮演各种不同性格的人设。  
但大家有没有想过：你自己的龙虾 / 编程助手，到底是什么人格？

于是我写了这样一个 skill，可以直接给你的 AI 做一次“人格测试”。

你只需要把这个 GitHub 地址发给你的 AI，它就会自己去做测试，然后生成一张它的人格卡。

AgentTypeTest 把题库、分批发题、结果聚合和报告渲染收在同一套流程里，方便拿不同 agent 反复跑、横向比、做展示。

## 项目特征

- `blind`：不把完整题库和计分规则直接暴露给被测 agent
- `staged`：一次只发当前批次题目
- `repeatable`：支持多轮重复测试和聚合结果
- `reportable`：结果能输出成适合人看的报告页面

## 当前覆盖

- 本地题库：`mbti93-cn`、`mini-ipip-en`
- 网站适配器：`16personalities`、`sbti-bilibili`、`dtti`
- transport：`manual`、`subprocess`、`openai-compatible`

## GPT-5.4 实例

下面这些是用真实 GPT-5.4 跑出来的报告截图。

<table>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/gpt-5.4-high-16personalities.png" alt="GPT-5.4 16Personalities 结果" />
      <br />
      <strong>16Personalities</strong><br />
      ENFP-T · Campaigner · 浏览器完整跑完 60 / 60 题
    </td>
    <td width="50%">
      <img src="./assets/screenshots/gpt-5.4-high-sbti.png" alt="GPT-5.4 SBTI 结果" />
      <br />
      <strong>SBTI Bilibili</strong><br />
      LOVE-R（多情者） · 平均匹配度 73.0% · 31 / 31 题全答
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/gpt-5.4-medium-dtti.png" alt="GPT-5.4 DTTI 结果" />
      <br />
      <strong>DTTI</strong><br />
      梅什金公爵 · profile consistency 1.00 · 从站点脚本提取题库后本地计分
    </td>
    <td width="50%">
      <img src="./assets/screenshots/gpt-5.4-medium-mbti93.png" alt="GPT-5.4 MBTI93 本地题库结果" />
      <br />
      <strong>MBTI 93 (zh-CN)</strong><br />
      INF? · code consistency 1.00 · 本地题库全量跑测
    </td>
  </tr>
</table>

## 给 agent

如果你是来用 skill，不要把这个 README 当成运行说明，直接去 skill 目录看。

直接从这里开始：

- [`skills/agent-type-test/SKILL.md`](./skills/agent-type-test/SKILL.md)

## 许可证

仓库代码采用 [GPL-3.0](./LICENSE)。

内置题库和题源各自可能还有来源说明或复用限制，发版前看这个文件：

- [skills/agent-type-test/references/built-in-sources.md](./skills/agent-type-test/references/built-in-sources.md)
