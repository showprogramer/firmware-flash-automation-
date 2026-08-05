"""specs/active Task 文件状态一致性检查。

检查项：
1. 表头「当前状态」与 Task DoD 勾选一致性；
2. 「待人工验证」状态与人工验证记录是否冲突；
3. Review / CHANGELOG / 迁移说明是否已标记（已完成 / 已同步 / 已关闭 / 不适用）；
4. 「完成 commit」：提交前阶段允许占位词「本次提交」；提交后阶段必须回填
   真实 hash 且存在于 git 历史，提交信息与任务 ID 不符时提示核对。

用法：
    python scripts/check_task_sync.py --pre-commit --strict   # 提交前门槛
    python scripts/check_task_sync.py --strict                # 提交后门槛（默认）
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ERROR = "error"
WARNING = "warning"
INFO = "info"

PENDING_STATE_RE = re.compile(r"待|等待")
DONE_STATE_RE = re.compile(r"✅|人工验证通过|已完成")
HEADING_RE = re.compile(r"^##\s+(.+)$")
STATE_ROW_RE = re.compile(r"^\|\s*当前状态\s*\|\s*(.+?)\s*\|")
COMMIT_ROW_RE = re.compile(r"^\|\s*完成 commit\s*\|\s*(.+?)\s*\|")
CHECKBOX_RE = re.compile(r"^-\s+\[([ x])\]\s*")
HASH_RE = re.compile(r"\b([0-9a-f]{7,40})\b")
MARKED_RE = re.compile(r"已完成|已同步|已关闭|已归档|不适用")
MANUAL_VERIFY_RE = re.compile(r"人工验证.*?(?:已完成|完成|通过)")
CLOSURE_KEYS = (
    ("Review", re.compile(r"Review", re.IGNORECASE)),
    ("CHANGELOG", re.compile(r"CHANGELOG", re.IGNORECASE)),
    ("迁移说明", re.compile(r"迁移说明")),
)
VERIFY_FIELDS = (
    ("平台", re.compile(r"平台\s*[:：]|平台\s*\|")),
    ("命令", re.compile(r"命令\s*[:：]|命令\s*\|")),
    ("结果", re.compile(r"结果\s*[:：]|结果\s*\|")),
    ("已知平台差异", re.compile(r"已知平台差异")),
    ("提交", re.compile(r"提交\s*[:：]|\bcommit\b", re.IGNORECASE)),
)


@dataclass
class Finding:
    severity: str
    line: int
    message: str


def parse_row(lines: list[str], name: str) -> str | None:
    for line in lines:
        if name == "当前状态":
            m = STATE_ROW_RE.search(line)
        else:
            m = COMMIT_ROW_RE.search(line)
        if m:
            return m.group(1).strip()
    return None


def section_span(
    lines: list[str], start_names: tuple[str, ...], end_names: tuple[str, ...]
) -> tuple[int, int] | None:
    starts = [
        i
        for i, line in enumerate(lines)
        if (m := HEADING_RE.match(line)) and any(n in m.group(1) for n in start_names)
    ]
    if not starts:
        return None
    start = starts[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if (m := HEADING_RE.match(lines[i])) and any(
            n in m.group(1) for n in end_names
        ):
            end = i
            break
    return start, end


def classify_state(value: str) -> str:
    if PENDING_STATE_RE.search(value):
        return "pending"
    if DONE_STATE_RE.search(value):
        return "done"
    return "unknown"


def hash_exists(h: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{h}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def commit_subject(h: str) -> str | None:
    result = subprocess.run(
        ["git", "log", "--format=%s", "-1", h],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def subject_matches_task(subject: str, task_id: str) -> bool:
    if task_id in subject:
        return True
    m = re.search(r"TASK-(\d{8})", task_id)
    return bool(m and f"TASK-{m.group(1)}" in subject)


def check_closure(lines: list[str], span: tuple[int, int] | None) -> list[Finding]:
    findings: list[Finding] = []
    if span is None:
        return [
            Finding(WARNING, 0, "缺少「验证记录 / 文档与收口」段落，无法核对收口标记")
        ]
    region = lines[span[0] : span[1]]
    for name, pattern in CLOSURE_KEYS:
        matched = [
            i
            for i, line in enumerate(region, start=span[0] + 1)
            if pattern.search(line)
        ]
        if not matched:
            findings.append(
                Finding(WARNING, span[0] + 1, f"「{name}」未标记（需写已完成/不适用）")
            )
        elif not any(MARKED_RE.search(lines[i - 1]) for i in matched):
            findings.append(
                Finding(WARNING, matched[0], f"「{name}」行存在但未写明完成/不适用标记")
            )
    for name, pattern in VERIFY_FIELDS:
        if not any(pattern.search(line) for line in region):
            findings.append(
                Finding(
                    WARNING,
                    span[0] + 1,
                    f"验证记录缺少「{name}」字段（模板见 agent-workflow.md）",
                )
            )
    return findings


def check_task(path: Path, pre_commit: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    state = parse_row(lines, "当前状态")
    commit = parse_row(lines, "完成 commit")
    closure = section_span(lines, ("验证记录", "收口"), ("DoD",))

    if state is None:
        findings.append(Finding(WARNING, 0, "缺少「当前状态」行"))
    else:
        status = classify_state(state)
        if status == "unknown":
            findings.append(Finding(WARNING, 1, f"无法识别当前状态：「{state}」"))
        elif status == "done" and commit is not None and "待提交" in commit:
            findings.append(
                Finding(ERROR, 1, "完成态任务「完成 commit」仍为「待提交」")
            )

    if commit is None:
        findings.append(Finding(WARNING, 0, "缺少「完成 commit」行"))
    elif (
        not pre_commit
        and state is not None
        and classify_state(state) == "done"
        and re.search(r"本次提交|当前提交", commit)
    ):
        findings.append(
            Finding(WARNING, 1, "完成态但「完成 commit」为占位词，请回填实际 hash")
        )
    else:
        for h in HASH_RE.findall(commit):
            if not hash_exists(h):
                findings.append(
                    Finding(ERROR, 1, f"「完成 commit」填写的 hash {h} 不存在")
                )
            elif not pre_commit:
                subject = commit_subject(h)
                if subject and not subject_matches_task(subject, path.stem):
                    findings.append(
                        Finding(
                            INFO,
                            1,
                            f"commit {h} 的提交信息未包含任务 ID，请核对 hash 归属：「{subject}」",
                        )
                    )

    dod = section_span(lines, ("DoD",), ())
    if dod is None:
        findings.append(Finding(WARNING, 0, "缺少「Task DoD」段落"))
    else:
        dod_lines = lines[dod[0] : dod[1]]
        unchecked = [
            i
            for i, line in enumerate(dod_lines, start=dod[0] + 1)
            if (m := CHECKBOX_RE.match(line)) and m.group(1) == " "
        ]
        if state is not None and classify_state(state) == "done" and unchecked:
            findings.append(
                Finding(
                    ERROR, unchecked[0], f"完成态但 DoD 存在 {len(unchecked)} 项未勾选"
                )
            )
        if state is not None and classify_state(state) == "pending" and not unchecked:
            findings.append(
                Finding(INFO, 1, "DoD 已全勾但状态仍为待验证，注意回写表头")
            )

    if closure is not None:
        region = lines[closure[0] : closure[1]]
        if (
            state is not None
            and classify_state(state) == "pending"
            and any(MANUAL_VERIFY_RE.search(line) for line in region)
        ):
            findings.append(
                Finding(
                    ERROR,
                    closure[0] + 1,
                    "状态为「待人工验证」但验证记录已标记人工验证完成",
                )
            )
        if (
            state is not None
            and classify_state(state) == "done"
            and not any(re.search(r"人工验证|人工检查", line) for line in region)
        ):
            findings.append(
                Finding(
                    WARNING,
                    closure[0] + 1,
                    "完成态但缺少人工验证记录（低风险任务请标记不适用）",
                )
            )

    findings.extend(check_closure(lines, closure))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 文件状态一致性检查")
    parser.add_argument(
        "--dir", default="specs/active", help="任务文件目录（默认 specs/active）"
    )
    parser.add_argument(
        "--strict", action="store_true", help="warning 也以非零退出码阻断（提交门槛）"
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="提交前阶段：允许「完成 commit」为占位词（本次提交），不校验 hash 归属",
    )
    args = parser.parse_args()

    files = sorted(Path(args.dir).glob("TASK-*.md"))
    if not files:
        print(f"未找到任务文件：{args.dir}/TASK-*.md")
        return 1

    errors = 0
    warnings = 0
    infos = 0
    for path in files:
        findings = check_task(path, pre_commit=args.pre_commit)
        if findings:
            print(f"{path}")
            for f in sorted(findings, key=lambda x: (x.severity != ERROR, x.line)):
                print(f"  {f.severity}:{f.line} {f.message}")
                if f.severity == ERROR:
                    errors += 1
                elif f.severity == WARNING:
                    warnings += 1
                else:
                    infos += 1

    summary = (
        f"{len(files)} 个任务文件：{errors} error, {warnings} warning, {infos} info"
    )
    print(f"\n{summary}")
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
