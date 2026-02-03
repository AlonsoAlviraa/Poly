import asyncio
import statistics
from scripts.simulate_paper_session import run_mega_backtest

async def optimize():
    print("[START] Starting Monte Carlo Parameter Optimization...")
    print("Searching for: Maximum Mean PnL over multiple scenarios.")
    print("-" * 50)
    
    # Parameter Grid
    spreads = [0.02, 0.05, 0.08]
    vol_thresholds = [0.003, 0.005, 0.010]
    skew_factors = [0.0001, 0.0005] # Gentle vs Aggressive skew
    
    seeds = [42, 101, 2024] # Corresponds to "Different Dates / Market Conditions"
    
    results = []
    
    total_runs = len(spreads) * len(vol_thresholds) * len(skew_factors) * len(seeds)
    run_count = 0
    
    best_config = None
    best_score = -float('inf')
    
    for s in spreads:
        for v in vol_thresholds:
            for k in skew_factors:
                
                outcomes = []
                for seed in seeds:
                    run_count += 1
                    # print(f"[{run_count}/{total_runs}] Testing Spread={s} Vol={v} Skew={k} Seed={seed} ...", end="\r")
                    
                    try:
                        pnl = await run_mega_backtest(
                            seed=seed,
                            spread=s,
                            vol_threshold=v,
                            skew_factor=k,
                            steps=300 # Faster than 500 for optimization
                        )
                        outcomes.append(pnl)
                    except Exception as e:
                        print(f"Error: {e}")
                        outcomes.append(-1000.0)
                
                # Evaluation metric: Mean PnL (Risk penalized implicitly by seeds coverage?)
                # Let's use lower_bound (Mean - StdDev) to penalize volatility of results
                mean_pnl = statistics.mean(outcomes)
                std_pnl = statistics.stdev(outcomes) if len(outcomes) > 1 else 0.0
                score = mean_pnl - (0.5 * std_pnl) # Conservative scoring
                
                # print(f"CFG: Spread={s} Vol={v} Skew={k} | Mean=${mean_pnl:.2f} Score={score:.2f}")
                
                results.append({
                    "params": (s, v, k),
                    "mean": mean_pnl,
                    "score": score
                })
                
                if score > best_score:
                    best_score = score
                    best_config = (s, v, k)
                    print(f"[*] NEW BEST: Spread={s} Vol={v} Skew={k} | Mean Based PnL: ${mean_pnl:.2f}")

    print("-" * 50)
    print(f"[WIN] WINNER CONFIGURATION:")
    print(f"Spread: {best_config[0]}")
    print(f"Volatility Threshold: {best_config[1]}")
    print(f"Inventory Skew Factor: {best_config[2]}")
    print(f"Score: {best_score:.2f}")

if __name__ == "__main__":
    asyncio.run(optimize())
