# 章循环协议（写作阶段核心流程）

适用于用户说「写第N章」「写下一章」。一次只推进一章。

## 1. 写前阻断

```bash
python scripts/tg.py prewrite --chapter N
```

- 任何 issue 输出都不动笔，先解决（跳章、大纲缺失、上章未终稿都会在这里被拒绝）。
- 通过后读 `projections/context.md`：这是本章写作的唯一事实依据，不要自行去读整份大纲。

## 2. 写前五问

读上下文包后、动笔前，从大纲本章条目中回答（写进 `qa/chNNN_prewrite.md`，每问一句）：

1. **可见伤害**：本章读者能"看见"的伤害是什么？（谁流血/谁损失/谁丢脸）
2. **物理对抗**：有没有至少一场身体或物层面的事件（打斗/追逐/搜查/对峙）？
3. **动词化爽点**：本章的爽点能不能用动词说清？（"打脸/翻盘/碾压"，而不是"变强了"）
4. **结尾档位**：章尾走炸（爆点）/ 钩（悬念）/ 静（余韵）哪一档？具体停在哪句话？
5. **前300字物理事件**：开篇第一个物理动作是什么？

**任何一问答不上来，回到大纲修条目，不硬写。**

## 3. 写作

产出 `chapters/chNNN_draft.md`（首行 `# 第N章 章标题`）。技法要求见 `references/craft.md`。要点：

- 表述不得超出上下文包「读者已知」栏；作者真相在揭示前不许泄漏。
- 避开「本章禁忌」栏的全部条目。
- 对齐「文风基准段」的语感。

## 4. 机器门禁（第一层 + 第二层）

```bash
python scripts/tg.py gate --file chapters/chNNN_draft.md --chapter N
```

报告落盘 `qa/chNNN_gate.json`。未通过时：

- **定向修复**（≤2 轮）：只改报告点名的问题（指标红项按 direction 改，lint 阻断项逐条处理），不要整章重写。
- 2 轮仍不过 → 走 `references/rubric/rewrite-protocol.md` 的两阶段重写。
- 改稿时注意「改稿指纹警告」：保住名词与动词，删修饰不改内容，防止内容词密度骤降。

## 5. 第三层 rubric（引证式审查）

机器门禁通过后，按顺序执行三个 pass，协议见 `references/rubric/`：

1. `narrative.md` — 叙事架构（一次只读一组特征）
2. `discourse.md` — 话语层
3. `style-pass.md` — 表面层（只查机器 lint 查不到的）

产出统一追加到 `qa/chNNN_rubric.md`。**三个 pass 有任一阻断级发现 → 先修复再继续**；参考级发现记录进 changes 的反哺清单。

## 6. 提炼章变更

从本章正文中提炼事实，写 `qa/chNNN_changes.json`（schema 由 `tg commit` 强制校验）：

```json
{
  "chapter": N,
  "summary": "≤300字本章摘要（后续章节上下文用）",
  "timeline_new": [{"objective_fact": "客观发生了什么", "reader_knowledge": "读者此刻知道什么", "reveal_status": "hidden|partial|revealed"}],
  "foreshadowing_planted": [{"content": "伏笔内容", "due_ch": 20, "priority": "high|mid|low"}],
  "foreshadowing_paid": ["F-001"],
  "hooks_new": [{"content": "钩子", "type": "章尾悬念"}],
  "hooks_rewarded": ["H-001"],
  "tropes_used": ["本 章 用 过 的 套 路 名"],
  "characters_update": [{"name": "角色名", "emotion": "...", "location": "...", "known_facts_add": ["..."]}],
  "anti_patterns_new": [{"source": "lint|metrics|rubric", "rule": "规则名", "note": "本章教训"}]
}
```

提炼纪律：只记正文里真实发生的；读者视角与作者视角分开填，宁缺勿滥。

## 7. 提交

```bash
python scripts/tg.py commit --chapter N --changes qa/chNNN_changes.json
```

commit 前置条件：`qa/chNNN_rubric.md` 存在且含「结论」段、终稿已保存为 `chapters/chNNN_final.md`。**commit 会对终稿重跑第一+第二层机器门禁（零 token）**：rubric 修复引入的硬伤在这里被拦下，不过则拒绝提交——草稿时代的门禁记录不能替终稿作证。提交成功后状态版本自增、投影重渲染——至此本章闭环。

**终稿处理**：机器门禁与 rubric 全部通过且无待改项时，把 draft 复制为 final；有修复则保存修复后的版本为 final。

## 8. 特殊说明

- 前 3 章：完成循环后请用户审开篇（300 字冲突/钩子/人设），通过再继续。
- 每 10 章：额外跑一次同质化检查（连续抽 5-10 章正文，对比套路使用与意象频次，见 `references/craft.md` §5），并把发现并入反哺清单。
- 用户在 G8 决策点（开篇/中段转折/终审）的否决永远优先，打回对应步骤重做。
