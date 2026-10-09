# 导出协议

适用于用户说「导出」「发番茄」。

## 流程

```bash
python scripts/tg.py export            # 导出到 exports/fanqie/第NNN章.txt
```

## 导出前检查（发布就绪清单）

1. `tg status`：确认预计章数全部 final。
2. 全书终审（用户是终审人，AI 只做核对）：
   - 伏笔台账（`projections/foreshadowing.md`）无「超期」且无未收束的 planted 项
   - 双时间线无「已揭示给读者但作者真相栏没有」的矛盾
   - 核心创意卡一致性：结尾是否兑现书魂卡的 core_conflict
3. 平台合规由使用者负责：各平台对 AI 辅助内容的披露要求不同且持续变化，发布前自行确认现行政策并如实披露。

## 输出规格（番茄）

- 每章一个 txt：`第NNN章.txt`（NNN 为三位章号）
- 首行 `第N章 章标题`，正文 markdown 标记已剥离
- 只导出 `chapters/chNNN_final.md`，draft 永不导出
