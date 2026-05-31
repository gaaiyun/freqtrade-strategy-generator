"""LLM 驱动的 Freqtrade 策略生成。

给一句话策略描述（"RSI 超卖 + 双均线趋势确认 + 5% 止损"），LLM 生成完整
``IStrategy`` 子类代码，含 ``populate_indicators`` / ``populate_entry_trend``
/ ``populate_exit_trend`` 三个核心方法，以及 ``minimal_roi`` / ``stoploss``
等关键参数。

设计目标：生成出的代码可直接放到 Freqtrade ``user_data/strategies/`` 跑
``freqtrade backtesting``，不用人工调。

LLMClient 适配 openai / anthropic / deepseek，缺 key 时 raise（不静默
fallback 到手写模板，因为 LLM 生成本身就是核心目的）。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal, Optional


LLMBackend = Literal["openai", "anthropic", "deepseek"]
Timeframe = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d"]


class LLMNotAvailable(RuntimeError):
    pass


SYSTEM_PROMPT = """你是一名 Freqtrade 策略代码生成专家。任务：把用户的一句话
策略描述变成完整的 IStrategy 子类。

输出要求：

1. **只输出 Python 代码**，不要任何前后缀文字、不要 markdown ```python``` 包裹
2. 必须含完整可跑结构：
   - `from freqtrade.strategy import IStrategy`
   - `from pandas import DataFrame`
   - `import talib.abstract as ta` （如果用 talib 指标）
   - 一个 IStrategy 子类，类名按用户给的 name 参数
3. 类必须含以下属性：
   - `INTERFACE_VERSION = 3`
   - `timeframe`（按用户指定）
   - `minimal_roi`（用户没指定时给合理默认值）
   - `stoploss`（用户没指定时给 -0.05）
   - `process_only_new_candles = True`
   - `startup_candle_count` 设合理值（默认 30）
4. 必须实现三个方法，签名严格保持：
   - `def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:`
   - `def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:`
   - `def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:`
5. **绝对不能**：
   - 用未来函数（不能用未来 K 线数据做信号）
   - 在 entry/exit 里直接读 `dataframe['close'].iloc[-1]` —— 必须用整列条件赋值
   - 调任何不存在的 talib 函数
6. 在 indicators 旁加简短注释说明"为什么用这个指标"
7. minimal_roi 表的 key 必须是字符串形式的整数（分钟数）："0" / "30" / "60"
"""


@dataclass(frozen=True)
class GeneratedStrategy:
    name: str
    description: str
    code: str
    backend: str
    raw_llm_response: Optional[str] = None


class LLMClient:
    def __init__(
        self,
        backend: LLMBackend = "deepseek",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        temperature: float = 0.2,
    ):
        self.backend = backend
        self.timeout = timeout
        self.temperature = temperature
        self.api_key = api_key or self._default_key(backend)
        self.base_url = base_url or self._default_base_url(backend)
        self.model = model or self._default_model(backend)

    @staticmethod
    def _default_key(backend: LLMBackend) -> Optional[str]:
        return {
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
            "deepseek": os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"),
        }.get(backend)

    @staticmethod
    def _default_base_url(backend: LLMBackend) -> Optional[str]:
        # 环境变量优先（自建网关/代理、或 deepseek 换 endpoint 时不用改代码）
        env = {
            "openai": "OPENAI_BASE_URL",
            "anthropic": "ANTHROPIC_BASE_URL",
            "deepseek": "DEEPSEEK_BASE_URL",
        }.get(backend)
        if env and os.getenv(env):
            return os.getenv(env)
        return {"deepseek": "https://api.deepseek.com/v1"}.get(backend)

    @staticmethod
    def _default_model(backend: LLMBackend) -> str:
        env = {
            "openai": "OPENAI_MODEL",
            "anthropic": "ANTHROPIC_MODEL",
            "deepseek": "DEEPSEEK_MODEL",
        }.get(backend)
        if env and os.getenv(env):
            return os.getenv(env)  # type: ignore[return-value]
        return {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-haiku-20241022",
            "deepseek": "deepseek-chat",
        }.get(backend, "gpt-4o-mini")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str) -> str:
        if not self.is_available():
            raise LLMNotAvailable(
                f"{self.backend} backend 缺 API key（环境变量 "
                f"{self.backend.upper()}_API_KEY）"
            )
        if self.backend == "anthropic":
            return self._call_anthropic(system, user)
        return self._call_openai_compatible(system, user)

    def _call_openai_compatible(self, system: str, user: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise LLMNotAvailable("缺 openai SDK：pip install openai") from e
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
        )
        return resp.choices[0].message.content or ""

    def _call_anthropic(self, system: str, user: str) -> str:
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise LLMNotAvailable("缺 anthropic SDK：pip install anthropic") from e
        kwargs = {"api_key": self.api_key, "timeout": self.timeout}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        client = Anthropic(**kwargs)
        resp = client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text if resp.content else ""


def _strip_code_fences(text: str) -> str:
    """LLM 偶尔会用 ```python 包裹，强行剥掉。"""
    text = text.strip()
    if text.startswith("```"):
        # 找到第一个换行后到结尾的 ```
        text = re.sub(r"^```(?:python|py)?\s*\n", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


class LLMStrategyGenerator:
    """主入口：自然语言描述 → IStrategy 代码。"""

    def __init__(self, llm_client: Optional[LLMClient] = None,
                 backend: LLMBackend = "deepseek"):
        self.llm_client = llm_client or LLMClient(backend=backend)

    def generate(
        self,
        name: str,
        description: str,
        timeframe: Timeframe = "5m",
        stoploss_pct: float = 0.05,
        temperature: Optional[float] = None,
    ) -> GeneratedStrategy:
        if not self.llm_client.is_available():
            raise LLMNotAvailable(
                "LLM client 没配 key，无法生成策略。"
                "v1 的硬编码模板请直接调 scripts/strategy_generator.py。"
            )

        # 类名标准化（驼峰，去非字母数字）
        clean_name = re.sub(r"[^A-Za-z0-9]", "", name) or "GeneratedStrategy"
        if not clean_name[0].isalpha():
            clean_name = "S" + clean_name

        user_prompt = (
            f"策略类名: {clean_name}\n"
            f"timeframe: {timeframe}\n"
            f"stoploss: {-abs(stoploss_pct)}（负小数表示百分比）\n\n"
            f"策略描述:\n{description}\n\n"
            f"按 system message 的要求输出完整 IStrategy 代码。"
        )

        # temperature 仅本次调用临时覆盖，结束后恢复，不污染复用的 client
        prev_temp = self.llm_client.temperature
        if temperature is not None:
            self.llm_client.temperature = temperature
        try:
            raw = self.llm_client.chat(SYSTEM_PROMPT, user_prompt)
        finally:
            self.llm_client.temperature = prev_temp
        code = _strip_code_fences(raw)

        return GeneratedStrategy(
            name=clean_name,
            description=description,
            code=code,
            backend=self.llm_client.backend,
            raw_llm_response=raw,
        )
