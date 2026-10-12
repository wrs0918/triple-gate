<div align="center">

# 三重门 · TripleGate

**会拒绝的网文连载流水线**

A web-novel pipeline that knows how to say NO.

Python 3.10+ · 纯标准库 · Agent Skill

**量化指标 → 模式 lint → 叙事 rubric 三层门禁 · 写前阻断 · 双时间线状态真源 · 断点续跑**

</div>

---

## 它是什么

一个跑在 AI Agent（Claude Code / TRAE / OpenCode 等）里的网文连载 Skill。每一章必须穿过三重门禁才能落账，门禁由**代码强制**，不靠模型自觉：

| 门 | 检查什么 | 谁执行 | 成本 |
|---|---|---|---|
| 第一层 | 量化指标：σ² 句长方差 / 等长句连串 / TTR / 段长 CV / 3gram 复读率 / 语气词·连词密度（参考） | Python（band 区间判定） | 零 token |
| 第二层 | 模式 lint：「不是X而是Y」及其反序 / 音量反差腔 / 章末升华预告 / 套词·比喻·套式反应密度（双门槛）/ 碎句号 / 动作清单 / 占位符 / AI 自我泄漏 / 逐字复读（30 规则，blocking/advisory 分级 + 台词豁免 + 密度分档） | Python（正则 + 序列检测） | 零 token |
| 第三层 | 叙事架构 rubric：主题点题 / 因果单线 / QUD 模板化 / 信息差泄漏 / 对话腔区分（引证制，一次一组） | LLM（按协议执行） | 低 |

写作在门禁**之前**还有一道写前阻断：五问答不出不许动笔。状态全部落盘在一个 JSON 真源上，会话断了从断点续跑。

## 三条设计公理

1. **会拒绝的流水线**：门禁是代码不是检查表。`tg gate` 不过、schema 不合法、章号不连续，工具直接拒绝并告诉你为什么。
2. **人类是 band 不是极值**：量化指标全部用区间判定（σ² 过高同样亮红灯），防止把文本从"句长均匀"修成"狂野"这种过度矫正——矫正到反方向极端会制造新的 AI 指纹。句长 CV 一类经实测无鉴别力的指标（AUROC≈0.52）只作参考展示，不参与判定。
3. **规则按真人语料校准**：blocking 句式（音量反差腔、反序对比、预告式收尾等）在万疆 20 章 / 七猫 5584 章 / 黑岩 3983 篇真人语料中命中≈0；密度型规则用「章内次数 + 每千字」双门槛防止短文本误报；台词内的句式是口语，一律豁免（只扫引号外叙述）。
4. **证据可累积**：机器门禁与 rubric 的每次发现经 commit 反哺进状态，成为后续章节的「本章禁忌」。同类问题不许犯第二次。

## 与状态管理的耦合

- `state/state.json` 是唯一真源（schema 校验强制），一切章变更经 `tg commit` 入账
- `projections/`（双时间线 / 伏笔台账 / 角色状态 / 进度）是从真源整份重渲染的派生视图，**手改会被 `tg check` 拒绝**
- 双时间线：每条事实分记「作者真相」与「读者已知」+ 揭示状态，写作上下文只带读者已知侧，从机制上杜绝"角色提前知道答案"
- 写前上下文包硬预算 12KB：书魂卡与本章大纲永不裁剪、「读者已知」最后裁剪（防剧透是硬规则），其余按优先级收缩——长跑成本可控

## 快速开始

```bash
# 环境：Python 3.10+，无需第三方依赖（可选 pip install jieba 提升 TTR 精度）
cd my-novel/                                # 新建一个目录作为书籍工作区
python /path/to/triple-gate/scripts/tg.py init --title 书名 --genre 题材
python /path/to/triple-gate/scripts/tg.py start     # 书魂卡填齐后进入写作
```

然后对你的 Agent 说「开新书」「写第1章」「继续写作」即可。SKILL.md 会引导 Agent 走完整协议：

```
prewrite（写前阻断+上下文包） → 写前五问 → DRAFT
  → tg gate（第一层+第二层，机器） → 未过：定向修复 ≤2 轮 → 仍不过：两阶段改写
  → rubric 三个 pass（第三层，引证制） → 提炼 changes.json
  → tg commit（状态入账+投影重渲染）
```

## 目录结构

```text
triple-gate/
├── SKILL.md                    # Skill 入口：路由、硬规则、命令速查
├── references/
│   ├── pipeline/               # plan / write-chapter / continue / export 协议
│   ├── rubric/                 # 第三层：总协议 + 叙事/话语/表面 三个 pass + 两阶段改写
│   └── craft.md                # 写作技法速查（开篇/章尾/爽点/伏笔纪律）
├── scripts/
│   ├── tg.py                  # CLI：init/start/status/prewrite/gate/commit/check/export
│   ├── core/                   # 文本 IO
│   ├── metrics/               # 第一层：indicators（计算）+ bands（区间判定单一来源）
│   ├── lint/                   # 第二层：patterns（30 规则表）+ rules（引擎：台词豁免/尾部窗口/双门槛）
│   ├── state/                  # schema / store（原子写）/ commit / render（投影）
│   ├── gate.py                # 三层编排 + 写前阻断检查
│   ├── context.py             # 上下文包组装（12KB 预算）
│   └── export.py               # 番茄导出
├── templates/book/             # 新书模板
├── tests/                      # 170 个测试，覆盖率 92%
└── .github/workflows/ci.yml    # pytest × Python 3.10/3.12 + 覆盖率门槛 80%
```

## token 成本

前两层门禁零 token（本地计算），写作上下文被预算硬约束在 12KB 内。一章的 LLM 开销集中在：写前五问（几百 token）、正文生成、rubric 三个 pass（各读一遍正文）。机器门禁先筛掉硬伤，LLM 只处理机器判不了的叙事问题。

## 测试与质量

```bash
pip install pytest pytest-cov
pytest --cov=scripts --cov-fail-under=80
```

- 170 个单元/集成测试，行覆盖率 92%（含 CLI 层）
- 阈值单一来源：`scripts/metrics/bands.py`（文档与代码不再两处维护）
- 规则与阈值来源：oh-story（7369★）的真人语料校准 + sepia（3046★）的语料实证研究（2026-10 移植）
- jieba 缺失时 TTR 自动降级为参考级指标，永不误判

## 能力边界（诚实声明）

- 量化指标测的是**统计分布特征**，不是平台 AI 检测器的判定结果；两者没有保证的映射关系。
- 查重只能对本项目历史章节与样本比对，**不具备**对全网已发布内容的平台级查重能力。
- 各网文平台对 AI 辅助内容的规定不同且持续变化，署名、披露与合规由使用者负责，发布前请确认平台现行政策并如实披露。

## License

MIT
