---
name: freqtrade-strategy-generator
description: 把一句话策略描述变成可直接放进 Freqtrade 跑回测的 IStrategy 子类代码（LLM 生成 + AST 静态校验）。
---

# freqtrade-strategy-generator

## 什么时候用

- "帮我生成一个 RSI / MACD / 网格 / 趋势跟踪策略"
- "把这段策略思路写成 Freqtrade IStrategy 代码"
- "校验一下这个 IStrategy 文件有没有问题"

## 入口

```bash
# 生成
python __main__.py generate RSIMomentum \
    --desc "RSI < 30 入场 + EMA20 > EMA50 趋势确认 + 5% 止损" \
    --timeframe 5m --stoploss 0.05 -o strategies/RSIMomentum.py

# 校验已有文件
python __main__.py validate strategies/RSIMomentum.py --json

# 查看可用 LLM backend
python __main__.py list-backends
```

库调用入口：

- `scripts/llm_generator.py::LLMStrategyGenerator.generate()` — LLM 生成
- `scripts/strategy_validator.py::validate()` — AST 静态校验，返回 `ValidationReport`
- `scripts/strategy_generator.py::StrategyGenerator` — v1 硬编码模板（不调 LLM）

## 校验错误码

| 码 | 含义 |
|---|---|
| FT000 | Python 语法错 |
| FT001 | 缺 IStrategy 子类 |
| FT002 | 缺 populate_indicators / populate_entry_trend / populate_exit_trend 之一 |
| FT003 | 缺 stoploss（error）或 timeframe / minimal_roi（warn） |
| FT004 | 嫌疑未来函数（直接读 dataframe.iloc[-1]） |
| FT005 | 误用聚宽 API（get_price 等） |
| FT006 | stoploss 是正数 |
| FT007 | 缺 freqtrade import |
| FT008 | minimal_roi 缺 "0" 键（freqtrade 会崩） |
| FT009 | minimal_roi 键写成整数而非字符串 |
| FT010 | 用了已废弃的 v2 接口 populate_buy_trend / populate_sell_trend |

## 依赖

- 必需：Python 3.11+
- v2 LLM 生成：`openai>=1.0.0` 或 `anthropic>=0.18.0`
- 环境变量：`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` 任一

## 注意事项

- 校验只看代码长得对不对，不跑代码 —— 指标语义错（如 RSI 周期 0）只能靠回测发现。
- LLM 生成的策略需自行回测，不构成投资建议。
