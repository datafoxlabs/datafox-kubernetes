#!/usr/bin/env python3
"""Check that intended bold markers render as CommonMark strong emphasis."""

from __future__ import annotations

import argparse
from pathlib import Path

from markdown_it import MarkdownIt


def unrendered_bold(source: str, parser: MarkdownIt) -> list[tuple[int, str]]:
    """Find visible double asterisks that the parser leaves as plain text."""
    problems = []
    for token in parser.parse(source):
        if token.type != "inline":
            continue
        line = (token.map[0] + 1) if token.map else 1
        for child in token.children or []:
            if child.type == "text" and "**" in child.content:
                snippet = child.content.replace("\n", " ").strip()[:120]
                problems.append((line, snippet))
    return problems


def markdown_files(root: Path) -> list[Path]:
    """Scan authored project Markdown; leave RepoFoundry-managed sources alone."""
    paths = [root / name for name in ("README.md", "ARCHITECTURE.md", "AGENTS.md")]
    paths.extend((root / "docs").rglob("*.md"))
    return sorted(
        path
        for path in paths
        if path.is_file()
        and "docs/agent-guides/managed/" not in path.relative_to(root).as_posix()
        and "docs/.designctl/snapshots/" not in path.relative_to(root).as_posix()
    )


def self_test(parser: MarkdownIt) -> None:
    valid = (
        "**业务单元（Cell）** 是可选的一等部署维度。",
        "这里**不是**强制项。",
        "中文 **（说明）** 中文",
        "| 字段 | **推荐** |",
        "代码：`** 保留字面量 **`",
        "```text\n** 原始代码 **\n```",
    )
    invalid = (
        "**业务单元（Cell）**是可选的一等部署维度。",
        "这里** 不是**强制项。",
        "中文**（说明）**中文",
        "| 字段 | ** 推荐** |",
    )
    for source in valid:
        assert not unrendered_bold(source, parser), f"Valid emphasis rejected: {source!r}"
    for source in invalid:
        assert unrendered_bold(source, parser), f"Broken emphasis accepted: {source!r}"


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--self-test", action="store_true", help="Verify known valid and invalid cases")
    args = cli.parse_args()
    parser = MarkdownIt("commonmark").enable("table")
    if args.self_test:
        self_test(parser)
        print("Markdown emphasis self-tests passed")
        return 0

    root = Path(__file__).resolve().parent.parent
    paths = markdown_files(root)
    failures = []
    for path in paths:
        for line, snippet in unrendered_bold(path.read_text(encoding="utf-8"), parser):
            failures.append(f"{path.relative_to(root)} (block starting line {line}): {snippet!r}")

    if failures:
        print("Unrendered bold delimiters found:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print(f"Markdown emphasis parsed successfully in {len(paths)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
