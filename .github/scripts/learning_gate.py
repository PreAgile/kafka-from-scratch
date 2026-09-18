#!/usr/bin/env python3
"""학습 규칙 게이트.

코드 품질이 아니라 '학습 절차를 지켰는가'를 검사한다.
이 게이트가 존재하는 이유는 단순하다. 바빠지면 사람은 재현 테스트를
건너뛰고 구현부터 한다. 그 순간 이 저장소는 코드 옮겨 적기가 된다.
"""
import json
import os
import re
import subprocess
import sys

FAIL = []
WARN = []


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True).stdout


def changed_files(base):
    out = sh("git", "diff", "--name-only", f"{base}...HEAD")
    return [f for f in out.splitlines() if f.strip()]


def rule_reference_is_frozen(files):
    """reference/ 는 원본 그대로여야 비교 기준으로서 의미가 있다."""
    touched = [f for f in files if f.startswith("reference/")]
    if touched:
        FAIL.append(
            "reference/ 아래 파일이 수정되었습니다: "
            + ", ".join(touched)
            + "\n  원본은 비교 기준입니다. 고치고 싶으면 내 구현 쪽에 복사해서 고치세요."
        )


def rule_implementation_needs_tests(files):
    """구현만 있고 테스트가 없으면 재현 테스트를 건너뛴 것이다."""
    src = [f for f in files
           if f.endswith(".java")
           and not f.startswith("reference/")
           and "/test/" not in f
           and not f.endswith("Test.java")]
    tests = [f for f in files
             if ("/test/" in f or f.endswith("Test.java"))
             and not f.startswith("reference/")]
    if src and not tests:
        FAIL.append(
            "프로덕션 코드 %d개가 바뀌었는데 테스트 변경이 없습니다.\n"
            "  이 저장소의 규칙은 재현 테스트를 먼저 쓰는 것입니다. "
            "정말 예외라면 PR 본문에 '테스트 예외:' 로 시작하는 줄을 넣으세요." % len(src)
        )


def rule_no_wall_clock(files):
    """시뮬레이터가 결정론적이려면 프로덕션 코드가 실제 시계를 부르면 안 된다."""
    banned = [
        (r"System\.currentTimeMillis", "System.currentTimeMillis"),
        (r"System\.nanoTime", "System.nanoTime"),
        (r"Thread\.sleep", "Thread.sleep"),
        (r"Instant\.now", "Instant.now"),
    ]
    for f in files:
        if not f.endswith(".java"):
            continue
        if f.startswith("reference/") or "/test/" in f or "simulation/" in f:
            continue
        if not os.path.exists(f):
            continue
        body = open(f, encoding="utf-8", errors="replace").read()
        for pat, name in banned:
            for m in re.finditer(pat, body):
                ln = body[: m.start()].count("\n") + 1
                FAIL.append(
                    f"{f}:{ln} 에서 {name} 을 직접 호출합니다.\n"
                    "  ADR 0003 에 따라 시계는 주입받아야 합니다. Clock 인터페이스를 쓰세요."
                )


def rule_pr_body(body, is_pr):
    """PR 본문이 학습 기록으로 기능해야 한다."""
    if not body:
        if is_pr:
            FAIL.append(
                "PR 본문이 비어 있습니다. 템플릿을 채우세요.\n"
                "  '백지 설명' 이 리뷰 봇의 주 입력입니다. 이게 없으면 하네스 전체가 무용지물입니다."
            )
        else:
            WARN.append("PR 이벤트가 아니라 본문 검사를 건너뜁니다.")
        return
    if "백지 설명" not in body:
        FAIL.append(
            "PR 본문에 '백지 설명' 섹션이 없습니다.\n"
            "  코드를 보지 않고 이 변경이 무엇을 왜 하는지 산문으로 쓰세요.\n"
            "  이 글과 실제 코드의 괴리를 찾는 것이 리뷰 봇의 주 임무입니다."
        )
    filled = re.search(r"##\s*백지 설명\s*\n+(.+?)(\n##|\Z)", body, re.S)
    if filled and len(filled.group(1).strip()) < 120:
        FAIL.append("'백지 설명' 이 너무 짧습니다. 최소 몇 문장은 쓰세요.")


def rule_writing_style(files, body):
    """AGENTS.md 글쓰기 규칙. 긴 대시 금지."""
    targets = [f for f in files
               if (f.endswith(".md") or f.endswith(".java"))
               and not f.startswith("reference/")]
    for f in targets:
        if not os.path.exists(f):
            continue
        for i, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
            if "—" in line or "–" in line:
                FAIL.append(f"{f}:{i} 에 긴 대시가 있습니다. AGENTS.md 글쓰기 규칙 위반입니다.")
    if body and ("—" in body or "–" in body):
        FAIL.append("PR 본문에 긴 대시가 있습니다.")


def main():
    base = os.environ.get("BASE_SHA") or "origin/main"
    body = ""
    is_pr = False
    ev = os.environ.get("GITHUB_EVENT_PATH")
    if ev and os.path.exists(ev):
        data = json.load(open(ev))
        pr = data.get("pull_request")
        if pr is not None:
            is_pr = True
            body = pr.get("body") or ""

    files = changed_files(base)
    print("변경 파일 %d개\n" % len(files))

    rule_reference_is_frozen(files)
    rule_no_wall_clock(files)
    rule_writing_style(files, body)
    rule_pr_body(body, is_pr)
    if "테스트 예외:" not in body:
        rule_implementation_needs_tests(files)

    for w in WARN:
        print("주의: " + w)
    if FAIL:
        print("\n학습 게이트 실패 %d건\n" % len(FAIL))
        for f in FAIL:
            print("  - " + f)
        print("\n이 게이트는 코드 품질이 아니라 절차를 봅니다. 우회하지 말고 절차를 지키세요.")
        sys.exit(1)
    print("학습 게이트 통과")


if __name__ == "__main__":
    main()
