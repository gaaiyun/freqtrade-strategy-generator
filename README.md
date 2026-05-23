> **维护状态说明**：本仓库当前是 AI 辅助生成的初始脚手架，未在生产环境持续打磨。代码可作为参考与起点，使用前请自行核对接口、依赖与边界条件。如果你打算接手维护、把它合并到其他项目，或者发现 bug，欢迎开 issue 或 PR。
# Freqtrade Strategy Generator

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Freqtrade](https://img.shields.io/badge/Powered%20by-Freqtrade-green.svg)](https://www.freqtrade.io/)

**使用 LLM 自动生成 Freqtrade 交易策略 - AI 驱动的策略开发**

基于 [Freqtrade](https://github.com/freqtrade/freqtrade) 的 AI 策略生成器，使用大语言模型自动生成、优化和回测交易策略。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd C:\Users\gaaiy\.openclaw\workspace\skills\freqtrade-strategy-gen

# 安装核心依赖
pip install openai anthropic pyyaml jinja2
```

### 2. 配置 API Key

创建 `.env` 文件：

```bash
# LLM API Keys (选择一个)
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx
DASHSCOPE_API_KEY=sk-xxx

# Freqtrade 路径
FREQTRADE_PATH=C:\Users\gaaiy\.openclaw\workspace\projects\freqtrade
```

### 3. 生成策略

```bash
# 使用自然语言描述策略
python scripts/generate.py --prompt "Create a momentum strategy that buys when RSI is below 30 and sells when RSI is above 70"

# 指定 LLM 模型
python scripts/generate.py --prompt "Grid trading strategy" --model gpt-4

# 自动回测生成的策略
python scripts/generate.py --prompt "MACD crossover strategy" --backtest
```

---

## 📖 功能特性

### AI 驱动策略生成
- ✅ **自然语言输入** - 用简单的语言描述策略
- ✅ **自动代码生成** - LLM 生成完整的 Python 策略代码
- ✅ **语法验证** - 自动检查生成的代码
- ✅ **最佳实践** - 遵循 Freqtrade 最佳实践

### 策略优化
- ✅ **参数建议** - AI 推荐最佳参数
- ✅ **风险管理** - 自动添加止损和止盈
- ✅ **回测集成** - 一键回测生成的策略
- ✅ **性能分析** - 详细的回测报告

### 多模型支持
- ✅ **OpenAI** - GPT-4, GPT-3.5
- ✅ **Anthropic** - Claude 3.5 Sonnet
- ✅ **阿里云** - Qwen Plus
- ✅ **本地模型** - Ollama 支持

---

## 📝 使用示例

### 示例 1: 生成动量策略

```bash
python scripts/generate.py --prompt "
Create a momentum strategy with the following rules:
- Buy when RSI(14) < 30 and price is above 20-day MA
- Sell when RSI(14) > 70 or price drops below 20-day MA
- Use 2% stop loss and 5% take profit
"
```

**生成的策略代码**:
```python
class MomentumStrategy(IStrategy):
    INTERFACE_VERSION = 3
    
    # ROI table
    minimal_roi = {
        "0": 0.05,  # 5% take profit
    }
    
    # Stoploss
    stoploss = -0.02  # 2% stop loss
    
    # Timeframe
    timeframe = '5m'
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Moving Average
        dataframe['ma20'] = ta.SMA(dataframe, timeperiod=20)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &
                (dataframe['close'] > dataframe['ma20'])
            ),
            'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) |
                (dataframe['close'] < dataframe['ma20'])
            ),
            'exit_long'] = 1
        
        return dataframe
```

### 示例 2: 生成网格交易策略

```bash
python scripts/generate.py --prompt "Grid trading strategy with 10 levels, 1% spacing"
```

### 示例 3: 批量生成和测试

```bash
# 生成多个策略变体
python scripts/batch_generate.py --base-prompt "RSI strategy" --variants 5

# 回测所有生成的策略
python scripts/batch_backtest.py --strategies-dir generated_strategies/
```

---

## ⚙️ 配置说明

### LLM 配置 (config/llm.yaml)

```yaml
llm:
  provider: openai  # openai, anthropic, dashscope, ollama
  model: gpt-4
  temperature: 0.7
  max_tokens: 2000

generation:
  include_comments: true
  include_docstrings: true
  validate_syntax: true
  auto_format: true

freqtrade:
  user_data_dir: ~/.freqtrade/user_data
  strategies_dir: strategies
  config_file: config.json
```

### Prompt 模板 (templates/strategy_prompt.txt)

```
You are an expert Freqtrade strategy developer.

Generate a complete Freqtrade strategy based on this description:
{user_prompt}

Requirements:
1. Use Freqtrade IStrategy interface (INTERFACE_VERSION = 3)
2. Include proper indicators in populate_indicators()
3. Define entry conditions in populate_entry_trend()
4. Define exit conditions in populate_exit_trend()
5. Set appropriate ROI and stoploss
6. Add comments explaining the logic
7. Follow Freqtrade best practices

Output only the Python code, no explanations.
```

---

## 🎯 高级功能

### 策略优化

```bash
# 生成策略并自动优化参数
python scripts/generate.py --prompt "MACD strategy" --optimize

# 使用 hyperopt 优化
python scripts/optimize.py --strategy GeneratedStrategy --epochs 100
```

### 策略组合

```bash
# 组合多个策略
python scripts/combine.py --strategies strategy1.py strategy2.py --output combined_strategy.py
```

### 策略分析

```bash
# 分析策略性能
python scripts/analyze.py --strategy GeneratedStrategy --timerange 20230101-20240101
```

---

## 📊 回测报告示例

```
=== Strategy Generation Report ===
Prompt: "RSI momentum strategy"
Model: gpt-4
Generated: 2026-03-01 16:50

=== Backtest Results ===
Strategy: RSI_Momentum_v1
Timeframe: 5m
Period: 2023-01-01 to 2024-01-01

Performance:
┌─────────────────────┬──────────┐
│ Metric              │ Value    │
├─────────────────────┼──────────┤
│ Total Return        │ 32.5%    │
│ Sharpe Ratio        │ 1.65     │
│ Max Drawdown        │ -8.2%    │
│ Win Rate            │ 58.3%    │
│ Total Trades        │ 247      │
│ Avg Trade Duration  │ 4.2h     │
└─────────────────────┴──────────┘

Recommendation: ✅ Strategy looks promising
```

---

## 📁 项目结构

```
freqtrade-strategy-gen/
├── SKILL.md              # OpenClaw Skill 描述
├── README.md             # 本文档
├── requirements.txt      # 依赖列表
├── scripts/
│   ├── generate.py       # 策略生成脚本
│   ├── batch_generate.py # 批量生成
│   ├── optimize.py       # 参数优化
│   └── analyze.py        # 策略分析
├── config/
│   └── llm.yaml          # LLM 配置
├── templates/
│   ├── strategy_prompt.txt    # Prompt 模板
│   └── strategy_template.py   # 策略模板
└── references/
    └── .env.example      # 环境变量模板
```

---

## 🔧 故障排除

### 常见问题

**Q: 生成的策略有语法错误**
```
A: 检查 LLM 配置
   - 使用更强大的模型（GPT-4）
   - 调整 temperature 参数
   - 启用语法验证
```

**Q: 回测失败**
```
A: 检查策略代码
   - 确保指标正确计算
   - 检查进出场条件
   - 查看 Freqtrade 日志
```

**Q: API 调用失败**
```
A: 检查 API Key
   - 确认 .env 文件配置正确
   - 检查 API 额度
   - 尝试其他 LLM 提供商
```

---

## 💡 策略 Idea 示例

### 1. 趋势跟踪策略
```
"Create a trend following strategy using EMA crossover (20/50) with ADX filter > 25"
```

### 2. 均值回归策略
```
"Mean reversion strategy: buy when price is 2 standard deviations below Bollinger Bands"
```

### 3. 突破策略
```
"Breakout strategy: enter when price breaks above 20-day high with volume confirmation"
```

### 4. 多指标组合
```
"Combine RSI, MACD, and Stochastic: buy when all three indicators are bullish"
```

---

## 🙏 致谢

- 原项目：[Freqtrade](https://github.com/freqtrade/freqtrade)
- LLM 提供商：OpenAI, Anthropic, 阿里云
- 社区：Freqtrade Discord

---

## 📄 许可证

MIT License

---

## ⚠️ 免责声明

本工具生成的策略仅供教育和研究目的。不构成投资建议。

AI 生成的策略可能包含错误或不适合实际交易。请在充分回测和验证后再使用。

---

_基于 [Freqtrade](https://github.com/freqtrade/freqtrade) 二次开发_
_AI 驱动的策略生成器_
