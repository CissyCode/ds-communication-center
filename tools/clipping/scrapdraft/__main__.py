"""사용법:
  python -m scrapdraft recommend 검색결과.xlsx [--date 2026-11-02] [--config config.yaml]
  python -m scrapdraft diff 확정목차.xlsx --date 2026-11-02
  python -m scrapdraft analyze 과거목차폴더
  python -m scrapdraft status
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .config import load_config
from .engine import build_draft
from .excel_io import file_sha256, read_export
from .ledger import Ledger
from .report import write_report
from .review import analyze_past, diff_against_final


def _out(args) -> Path:
    return Path(args.out)


def cmd_recommend(args) -> int:
    cfg = load_config(args.config, [args.issues, args.today])
    target = date.fromisoformat(args.date) if args.date else date.today()
    src = Path(args.input)
    df = read_export(src)
    ledger = Ledger(_out(args) / "ledger.sqlite")
    sha = file_sha256(src)
    prev = ledger.same_input_before(target, sha, cfg.sha256)
    run_id = ledger.start_run(target, str(src), sha, cfg.sha256, len(df))

    missing = {"title", "media", "serial", "kind", "page"} - set(df.attrs.get("has_columns", []))
    if missing:
        print(f"[주의] 엑셀에 없는 항목: {', '.join(sorted(missing))} — 엑셀 저장 옵션에서 체크해 주세요.")

    now = datetime.combine(target, datetime.strptime(args.now, "%H:%M").time()) if args.now else None
    res = build_draft(df, cfg, target, confirmed_empty=args.confirmed_empty or [], now=now)
    ledger.step(run_id, "선정·배열 완료")
    new = ledger.record_candidates(run_id, target, res.selected)
    res.selected["new"] = res.selected["key"].map(lambda k: "신규" if k in new else "")
    ledger.step(run_id, "원장 기록 완료")

    out = _out(args) / f"검토초안_{target.isoformat()}_run{run_id}.xlsx"
    write_report(out, res, {
        "대상 일자": target.isoformat(), "실행 번호": run_id, "입력 파일": src.name,
        "입력 기사 수": len(df), "추천": len(res.selected), "참고": len(res.reference), "제외·중복": len(res.removed),
        "이번 실행 신규 추천": len(new), "전체 상태": res.overall,
        "동일 입력 이전 실행": prev or "", "규칙 해시": cfg.sha256[:12],
        **({"분량(참고 범위, 자르지 않음)": f"{len(res.selected)}건 / {cfg.volume_range[0]}~{cfg.volume_range[1]}건"}
           if cfg.volume_range else {}),
    })
    ledger.finish_run(run_id, res.overall, len(res.selected), res.paper_status)

    print(f"전체 상태: {res.overall}")
    print(res.paper_status.to_string(index=False))
    print(f"추천 {len(res.selected)}건 (신규 {len(new)}) / 참고 {len(res.reference)} / 제외·중복 {len(res.removed)}")
    print(f"결과: {out}")
    return 0 if res.overall == "완료" else 2


def cmd_diff(args) -> int:
    target = date.fromisoformat(args.date)
    ledger = Ledger(_out(args) / "ledger.sqlite")
    rec = ledger.recommended(target)
    if not rec:
        print(f"{target} 추천 기록이 없습니다. recommend를 먼저 실행해 주세요.")
        return 1
    rows = diff_against_final(rec, read_export(args.final))
    ledger.record_diff(target, rows)
    df = pd.DataFrame(rows)
    out = _out(args) / f"검토결과비교_{target.isoformat()}.xlsx"
    df.rename(columns={"key": "기사 키", "action": "구분", "rec_rank": "추천순번", "final_rank": "확정순번",
                       "media": "매체", "title": "기사 제목"}).to_excel(out, index=False)
    print(df["action"].value_counts().to_string())
    print(f"결과: {out}")
    return 0


def cmd_analyze(args) -> int:
    folder = Path(args.folder)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".xlsx", ".xls", ".csv"))
    if not files:
        print("분석할 엑셀이 없습니다.")
        return 1
    result = analyze_past(files)
    out = _out(args) / "과거스크랩분석.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        for name, df in result.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
    print(result["매체순서 추정"].head(20).to_string(index=False))
    print(f"결과: {out}")
    return 0


def cmd_status(args) -> int:
    ledger = Ledger(_out(args) / "ledger.sqlite")
    for r in ledger.last_runs():
        run_id, d, started, finished, step, overall, n_in, n_sel = r
        state = overall if finished else f"중단됨(마지막 단계: {step})"
        print(f"#{run_id} {d} 시작 {started} | {state} | 입력 {n_in} → 추천 {n_sel}")
    return 0


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="scrapdraft", description="스크랩마스터 조간 스크랩 검토 초안 도구")
    p.add_argument("--config", default=str(here / "config.yaml"))
    p.add_argument("--issues", default=None, help="현안 규칙 파일(선택, 만료일 필수)")
    p.add_argument("--today", default=None, help="당일 지시 파일(선택, 예: 오늘 보도자료 키워드)")
    p.add_argument("--out", default=str(here / "output"))
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("recommend", help="검색결과 엑셀 → 검토 초안")
    r.add_argument("input")
    r.add_argument("--date")
    r.add_argument("--confirmed-empty", nargs="*", help="뉴스 탭에서 수집은 확인했지만 해당 기사가 없는 신문")
    r.add_argument("--now", help="상태 판정 기준 시각(HH:MM, 기본은 현재 시각)")
    r.set_defaults(fn=cmd_recommend)

    d = sub.add_parser("diff", help="확정 목차 엑셀과 추천안 비교")
    d.add_argument("final")
    d.add_argument("--date", required=True)
    d.set_defaults(fn=cmd_diff)

    a = sub.add_parser("analyze", help="과거 완성본 목차 엑셀 폴더 분석")
    a.add_argument("folder")
    a.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("status", help="최근 실행 기록")
    s.set_defaults(fn=cmd_status)

    args = p.parse_args(argv)
    if args.cmd != "analyze" and args.cmd != "status" and not Path(args.config).exists():
        print(f"규칙 파일이 없습니다: {args.config}  (config.example.yaml을 복사해 config.yaml로 만드세요)")
        return 1
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
