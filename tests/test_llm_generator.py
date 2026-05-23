"""llm_generator.py 测试（mock LLM，不发真网络请求）。"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from llm_generator import (
    GeneratedStrategy,
    LLMClient,
    LLMNotAvailable,
    LLMStrategyGenerator,
    _strip_code_fences,
)


# --- LLMClient ----------------------------------------------------------------

def test_llm_client_default_models():
    assert LLMClient(backend="openai", api_key="x").model == "gpt-4o-mini"
    assert LLMClient(backend="anthropic", api_key="x").model == "claude-3-5-haiku-20241022"
    assert LLMClient(backend="deepseek", api_key="x").model == "deepseek-chat"


def test_llm_client_deepseek_uses_deepseek_base_url():
    c = LLMClient(backend="deepseek", api_key="x")
    assert c.base_url == "https://api.deepseek.com/v1"


def test_llm_client_openai_no_default_base_url():
    c = LLMClient(backend="openai", api_key="x")
    assert c.base_url is None


def test_llm_client_is_available_when_key_provided():
    c = LLMClient(backend="deepseek", api_key="sk-test")
    assert c.is_available() is True


def test_llm_client_is_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = LLMClient(backend="deepseek")
    assert c.is_available() is False


def test_llm_client_chat_raises_when_no_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = LLMClient(backend="deepseek")
    with pytest.raises(LLMNotAvailable):
        c.chat("system", "user")


def test_llm_client_picks_up_env_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-from-env")
    c = LLMClient(backend="deepseek")
    assert c.api_key == "sk-from-env"


def test_llm_client_explicit_model_overrides_default():
    c = LLMClient(backend="openai", api_key="x", model="gpt-4o")
    assert c.model == "gpt-4o"


# --- _strip_code_fences -------------------------------------------------------

def test_strip_code_fences_python_block():
    raw = "```python\nfrom freqtrade.strategy import IStrategy\n```"
    assert _strip_code_fences(raw) == "from freqtrade.strategy import IStrategy"


def test_strip_code_fences_bare_block():
    raw = "```\nclass Foo: pass\n```"
    assert _strip_code_fences(raw) == "class Foo: pass"


def test_strip_code_fences_no_block_returns_as_is():
    raw = "class Foo: pass"
    assert _strip_code_fences(raw) == "class Foo: pass"


def test_strip_code_fences_handles_leading_trailing_whitespace():
    raw = "\n\n```python\nclass Bar: pass\n```\n\n"
    assert _strip_code_fences(raw) == "class Bar: pass"


# --- LLMStrategyGenerator -----------------------------------------------------

VALID_STRATEGY_CODE = """from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class RSIMomentum(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    minimal_roi = {"0": 0.05, "30": 0.02}
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


def _mock_client(response: str = VALID_STRATEGY_CODE) -> LLMClient:
    c = LLMClient(backend="deepseek", api_key="sk-test")
    c.chat = MagicMock(return_value=response)
    return c


def test_generate_raises_when_llm_unavailable(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    g = LLMStrategyGenerator()
    with pytest.raises(LLMNotAvailable):
        g.generate(name="X", description="RSI strategy")


def test_generate_returns_generated_strategy():
    client = _mock_client()
    g = LLMStrategyGenerator(llm_client=client)
    result = g.generate(name="RSIMomentum", description="RSI < 30 入场")
    assert isinstance(result, GeneratedStrategy)
    assert result.name == "RSIMomentum"
    assert "class RSIMomentum(IStrategy)" in result.code
    assert result.backend == "deepseek"


def test_generate_strips_markdown_fences():
    fenced = f"```python\n{VALID_STRATEGY_CODE}\n```"
    client = _mock_client(response=fenced)
    g = LLMStrategyGenerator(llm_client=client)
    result = g.generate(name="X", description="foo")
    assert not result.code.startswith("```")
    assert "from freqtrade.strategy import IStrategy" in result.code


def test_generate_sanitizes_name_with_special_chars():
    client = _mock_client()
    g = LLMStrategyGenerator(llm_client=client)
    result = g.generate(name="RSI-Momentum!@#", description="foo")
    assert result.name == "RSIMomentum"


def test_generate_prepends_s_if_name_starts_with_digit():
    client = _mock_client()
    g = LLMStrategyGenerator(llm_client=client)
    result = g.generate(name="123abc", description="foo")
    assert result.name == "S123abc"


def test_generate_fallback_name_for_empty_clean():
    client = _mock_client()
    g = LLMStrategyGenerator(llm_client=client)
    result = g.generate(name="!@#$%^", description="foo")
    assert result.name == "GeneratedStrategy"


def test_generate_passes_timeframe_and_stoploss_to_prompt():
    client = _mock_client()
    g = LLMStrategyGenerator(llm_client=client)
    g.generate(name="X", description="foo", timeframe="1h", stoploss_pct=0.08)
    # client.chat 被调用，user prompt 里应包含 timeframe 和 stoploss
    args = client.chat.call_args
    user_prompt = args[0][1]  # 第二个位置参数是 user message
    assert "1h" in user_prompt
    assert "-0.08" in user_prompt


def test_generate_stoploss_always_negative_in_prompt():
    """无论用户传正还是负，prompt 里都应该是负数。"""
    client = _mock_client()
    g = LLMStrategyGenerator(llm_client=client)
    g.generate(name="X", description="foo", stoploss_pct=0.05)
    user_prompt = client.chat.call_args[0][1]
    assert "-0.05" in user_prompt


def test_generate_preserves_raw_llm_response():
    client = _mock_client(response="```python\nfoo\n```")
    g = LLMStrategyGenerator(llm_client=client)
    result = g.generate(name="X", description="foo")
    assert result.raw_llm_response == "```python\nfoo\n```"
    assert result.code == "foo"
