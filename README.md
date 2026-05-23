# freqtrade-strategy-generator

把一句话策略描述变成可直接放进 [Freqtrade](https://github.com/freqtrade/freqtrade) 跑回测的 `IStrategy` 子类代码。

核心解决两件事：

1. **生成**：LLM 按 Freqtrade IStrategy v3 接口规范输出代码（含 `populate_indicators` / `populate_entry_trend` / `populate_exit_trend` 三个方法 + `timeframe` / `stoploss` / `minimal_roi` 关键属性）。
2. **校验**：生成完不能直接信，用 AST 静态检查 8 类常见 LLM 翻车（语法错、缺方法、缺属性、未来函数嫌疑、把聚宽 API 抄过来、stoploss 写成正数、漏 freqtrade import 等），有 `FT000`–`FT007` 错误码。

## v2 LLM 生成（新）

不用手写 IStrategy 模板，描述策略思路 → LLM 直接给完整可跑代码：

```bash
python __main__.py generate RSIMomentum \
    --desc "RSI < 30 入场 + EMA20 > EMA50 趋势确认 + 5% 止损 + 月度止盈递减" \
    --timeframe 5m --stoploss 0.05 -o strategies/RSIMomentum.py

# 校验现有策略文件（也能验非本工具生成的）
python __main__.py validate strategies/RSIMomentum.py --json

# 列已配置的 LLM backend
python __main__.py list-backends
```

LLM 三 backend：`openai` / `anthropic` / `deepseek`，默认 deepseek（性价比高 + 中文友好）。读取对应环境变量 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY`。

库调用：

```python
from llm_generator import LLMClient, LLMStrategyGenerator
from strategy_validator import validate, render_report

gen = LLMStrategyGenerator(LLMClient(backend="deepseek"))
result = gen.generate(
    name="RSIMomentum",
    description="RSI < 30 入场 + EMA20 > EMA50 趋势确认 + 5% 止损",
    timeframe="5m",
    stoploss_pct=0.05,
)

# result.code 是 LLM 输出的 IStrategy 完整代码
# result.name / result.backend / result.raw_llm_response 也都在

report = validate(result.code)
print(render_report(report))
if report.passed:
    open("strategies/RSIMomentum.py", "w", encoding="utf-8").write(result.code)
```

## 校验器输出的错误码

| 码 | 严重度 | 含义 |
|---|---|---|
| FT000 | error | Python 语法错（`ast.parse` 抛 SyntaxError） |
| FT001 | error | 找不到 `class X(IStrategy)` |
| FT002 | error | 缺 `populate_indicators` / `populate_entry_trend` / `populate_exit_trend` 之一 |
| FT003 | error/warn | 缺 `stoploss`（error）或 `timeframe` / `minimal_roi`（warn） |
| FT004 | warning | 在 entry/exit 里直接读 `dataframe['close'].iloc[-1]` — 容易误用 |
| FT005 | error | 出现聚宽 API（`get_price` / `attribute_history` 等），LLM 串了平台 |
| FT006 | error | `stoploss` 是正数（Freqtrade 约定必须负数） |
| FT007 | warning | 看不到 `from freqtrade.* import ...` |

校验过的策略 ≠ 一定能赚钱，但能过滤掉绝大多数"LLM 写的代码连 backtest 都跑不起来"的情况。

## v1 硬编码模板（仍保留）

不想/没条件调 LLM 的话，`scripts/strategy_generator.py` 是按指标白名单（SMA/EMA/RSI/MACD/BB）拼模板的生成器，没外部依赖：

```python
from scripts.strategy_generator import StrategyGenerator

g = StrategyGenerator()
code = g.generate_strategy(name="AutoStrategy", indicators=["RSI", "SMA", "MACD"])
g.save_strategy(name="AutoStrategy",
                indicators=["RSI", "SMA", "MACD"],
                output_path="strategies")
```

适合冷启动 / CI 跑测试 / 不想配 API key 的场景，但模板固定，没有"按描述生成"能力。

## 安装

```bash
pip install -r requirements.txt
# 如果用 LLM 功能，至少装其中一个：
pip install openai       # openai / deepseek backend
pip install anthropic    # anthropic backend
```

Freqtrade 本身不是本仓库的运行时依赖 —— 你只需要在 Freqtrade 运行的环境里把生成好的 `.py` 文件放到 `user_data/strategies/` 即可。

## 项目结构

```
freqtrade-strategy-generator/
├── __main__.py                 # CLI：generate / validate / list-backends
├── scripts/
│   ├── llm_generator.py        # v2：LLMClient + LLMStrategyGenerator
│   ├── strategy_validator.py   # v2：AST 静态校验（FT000-FT007）
│   └── strategy_generator.py   # v1：硬编码模板生成器
├── tests/
│   ├── test_llm_generator.py    # 21 个 mock-LLM 测试，不发真请求
│   └── test_strategy_validator.py  # 20 个用刻意 bad code 触发各错误码的测试
├── SKILL.md
├── README.md
├── requirements.txt
└── config/
    └── llm.yaml                # 旧版配置，v2 已不需要
```

## 设计取舍

- **LLM 不内置 fallback 模板**：缺 key 时 `generate` 直接 raise `LLMNotAvailable`，不静默回退到模板假装成功。LLM 生成本身就是 v2 的核心目的，悄悄退化会让人误以为是 LLM 输出。
- **校验是建议性的，不是阻塞性的**：CLI 默认不会因为校验不过就拒绝输出，`--allow-invalid` 可以强行保存（默认是不允许 —— 见 `__main__.py`）。这样你能拿着报错信息回头让 LLM 修，而不是反复重生成。
- **system prompt 强制 INTERFACE_VERSION = 3**：现在 Freqtrade 主线已经是 v3 接口（`populate_entry_trend` 而非旧的 `populate_buy_trend`），生成的策略不会兼容老版本。

## 测试

```bash
pip install pytest
pytest tests/ -v
```

41 个测试全过，全部 mock，不发真 LLM 请求。

## 已知限制

- 校验只看代码"长得对不对"，不跑代码。LLM 生成的指标可能确实存在但语义错误（比如 `ta.RSI` 周期写成 0），需要靠回测发现。
- FT004 把 `dataframe.iloc[-1]` 标记为"嫌疑未来函数"是保守判断 —— 在某些 callback 里这个用法合法，校验会误报。
- 默认 `temperature=0.2` 让生成结果偏稳定但缺乏多样性；如果想拿同一描述生成几个变体，得改源码或加 `--temperature` 参数（待加）。

## 许可

MIT
