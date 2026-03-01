---
name: freqtrade-strategy-gen
description: AI-powered Freqtrade strategy generator using LLM. Generate, optimize and backtest trading strategies from natural language descriptions.
---

# Freqtrade Strategy Generator

## 1. 什么时候用我？

当用户说：
- "生成一个交易策略"
- "创建 Freqtrade 策略"
- "用 AI 写交易策略"
- "Generate trading strategy"
- "自动生成策略代码"
- 任何需要创建 Freqtrade 策略的场景

## 2. 我能做什么？

### AI 驱动策略生成
- **自然语言输入** - 用简单的语言描述策略
- **自动代码生成** - LLM 生成完整的 Python 策略代码
- **语法验证** - 自动检查生成的代码
- **最佳实践** - 遵循 Freqtrade 最佳实践

### 策略优化
- **参数建议** - AI 推荐最佳参数
- **风险管理** - 自动添加止损和止盈
- **回测集成** - 一键回测生成的策略
- **性能分析** - 详细的回测报告

### 多模型支持
- **OpenAI** - GPT-4, GPT-3.5
- **Anthropic** - Claude 3.5 Sonnet
- **阿里云** - Qwen Plus
- **本地模型** - Ollama 支持

## 3. 使用示例

### 基础用法
```bash
# 生成动量策略
python scripts/generate.py --prompt "RSI momentum strategy with 30/70 levels"

# 生成并回测
python scripts/generate.py --prompt "MACD crossover strategy" --backtest

# 批量生成
python scripts/batch_generate.py --base-prompt "Grid trading" --variants 5
```

### Python API
```python
from freqtrade_strategy_gen import StrategyGenerator

# 初始化生成器
generator = StrategyGenerator(model="gpt-4")

# 生成策略
strategy_code = generator.generate(
    prompt="Create a momentum strategy using RSI and MA",
    validate=True,
    optimize=True
)

# 保存策略
generator.save_strategy(strategy_code, "my_strategy.py")

# 回测策略
results = generator.backtest("my_strategy.py")
```

### OpenClaw 调用
```python
# 在 OpenClaw 中自动触发
用户："帮我生成一个 RSI 策略"
→ 自动调用 freqtrade-strategy-gen
→ 生成策略代码
→ 验证语法
→ 返回策略文件
```

## 4. 配置说明

### 环境变量
```bash
# LLM API Keys
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx
DASHSCOPE_API_KEY=sk-xxx

# Freqtrade 路径
FREQTRADE_PATH=/path/to/freqtrade
```

### LLM 配置 (config/llm.yaml)
```yaml
llm:
  provider: openai
  model: gpt-4
  temperature: 0.7
  max_tokens: 2000

generation:
  include_comments: true
  validate_syntax: true
  auto_format: true
```

## 5. 生成的策略示例

### RSI 动量策略
```python
class RSI_Momentum(IStrategy):
    INTERFACE_VERSION = 3
    
    minimal_roi = {"0": 0.05}
    stoploss = -0.02
    timeframe = '5m'
    
    def populate_indicators(self, dataframe, metadata):
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['ma20'] = ta.SMA(dataframe, timeperiod=20)
        return dataframe
    
    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[
            (dataframe['rsi'] < 30) &
            (dataframe['close'] > dataframe['ma20']),
            'enter_long'] = 1
        return dataframe
    
    def populate_exit_trend(self, dataframe, metadata):
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'] = 1
        return dataframe
```

## 6. Prompt 示例

### 趋势跟踪
```
"Create a trend following strategy using EMA crossover (20/50) with ADX filter > 25"
```

### 均值回归
```
"Mean reversion strategy: buy when price is 2 standard deviations below Bollinger Bands"
```

### 突破策略
```
"Breakout strategy: enter when price breaks above 20-day high with volume confirmation"
```

## 7. 依赖项

### Python 包
- Python 3.11+
- openai / anthropic
- pyyaml
- jinja2
- freqtrade

### 安装
```bash
pip install openai anthropic pyyaml jinja2
```

## 8. 注意事项

1. **AI 生成限制**: AI 生成的策略可能包含错误
2. **充分测试**: 必须回测验证后再使用
3. **风险管理**: 始终设置止损和仓位管理
4. **API 成本**: LLM API 调用有成本

## 9. 故障排除

### 常见问题
- **语法错误**: 使用更强大的模型（GPT-4）
- **回测失败**: 检查策略逻辑和指标
- **API 失败**: 检查 API Key 和额度

### 日志位置
- `~/.openclaw/workspace/logs/strategy-gen.log`

---

_基于 [Freqtrade](https://github.com/freqtrade/freqtrade) 二次开发_
_AI 驱动的策略生成器_
