"""strategy_validator.py 测试。

每个 FT0XX 错误码用一段刻意编造的"问题代码"触发。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from strategy_validator import (
    ValidationReport,
    render_report,
    validate,
)


VALID_CODE = """from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class GoodStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    minimal_roi = {"0": 0.05}
    stoploss = -0.05
    process_only_new_candles = True
    startup_candle_count = 30

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["rsi"] < 30, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["rsi"] > 70, "exit_long"] = 1
        return dataframe
"""


# --- happy path ---------------------------------------------------------------

def test_valid_code_passes():
    report = validate(VALID_CODE)
    assert report.passed
    assert len(report.errors) == 0


def test_report_is_validation_report():
    report = validate(VALID_CODE)
    assert isinstance(report, ValidationReport)
    assert report.code == VALID_CODE


# --- FT000 语法错误 -----------------------------------------------------------

def test_ft000_syntax_error():
    bad = "class Foo(IStrategy:\n    pass"  # 漏右括号
    report = validate(bad)
    assert not report.passed
    codes = {i.code for i in report.errors}
    assert "FT000" in codes


# --- FT001 缺 IStrategy 子类 --------------------------------------------------

def test_ft001_no_istrategy_subclass():
    bad = """class Foo:
    pass

class Bar(SomethingElse):
    pass
"""
    report = validate(bad)
    assert not report.passed
    assert any(i.code == "FT001" for i in report.errors)


def test_ft001_allows_qualified_istrategy_base():
    """from freqtrade.strategy.interface import IStrategy; class X(interface.IStrategy)."""
    code = """from freqtrade.strategy import interface

class S(interface.IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(code)
    # 不应该报 FT001
    assert not any(i.code == "FT001" for i in report.errors)


# --- FT002 缺必需方法 ---------------------------------------------------------

def test_ft002_missing_populate_indicators():
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.05}

    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    missing_msgs = [i.message for i in report.errors if i.code == "FT002"]
    assert any("populate_indicators" in m for m in missing_msgs)


def test_ft002_missing_all_three_methods():
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.05}
"""
    report = validate(bad)
    ft002s = [i for i in report.errors if i.code == "FT002"]
    assert len(ft002s) == 3


# --- FT003 缺类属性 -----------------------------------------------------------

def test_ft003_missing_stoploss_is_error():
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    stoploss_issues = [i for i in report.issues
                       if i.code == "FT003" and "stoploss" in i.message]
    assert len(stoploss_issues) == 1
    assert stoploss_issues[0].severity == "error"


def test_ft003_missing_timeframe_is_warning():
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    stoploss = -0.05
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    tf_issues = [i for i in report.issues
                 if i.code == "FT003" and "timeframe" in i.message]
    assert len(tf_issues) == 1
    assert tf_issues[0].severity == "warning"


# --- FT004 未来函数嫌疑 -------------------------------------------------------

def test_ft004_iloc_minus_one_warning():
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata):
        last_close = dataframe['close'].iloc[-1]
        return dataframe

    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    ft004 = [i for i in report.warnings if i.code == "FT004"]
    assert len(ft004) >= 1


# --- FT005 聚宽 API 幻觉 ------------------------------------------------------

def test_ft005_joinquant_api_get_price():
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata):
        prices = get_price("000001.XSHE", count=10)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    assert any(i.code == "FT005" for i in report.errors)


def test_ft005_ignores_api_in_comments():
    code = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.05}

    # 注意：不要用 get_price（聚宽 API）
    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(code)
    assert not any(i.code == "FT005" for i in report.errors)


# --- FT006 stoploss 必须负数 --------------------------------------------------

def test_ft006_positive_stoploss():
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = 0.05
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    assert any(i.code == "FT006" for i in report.errors)


def test_ft006_negative_stoploss_ok():
    report = validate(VALID_CODE)
    assert not any(i.code == "FT006" for i in report.errors)


# --- FT006 stoploss 注解赋值也要查 -------------------------------------------

def test_ft006_positive_stoploss_annotated():
    """stoploss: float = 0.05 这种带注解的正数也得报。"""
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss: float = 0.05
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    assert any(i.code == "FT006" for i in report.errors)


# --- FT007 缺 freqtrade import ----------------------------------------------

def test_ft007_missing_freqtrade_import():
    bad = """from pandas import DataFrame

class S:
    IStrategy = object  # 伪装

class S2(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    assert any(i.code == "FT007" for i in report.warnings)


# --- FT008 minimal_roi 缺 "0" 键 ---------------------------------------------

def test_ft008_minimal_roi_missing_zero_key():
    """minimal_roi 没有 "0" 键，freqtrade 在 ROI 检查时 max() 空列表会崩。"""
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"30": 0.02, "60": 0.01}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    assert any(i.code == "FT008" for i in report.errors)


def test_ft008_minimal_roi_with_zero_key_ok():
    report = validate(VALID_CODE)  # minimal_roi = {"0": 0.05}
    assert not any(i.code == "FT008" for i in report.issues)


def test_ft008_skipped_when_roi_not_a_literal_dict():
    """minimal_roi 用变量/函数构造时无法静态判断，不应误报 FT008。"""
    code = """from freqtrade.strategy import IStrategy

def _build_roi():
    return {"0": 0.05}

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = _build_roi()

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(code)
    assert not any(i.code == "FT008" for i in report.issues)


# --- FT009 minimal_roi 键必须是字符串 ----------------------------------------

def test_ft009_minimal_roi_int_keys():
    """LLM 常写成 {0: .., 30: ..}，freqtrade 约定 key 是字符串分钟数。"""
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {0: 0.05, 30: 0.02}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_entry_trend(self, dataframe, metadata): return dataframe
    def populate_exit_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    assert any(i.code == "FT009" for i in report.warnings)


def test_ft009_string_keys_ok():
    report = validate(VALID_CODE)
    assert not any(i.code == "FT009" for i in report.issues)


# --- FT010 用了已废弃的 v2 接口（populate_buy/sell_trend）---------------------

def test_ft010_deprecated_buy_sell_interface():
    """老接口 populate_buy_trend / populate_sell_trend：给针对性提示，而非泛泛 FT002。"""
    bad = """from freqtrade.strategy import IStrategy

class S(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.05}

    def populate_indicators(self, dataframe, metadata): return dataframe
    def populate_buy_trend(self, dataframe, metadata): return dataframe
    def populate_sell_trend(self, dataframe, metadata): return dataframe
"""
    report = validate(bad)
    codes = {i.code for i in report.errors}
    assert "FT010" in codes
    # 给了 FT010 针对性提示后，不应该再为 entry/exit 重复报 FT002
    assert "FT002" not in codes


def test_ft010_not_triggered_for_correct_interface():
    report = validate(VALID_CODE)
    assert not any(i.code == "FT010" for i in report.issues)


# --- render_report ------------------------------------------------------------

def test_render_report_passed_no_warnings():
    out = render_report(validate(VALID_CODE))
    assert "PASSED" in out


def test_render_report_with_errors():
    bad = "class X:\n    pass"  # 没继承 IStrategy
    out = render_report(validate(bad))
    assert "FT001" in out
    assert "[ERROR]" in out


def test_render_report_orders_errors_before_warnings():
    """两种 severity 都有时，error 应排在 warning 前。"""
    bad = """from pandas import DataFrame

class S(IStrategy):
    timeframe = "5m"

    def populate_indicators(self, dataframe, metadata): return dataframe
"""
    # 这段：缺 stoploss (error) + 缺其他 (errors) + 缺 freqtrade import (warning)
    out = render_report(validate(bad))
    error_idx = out.find("[ERROR]")
    warn_idx = out.find("[WARN]")
    if error_idx != -1 and warn_idx != -1:
        assert error_idx < warn_idx


# --- 边界：空代码 -------------------------------------------------------------

def test_empty_code_fails_no_class():
    report = validate("")
    assert not report.passed
    assert any(i.code == "FT001" for i in report.errors)


def test_only_imports_no_class():
    report = validate("from freqtrade.strategy import IStrategy\n")
    assert not report.passed
    assert any(i.code == "FT001" for i in report.errors)
