"""freqtrade-strategy-generator CLI。

子命令：
    generate <name> --desc "..."   LLM 生成 IStrategy 子类代码
    validate <file>                校验 .py 是否符合 Freqtrade 规范
    list-backends                  列 LLM backend

示例：

    python __main__.py generate RSIMomentum \\
        --desc "RSI < 30 入场 + EMA20 > EMA50 趋势确认 + 5% 止损 + 月度止盈递减" \\
        --timeframe 5m --stoploss 0.05 -o strategies/RSIMomentum.py

    python __main__.py validate strategies/RSIMomentum.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from llm_generator import LLMClient, LLMNotAvailable, LLMStrategyGenerator  # noqa: E402
from strategy_validator import render_report, validate  # noqa: E402


def cmd_generate(args) -> int:
    generator = LLMStrategyGenerator(LLMClient(backend=args.backend))
    try:
        result = generator.generate(
            name=args.name,
            description=args.desc,
            timeframe=args.timeframe,
            stoploss_pct=args.stoploss,
        )
    except LLMNotAvailable as e:
        sys.stderr.write(f"[error] {e}\n")
        return 2

    # 校验
    report = validate(result.code)

    output_path = args.output or f"{result.name}.py"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(result.code, encoding="utf-8")

    sys.stderr.write(f"[ok] 生成 {output_path}\n")
    sys.stderr.write(render_report(report) + "\n")

    if not report.passed and not args.allow_invalid:
        sys.stderr.write(
            "[error] 校验未通过；用 --allow-invalid 强制输出，或调高 LLM 模型重试\n"
        )
        return 3
    return 0


def cmd_validate(args) -> int:
    p = Path(args.file)
    if not p.exists():
        sys.stderr.write(f"[error] 找不到 {p}\n")
        return 1
    code = p.read_text(encoding="utf-8")
    report = validate(code)
    print(render_report(report))
    if args.json:
        payload = {
            "passed": report.passed,
            "n_errors": len(report.errors),
            "n_warnings": len(report.warnings),
            "issues": [
                {"severity": i.severity, "code": i.code,
                 "message": i.message, "line": i.line}
                for i in report.issues
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


def cmd_list_backends(args) -> int:
    import os as _os
    rows = [
        ("openai",    "gpt-4o-mini",                "OPENAI_API_KEY"),
        ("anthropic", "claude-3-5-haiku-20241022",  "ANTHROPIC_API_KEY"),
        ("deepseek",  "deepseek-chat",              "DEEPSEEK_API_KEY"),
    ]
    print(f"{'backend':<12} {'default model':<32} {'env var'}")
    print("-" * 70)
    for b, m, e in rows:
        cfg = "yes" if _os.getenv(e) else "no"
        print(f"{b:<12} {m:<32} {e}  (configured: {cfg})")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ftgen", description="Freqtrade 策略 LLM 生成器")
    sub = p.add_subparsers(dest="cmd", required=True)
    common_backends = ["openai", "anthropic", "deepseek"]
    timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

    sp = sub.add_parser("generate", help="LLM 生成 IStrategy 代码")
    sp.add_argument("name", help="策略类名（驼峰）")
    sp.add_argument("--desc", required=True, help="一句话策略描述")
    sp.add_argument("--timeframe", default="5m", choices=timeframes)
    sp.add_argument("--stoploss", type=float, default=0.05,
                    help="止损百分比（正数，会自动加负号）")
    sp.add_argument("--backend", default="deepseek", choices=common_backends)
    sp.add_argument("--allow-invalid", action="store_true",
                    help="即使校验不通过也保存输出文件")
    sp.add_argument("-o", "--output")
    sp.set_defaults(func=cmd_generate)

    sp = sub.add_parser("validate", help="校验策略文件是否合规")
    sp.add_argument("file")
    sp.add_argument("--json", action="store_true", help="也输出 JSON 格式")
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("list-backends")
    sp.set_defaults(func=cmd_list_backends)

    return p


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
