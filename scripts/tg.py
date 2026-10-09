#!/usr/bin/env python3
"""三重门 CLI：会拒绝的网文流水线的命令行入口。

子命令：
  init     初始化书籍工作区
  start    校验书魂卡齐备，进入写作阶段
  status   查看进度与断点
  prewrite 写前阻断检查 + 生成上下文包
  gate     第一层（量化指标）+ 第二层（模式 lint）机器门禁
  commit   第三层确认后提交章变更，渲染投影
  check    校验投影与状态一致性（拒绝手改派生文件）
  export   导出终稿（当前支持番茄格式）
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# 允许从任意工作区目录直接运行本脚本（python /path/to/triple-gate/scripts/tg.py）
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.context import build_context  # noqa: E402
from scripts.core.errors import GateError
from scripts.core.textio import read_text
from scripts.export import export_fanqie
from scripts.gate import extract_outline_entry, prewrite_checks, run_gate
from scripts.state import layout
from scripts.state.commit import apply_changes, prepare_chapter, record_gate
from scripts.state.render import check_projections, render_projections
from scripts.state.schema import NORTH_STAR_FIELDS
from scripts.state.store import load_state, save_state
from scripts.state.template import new_state

EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_ERROR = 2

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "book"


def _cmd_init(args: argparse.Namespace) -> int:
    if Path(layout.BOOK_JSON).exists():
        raise GateError("本书已初始化（book.json 已存在），删除后才能重新 init")
    for name in ("state", "outline", layout.PROJECTIONS_DIR, layout.CHAPTERS_DIR, layout.QA_DIR, layout.EXPORTS_DIR, ".gate"):
        Path(name).mkdir(parents=True, exist_ok=True)
    book = {"title": args.title, "genre": args.genre, "platform": args.platform}
    Path(layout.BOOK_JSON).write_text(
        json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    save_state(layout.STATE_FILE, new_state(args.title, args.genre, args.platform))
    shutil.copyfile(_TEMPLATES_DIR / "outline.md", layout.OUTLINE_FILE)
    print(f"已初始化《{args.title}》。下一步：填写大纲与书魂卡，然后 tg start")
    return EXIT_OK


def _cmd_start(args: argparse.Namespace) -> int:
    state = load_state(layout.STATE_FILE)
    star = state["book"]["north_star"]
    missing = [field for field in NORTH_STAR_FIELDS if not str(star.get(field, "")).strip()]
    if missing:
        print("书魂卡未填齐，不能开始写作：")
        for field in missing:
            print(f"  - state/state.json → book.north_star.{field} 为空")
        return EXIT_GATE_FAILED
    state["progress"]["phase"] = "writing"
    save_state(layout.STATE_FILE, state)
    print("书魂卡齐备，进入写作阶段。用「写第N章」开始章循环")
    return EXIT_OK


def _cmd_status(args: argparse.Namespace) -> int:
    state = load_state(layout.STATE_FILE)
    progress = state["progress"]
    finals = sum(1 for c in state["chapters"].values() if c["status"] == "final")
    print(f"《{state['book']['title']}》｜{state['book']['genre']}｜{state['book']['platform']}")
    print(f"阶段：{progress['phase']}｜当前章：第 {progress['current_chapter']} 章｜已终稿：{finals} 章")
    print(f"状态版本：{progress['state_revision']}｜伏笔活跃：{sum(1 for f in state['foreshadowing'] if f['status'] == 'planted')} 条")
    return EXIT_OK


def _cmd_prewrite(args: argparse.Namespace) -> int:
    state = load_state(layout.STATE_FILE)
    outline_text = read_text(layout.OUTLINE_FILE)
    issues = prewrite_checks(state, outline_text, args.chapter)
    if issues:
        print("写前阻断：以下问题解决前不应动笔：")
        for issue in issues:
            print(f"  - {issue}")
        return EXIT_GATE_FAILED
    state = prepare_chapter(state, args.chapter)
    save_state(layout.STATE_FILE, state)
    entry = extract_outline_entry(outline_text, args.chapter)
    context = build_context(state, entry)
    target = Path(layout.context_pack())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(context, encoding="utf-8")
    print(f"写前检查通过，上下文包已生成：{layout.context_pack()}（{len(context)} 字符）")
    print(f"下一步：读上下文包 → 回答写前五问 → 写 {layout.chapter_draft(args.chapter)} → tg gate")
    return EXIT_OK


def _read_whitelist() -> list[str]:
    path = Path(layout.WHITELIST_FILE)
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def _print_gate_summary(chapter: int, report: dict) -> None:
    status = "通过" if report["passed"] else "未通过"
    print(f"第 {chapter} 章机器门禁：{status}（字数 {report['word_count']}）")
    for verdict in report["layer1"]["verdicts"]:
        if verdict["status"] in ("red", "yellow"):
            print(f"  [指标·{verdict['status']}] {verdict['label']} = {verdict['value']} → {verdict['direction']}")
    for warning in report["layer1"]["warnings"]:
        print(f"  [警告] {warning}")
    for violation in report["layer2"]["blocking"]:
        print(f"  [lint·阻断] {violation['description']} 命中 {violation['count']} 次（限 {violation['limit']}）→ {violation['direction']}")
    print(f"  lint 密度：{report['layer2']['density_grade']}（advisory 明细见 {layout.qa_gate(chapter)}）")


def _cmd_gate(args: argparse.Namespace) -> int:
    state = load_state(layout.STATE_FILE)
    text = read_text(args.file)
    previous = read_text(args.previous_file) if args.previous_file else None
    report = run_gate(text, whitelist=_read_whitelist(), previous_text=previous)
    chapter = args.chapter
    target = Path(layout.qa_gate(chapter))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    state = record_gate(state, chapter, "layer1", report["layer1"]["passed"])
    state = record_gate(state, chapter, "layer2", report["layer2"]["passed"])
    save_state(layout.STATE_FILE, state)
    _print_gate_summary(chapter, report)
    return EXIT_OK if report["passed"] else EXIT_GATE_FAILED


def _cmd_commit(args: argparse.Namespace) -> int:
    state = load_state(layout.STATE_FILE)
    try:
        changes = json.loads(read_text(args.changes))
    except json.JSONDecodeError as exc:
        raise GateError(f"变更文件不是合法 JSON：{args.changes}：{exc}") from exc
    chapter = args.chapter
    if not Path(layout.chapter_final(chapter)).exists():
        print(f"缺少终稿文件：{layout.chapter_final(chapter)}（机器门禁与 rubric 通过后保存终稿再提交）")
        return EXIT_GATE_FAILED
    if not Path(layout.qa_rubric(chapter)).exists():
        print(f"缺少第三层 rubric 报告：{layout.qa_rubric(chapter)}（按 rubric 协议完成审查后重试）")
        return EXIT_GATE_FAILED
    state = record_gate(state, chapter, "layer3", True)
    state = apply_changes(state, changes)
    save_state(layout.STATE_FILE, state)
    render_projections(state, layout.PROJECTIONS_DIR)
    print(
        f"第 {chapter} 章已提交（revision {state['progress']['state_revision']}），"
        f"下一章：第 {state['progress']['current_chapter']} 章，投影已重新渲染"
    )
    return EXIT_OK


def _cmd_check(args: argparse.Namespace) -> int:
    state = load_state(layout.STATE_FILE)
    mismatches = check_projections(state, layout.PROJECTIONS_DIR)
    if mismatches:
        print("投影不一致：")
        for item in mismatches:
            print(f"  - {item}")
        return EXIT_GATE_FAILED
    print("投影与状态一致")
    return EXIT_OK


def _cmd_export(args: argparse.Namespace) -> int:
    if args.platform != "fanqie":
        raise GateError(f"暂不支持平台：{args.platform}（当前仅 fanqie）")
    files = export_fanqie(".")
    print(f"已导出 {len(files)} 章到 {layout.EXPORTS_DIR}/fanqie/")
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg", description="三重门：会拒绝的网文流水线")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="初始化书籍工作区")
    init.add_argument("--title", required=True, help="书名")
    init.add_argument("--genre", required=True, help="题材")
    init.add_argument("--platform", default="fanqie", help="目标平台（默认 fanqie）")
    init.set_defaults(func=_cmd_init)

    start = sub.add_parser("start", help="校验书魂卡，进入写作阶段")
    start.set_defaults(func=_cmd_start)

    sub.add_parser("status", help="查看进度与断点").set_defaults(func=_cmd_status)

    prewrite = sub.add_parser("prewrite", help="写前阻断检查 + 生成上下文包")
    prewrite.add_argument("--chapter", type=int, required=True, help="章号")
    prewrite.set_defaults(func=_cmd_prewrite)

    gate = sub.add_parser("gate", help="第一层+第二层机器门禁")
    gate.add_argument("--file", required=True, help="草稿/终稿文件路径")
    gate.add_argument("--chapter", type=int, required=True, help="章号")
    gate.add_argument("--previous-file", default=None, help="上一版文本（用于改稿指纹监控）")
    gate.set_defaults(func=_cmd_gate)

    commit = sub.add_parser("commit", help="提交章变更并渲染投影")
    commit.add_argument("--chapter", type=int, required=True, help="章号")
    commit.add_argument("--changes", required=True, help="章变更 JSON 文件路径")
    commit.set_defaults(func=_cmd_commit)

    sub.add_parser("check", help="校验投影一致性").set_defaults(func=_cmd_check)

    export = sub.add_parser("export", help="导出终稿")
    export.add_argument("--platform", default="fanqie", help="导出平台（默认 fanqie）")
    export.set_defaults(func=_cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (GateError, FileNotFoundError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
