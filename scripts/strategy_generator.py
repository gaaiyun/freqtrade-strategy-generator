#!/usr/bin/env python3
"""
Freqtrade Strategy Generator
"""

import pandas as pd
from typing import Dict, List


class StrategyGenerator:
    """Generate trading strategies for Freqtrade"""
    
    def __init__(self):
        self.indicators = ['SMA', 'EMA', 'RSI', 'MACD', 'BB']
        self.timeframes = ['5m', '15m', '1h', '4h', '1d']
    
    def generate_strategy(self, name: str, indicators: List[str]) -> str:
        """Generate strategy code"""
        code = f'''
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class {name}(IStrategy):
    """
    Auto-generated strategy
    """
    
    # Strategy parameters
    minimal_roi = {{
        "0": 0.10,
        "30": 0.05,
        "60": 0.02,
        "120": 0.01
    }}
    
    stoploss = -0.05
    timeframe = '5m'
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Add indicators"""
'''
        
        for indicator in indicators:
            if indicator == 'SMA':
                code += '''
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
'''
            elif indicator == 'RSI':
                code += '''
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
'''
            elif indicator == 'MACD':
                code += '''
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
'''
        
        code += '''
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Entry signals"""
        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &
                (dataframe['sma_20'] > dataframe['sma_50'])
            ),
            'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Exit signals"""
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) |
                (dataframe['sma_20'] < dataframe['sma_50'])
            ),
            'exit_long'] = 1
        
        return dataframe
'''
        
        return code
    
    def save_strategy(self, name: str, indicators: List[str], output_path: str):
        """Save strategy to file"""
        code = self.generate_strategy(name, indicators)
        
        with open(f"{output_path}/{name}.py", 'w', encoding='utf-8') as f:
            f.write(code)
        
        return f"{output_path}/{name}.py"


def main():
    generator = StrategyGenerator()
    
    # Generate strategy
    strategy_file = generator.save_strategy(
        name='AutoStrategy',
        indicators=['SMA', 'RSI', 'MACD'],
        output_path='strategies'
    )
    
    print(f"Strategy generated: {strategy_file}")


if __name__ == '__main__':
    main()
