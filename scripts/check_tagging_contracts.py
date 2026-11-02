#!/usr/bin/env python3
"""Validate the canonical tagging registry, test IDs, and local document links."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REGISTRY = DOCS / "attribute-registry.md"
TESTS = DOCS / "tagging-contract-tests.md"

STANDARD_ROW = re.compile(
    r"^\| \[`([a-z][a-z0-9_.]+)`\]\("
    r"https://github\.com/open-telemetry/semantic-conventions/"
    r"blob/main/docs/registry/attributes/([a-z]+)\.md\) \|"
)
CASE_ROW = re.compile(r"^\| (Tag|Inst|Domain)-(\d{2}) \|")
LINK = re.compile(r"\]\(([^)]+)\)")
FILES = (
    "README.md",
    "docs/index.md",
    "docs/architecture.md",
    "docs/unified-tagging-convention.md",
    "docs/attribute-registry.md",
    "docs/kubernetes-resource-mapping.md",
    "docs/tagging-contract-tests.md",
    "docs/deployment-topology-and-isolation.md",
    "docs/implementation-and-verification.md",
)


def check_registry(errors: list[str]) -> None:
    source = REGISTRY.read_text(encoding="utf-8")
    entries: dict[str, int] = {}
    for n, line in enumerate(source.splitlines(), 1):
        match = STANDARD_ROW.match(line)
        if match is None:
            continue
        key, namespace = match.groups()
        if key in entries:
            errors.append(f"duplicate attribute {key} (lines {entries[key]} and {n})")
        entries[key] = n
        if key.split(".", 1)[0] != namespace:
            errors.append(f"registry link namespace mismatch for {key}, line {n}")
        cells = line.split("|")[1:-1]
        if len(cells) != 6 or any(not cell.strip() for cell in cells):
            errors.append(f"invalid attribute columns for {key}, line {n}")
        if len(cells) == 6 and cells[3].strip() not in (
            "Stable",
            "Development",
            "Release Candidate",
            "Deprecated",
        ):
            errors.append(f"unrecognized upstream stability for {key}, line {n}")

    for key in ("service.name", "service.version", "service.instance.id",
                "deployment.environment.name", "k8s.pod.uid", "k8s.pod.ip",
                "container.image.tags", "cloud.region", "host.ip", "server.address"):
        if key not in entries:
            errors.append(f"missing core attribute {key}")
    print(f"Registry: {len(entries)} unique standard attributes")


def check_cases(errors: list[str]) -> None:
    source = TESTS.read_text(encoding="utf-8")
    values: dict[str, list[int]] = {"Tag": [], "Inst": [], "Domain": []}
    for line in source.splitlines():
        if match := CASE_ROW.match(line):
            values[match.group(1)].append(int(match.group(2)))
    for prefix, count in (("Tag", 15), ("Inst", 8), ("Domain", 9)):
        if sorted(values[prefix]) != list(range(1, count + 1)):
            errors.append(f"{prefix} case IDs are missing, duplicated, or out of range: {values[prefix]}")
    print("Tests: " + ", ".join(f"{name}={len(ids)}" for name, ids in values.items()))


def check_links(errors: list[str]) -> None:
    n = 0
    for filename in FILES:
        doc = ROOT / filename
        text = doc.read_text(encoding="utf-8")
        fenced = False
        for line_no, line in enumerate(text.splitlines(), 1):
            if re.match(r"^\s*(`{3,}|~{3,})", line):
                fenced = not fenced
                continue
            if fenced:
                continue
            for match in LINK.finditer(line):
                target = unquote(match.group(1)).split("#", 1)[0]
                if not target or re.match(r"^[a-z][a-z0-9+.-]*:|^//", target, re.I):
                    continue
                n += 1
                if not (doc.parent / target).exists():
                    errors.append(f"missing relative link: {filename}:{line_no} => {target}")
    print(f"Links: {n} local relative targets checked")


def main() -> int:
    errors: list[str] = []
    check_registry(errors)
    check_cases(errors)
    check_links(errors)
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    print("Tagging documentation checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
