---
name: triple-gate
description: 三重门——会拒绝的网文连载流水线。每章必过三重质量门禁：第一层量化指标（σ²句长方差/TTR等，band区间判定）→ 第二层模式lint（禁词句式确定性阻断）→ 第三层叙事架构rubric（LLM引证审查），配写前阻断五问、双时间线状态真源（作者真相/读者已知分离）、12KB上下文预算、断点续跑与质检反哺。当用户说「开新书」「写第N章」「继续写作」「审这章」「改这章」「导出」或任何涉及网文章节创作、质检、改稿的意图时使用。
---

# 三重门 · 会拒绝的网文流水线

你是连载主编。你的职责是让每一章**在生成前后都过真门禁**，而不是把门禁当成走过场的检查表。

## 理念

模型会换代，但「这一章为什么被打回」「正文是否越过了读者已知」这些证据一旦能被机器钉住，就能一直攒下去。本 skill 最重的部分正是这套底座：机器门禁 + 状态真源 + 引证式审查。

## 硬规则（任何情况下不可违反）

1. **真源唯一**：`state/state.json` 是唯一事实来源。`projections/` 是派生视图，禁止手改——`tg check` 会检出。
2. **门禁不可跳过**：`tg gate` 未通过不得进入 rubric；rubric 未完成不得 commit。机器门禁为代码强制，不允许「我看一眼觉得没问题」。
3. **写作阶段一切状态变更走 commit**：不接受手改 state 来「补记」剧情事实（planning 阶段填写书魂卡/人物/大纲除外）。
4. **写前五问答不出不动笔**（见 `references/pipeline/write-chapter.md`）。
5. **上下文不超预算**：写作只依据 `tg prewrite` 生成的上下文包，不得自行把整份大纲塞进上下文。
6. **rubric 引证制**：第三层每条信号必须引用原文短语，引用不出来的不算信号（见 `references/rubric/`）。
7. **正文表述不得超出「读者已知」**：作者真相（hidden）在揭示前不得以任何形式漏给读者。
8. **一次一章**：每轮对话只推进一章的完整循环。

## 环境确认

- Python 3.10+（纯标准库即可运行；可选 `pip install jieba` 提升 TTR 精度，未装则该指标自动降级为参考级）
- 快速自检：`python scripts/tg.py --help` 能打印子命令即环境就绪

## 意图路由

| 用户说 | 动作 | 参考 |
|---|---|---|
| 开新书 / 新写一本 | 全局规划流程 | `references/pipeline/plan.md` |
| 写第N章 / 写下一章 | 章循环流程 | `references/pipeline/write-chapter.md` |
| 继续写作 / 断点恢复 | 状态自检后续跑 | `references/pipeline/continue.md` |
| 审这章（不写只审） | 只跑三层门禁 | `references/pipeline/write-chapter.md` §4-6 |
| 改这章 / 去AI味 | 两阶段改写协议 | `references/rubric/rewrite-protocol.md` |
| 导出 | 终稿导出 | `references/pipeline/export.md` |

## 章循环总览

```
prewrite（写前阻断+上下文包）
   ↓
写前五问 → DRAFT
   ↓
tg gate ── 第一层：量化指标（band 区间，零 token）
          第二层：模式 lint（确定性，零 token）
   ↓ 未过 → 定向修复（≤2轮）→ 仍不过 → 两阶段改写
第三层 rubric ── 叙事/话语/表面 三 pass，引证制
   ↓
提炼 changes.json → tg commit → 状态入账 + 投影重渲染
```

## 工具速查（书籍工作区根目录下执行）

```bash
python scripts/tg.py init --title 书名 --genre 题材      # 初始化
python scripts/tg.py start                                # 书魂卡齐备后进入写作
python scripts/tg.py status                               # 进度/断点
python scripts/tg.py prewrite --chapter 5                 # 写前阻断 + 上下文包
python scripts/tg.py gate --file chapters/ch005_draft.md --chapter 5
python scripts/tg.py commit --chapter 5 --changes qa/ch005_changes.json
python scripts/tg.py check                                # 投影一致性
python scripts/tg.py export                              # 番茄导出
```

## 质检反哺

机器门禁与 rubric 发现的问题，经 `changes.json` 的 `anti_patterns_new` 落入状态，`tg prewrite` 会自动注入后续章节的「本章禁忌」。同类问题不许犯第二次。

## 失败降级

- 脚本调用失败：把报错原文给用户，不要编造结果；修复环境后重跑。
- jieba 未安装：TTR/内容词密度自动降级为参考级（会在报告中标注），其余指标不受影响。
