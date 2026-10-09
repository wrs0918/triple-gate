# 断点续跑协议

适用于会话中断后用户说「继续写作」。状态真源 + 落盘产物让任何断点可恢复。

## 1. 自检顺序

```bash
python scripts/tg.py status
```

读 `state/state.json` 的 `progress.current_chapter`（N）与 `chapters` 中 `chNNN` 条目，按下面的判定表找到断点：

| 现场特征 | 断点位置 | 从这里继续 |
|---|---|---|
| `chNNN` 条目不存在 | 尚未 prewrite | `write-chapter.md` §1 |
| 条目存在但 gate_layer1 = pending | 写作中 | `write-chapter.md` §3（先看草稿文件存在与否） |
| gate_layer1/2 = failed | 机器门禁修复循环 | `write-chapter.md` §4 |
| gate 通过但 `qa/chNNN_rubric.md` 缺失 | 第三层审查未做 | `write-chapter.md` §5 |
| rubric 存在但 `qa/chNNN_changes.json` 缺失/损坏 | 变更未提炼 | `write-chapter.md` §6 |
| changes 存在但 `chapters/chNNN_final.md` 缺失 | 终稿未保存 | `write-chapter.md` §7 前置条件 |
| 以上全有但未提交 | commit 未执行 | `write-chapter.md` §7 |
| `chNNN` 状态已是 final | 本章已闭环 | 下一章 prewrite |

## 2. 一致性兜底

```bash
python scripts/tg.py check
```

投影不一致 = 有人手改过派生文件。处理：以 `state/state.json` 为准（`commit` 会整份重渲染），提醒用户不要手改 `projections/`。

## 3. 恢复纪律

- 从断点步骤继续，**不要重做已通过的步骤**（机器门禁结果、rubric 报告都是落盘的，直接复用）。
- 无法判断时，把 `status` 输出与判定表给用户看，让作者拍板。
- 恢复后照常走完本章剩余步骤，一次一章。
