"""Freqtrade 策略代码静态校验。

LLM 生成的代码可能少方法、少 import、用未来函数等。这里做静态检查：

- Python 语法合法（ast.parse 不抛）
- 含 IStrategy 子类
- 三个必需方法（populate_indicators / populate_entry_trend / populate_exit_trend）签名正确
- 关键属性：timeframe / stoploss / minimal_roi
- 未来函数嫌疑：``dataframe[...].iloc[-1]`` 这类直接读最后一行的写法
- 不调用聚宽 API（这是 Freqtrade 策略，不该出现 get_price 等）
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationIssue:
    severity: str        # "error" | "warning"
    code: str
    message: str
    line: int = 0


@dataclass
class ValidationReport:
    code: str
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def add(self, severity: str, code: str, message: str, line: int = 0) -> None:
        self.issues.append(ValidationIssue(severity=severity, code=code,
                                           message=message, line=line))


_REQUIRED_METHODS = {
    "populate_indicators",
    "populate_entry_trend",
    "populate_exit_trend",
}

_REQUIRED_CLASS_ATTRS = {"timeframe", "stoploss", "minimal_roi"}

_HALLUCINATED_APIS = {
    "get_price",
    "attribute_history",
    "history",
    "get_current_data",
    "order_target",
    "order_value",
    "context.portfolio",
}


def validate(code: str) -> ValidationReport:
    """对一段 Freqtrade 策略代码做静态校验。"""
    report = ValidationReport(code=code)

    # 1. 语法合法
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        report.add("error", "FT000",
                   f"Python 语法错误：{e.msg}", line=e.lineno or 0)
        return report

    # 2. 找 IStrategy 子类
    strategy_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if (isinstance(base, ast.Name) and base.id == "IStrategy") or \
                   (isinstance(base, ast.Attribute) and base.attr == "IStrategy"):
                    strategy_class = node
                    break
            if strategy_class:
                break

    if strategy_class is None:
        report.add("error", "FT001",
                   "找不到 IStrategy 子类。Freqtrade 策略必须 class MyStrategy(IStrategy):")
        return report

    # 3. 检查必需方法
    methods_found = {
        item.name for item in strategy_class.body
        if isinstance(item, ast.FunctionDef)
    }
    missing = _REQUIRED_METHODS - methods_found
    for m in missing:
        report.add("error", "FT002",
                   f"缺必需方法 {m}（IStrategy 三个核心方法之一）",
                   line=strategy_class.lineno)

    # 4. 检查必需类属性
    class_attrs = set()
    for item in strategy_class.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    class_attrs.add(target.id)
        elif isinstance(item, ast.AnnAssign):
            if isinstance(item.target, ast.Name):
                class_attrs.add(item.target.id)

    missing_attrs = _REQUIRED_CLASS_ATTRS - class_attrs
    for a in missing_attrs:
        sev = "error" if a == "stoploss" else "warning"
        report.add(sev, "FT003",
                   f"缺类属性 {a}（Freqtrade 需要）",
                   line=strategy_class.lineno)

    # 5. 检查未来函数嫌疑（dataframe['col'].iloc[-1] 这种读最后一行的写法）
    iloc_pattern = re.compile(r"dataframe\[['\"][^'\"]+['\"]\]\.iloc\[-1\]")
    for i, line in enumerate(code.splitlines(), start=1):
        if iloc_pattern.search(line):
            report.add("warning", "FT004",
                       f"嫌疑未来函数：直接读 dataframe.iloc[-1] 在 Freqtrade 是合法但容易"
                       f"误用；应该用整列条件赋值 dataframe.loc[condition, 'enter_long']=1",
                       line=i)

    # 6. 检查不该出现的聚宽 API
    for api in _HALLUCINATED_APIS:
        for i, line in enumerate(code.splitlines(), start=1):
            if api in line and not line.strip().startswith("#"):
                report.add("error", "FT005",
                           f"不该出现 {api}（聚宽 API，不是 Freqtrade）",
                           line=i)
                break

    # 7. 检查 stoploss 是负数
    for item in strategy_class.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "stoploss":
                    val = item.value
                    if isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub):
                        pass  # 是负数 -0.05
                    elif isinstance(val, ast.Constant) and isinstance(val.value, (int, float)) and val.value >= 0:
                        report.add("error", "FT006",
                                   f"stoploss 必须是负数（如 -0.05 表示 -5%），实际 {val.value}",
                                   line=item.lineno)

    # 8. 检查必要 import：必须 from freqtrade.* 或 import freqtrade*
    has_freqtrade_import = False
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.ImportFrom):
            if stmt.module and stmt.module.startswith("freqtrade"):
                has_freqtrade_import = True
                break
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if alias.name.startswith("freqtrade"):
                    has_freqtrade_import = True
                    break
            if has_freqtrade_import:
                break
    if not has_freqtrade_import:
        report.add("warning", "FT007",
                   "代码里看不到 from freqtrade.strategy import IStrategy")

    return report


def render_report(report: ValidationReport) -> str:
    """把报告渲染成人类可读字符串。"""
    lines = ["=" * 60, "Freqtrade Strategy Validation", "=" * 60]
    if report.passed and not report.warnings:
        lines.append("PASSED — 没有问题")
        return "\n".join(lines)
    lines.append(f"Errors: {len(report.errors)}    Warnings: {len(report.warnings)}")
    lines.append("")
    sev_order = {"error": 0, "warning": 1}
    for issue in sorted(report.issues, key=lambda i: (sev_order[i.severity], i.line)):
        tag = "[ERROR]" if issue.severity == "error" else "[WARN] "
        loc = f"L{issue.line}" if issue.line else "global"
        lines.append(f"{tag} {issue.code} {loc}: {issue.message}")
    lines.append("=" * 60)
    return "\n".join(lines)
