#!/usr/bin/env python3
"""
Analyzer for paper trading simulation results.
Reads simulation_results.csv and provides detailed analytics.
"""

import pandas as pd
import os
from datetime import datetime

def analyze_simulation(csv_file="simulation_results.csv"):
    """Analyze paper trading results"""
    
    if not os.path.exists(csv_file):
        print(f"❌ File {csv_file} not found. Run bot in PAPER_TRADING mode first.")
        return
    
    # Load data
    df = pd.read_csv(csv_file)
    
    if len(df) == 0:
        print(f"❌ No trades in {csv_file}. Let the bot run longer.")
        return
    
    # Convert timestamp
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    # Calculate metrics
    total_trades = len(df)
    winning_trades = len(df[df['Actual_Profit_After_Costs'].astype(float) > 0])
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    initial_balance = float(df.iloc[0]['Virtual_Balance']) - float(df.iloc[0]['Actual_Profit_After_Costs'])
    final_balance = float(df.iloc[-1]['Virtual_Balance'])
    total_return = final_balance - initial_balance
    roi = (total_return / initial_balance) * 100
    
    avg_profit = df['Actual_Profit_After_Costs'].astype(float).mean()
    max_profit = df['Actual_Profit_After_Costs'].astype(float).max()
    max_loss = df['Actual_Profit_After_Costs'].astype(float).min()
    
    # Time analysis
    duration = (df['Timestamp'].iloc[-1] - df['Timestamp'].iloc[0]).total_seconds() / 3600
    trades_per_hour = total_trades / duration if duration > 0 else 0
    
    # Print report
    print(f"\n{'='*70}")
    print(f"📊 PAPER TRADING ANALYSIS")
    print(f"{'='*70}\n")
    
    print(f"📅 Simulation Period")
    print(f"   Start:    {df['Timestamp'].iloc[0]}")
    print(f"   End:      {df['Timestamp'].iloc[-1]}")
    print(f"   Duration: {duration:.1f} hours\n")
    
    print(f"💼 Portfolio Performance")
    print(f"   Initial Capital:  ${initial_balance:.2f}")
    print(f"   Final Balance:    ${final_balance:.2f}")
    print(f"   Total Return:     ${total_return:.2f}")
    print(f"   ROI:              {roi:.2f}%\n")
    
    print(f"📈 Trade Statistics")
    print(f"   Total Trades:     {total_trades}")
    print(f"   Winning Trades:   {winning_trades} ({win_rate:.1f}%)")
    print(f"   Losing Trades:    {losing_trades}")
    print(f"   Avg Profit/Trade: ${avg_profit:.2f}")
    print(f"   Best Trade:       ${max_profit:.2f}")
    print(f"   Worst Trade:      ${max_loss:.2f}\n")
    
    print(f"⚡ Frequency")
    print(f"   Trades/Hour:      {trades_per_hour:.2f}")
    print(f"   Trades/Day (est): {trades_per_hour * 24:.1f}\n")
    
    # Projections
    if duration > 0:
        daily_return = (total_return / duration) * 24
        monthly_return = daily_return * 30
        monthly_roi = (monthly_return / initial_balance) * 100
        
        print(f"🎯 Projections (if this pace continues)")
        print(f"   Daily Return:     ${daily_return:.2f}")
        print(f"   Monthly Return:   ${monthly_return:.2f}")
        print(f"   Monthly ROI:      {monthly_roi:.1f}%\n")
    
    # Strategy breakdown
    print(f"📋 Strategy Breakdown")
    strategy_stats = df.groupby('Strategy')['Actual_Profit_After_Costs'].agg(['count', 'sum', 'mean'])
    for strategy, row in strategy_stats.iterrows():
        print(f"   {strategy[:40]}")
        print(f"      Trades: {int(row['count'])}, Total: ${row['sum']:.2f}, Avg: ${row['mean']:.2f}")
    
    print(f"\n{'='*70}\n")
    
    # Red flags
    if win_rate < 50:
        print(f"⚠️  WARNING: Win rate < 50%. Review opportunity detection logic.")
    if roi < 0:
        print(f"⚠️  WARNING: Negative ROI. Strategy not profitable in simulation.")
    if trades_per_hour < 0.1:
        print(f"⚠️  WARNING: Very low trade frequency. Lower MIN_PROFIT_PERCENT?")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if roi > 50:
        print(f"   ✅ Strong performance. Consider going LIVE with small position sizes.")
    elif roi > 20:
        print(f"   ⚠️  Moderate performance. Run longer simulation (48-72h) before LIVE.")
    else:
        print(f"   ❌ Weak performance. Review thresholds and matching logic.")
    
    print()

if __name__ == "__main__":
    import sys
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "simulation_results.csv"
    analyze_simulation(csv_file)
