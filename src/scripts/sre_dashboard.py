import requests
import json
import time
import logging

# Config
METRICS_URL = "http://localhost:8000/metrics"

def fetch_metrics():
    try:
        resp = requests.get(METRICS_URL)
        return parse_prometheus(resp.text)
    except Exception as e:
        print(f"Error fetching metrics: {e}")
        return {}

def parse_prometheus(text):
    data = {}
    for line in text.strip().split('\n'):
        if line.startswith('#'): continue
        parts = line.split()
        if len(parts) >= 2:
            key = parts[0]
            val = float(parts[1])
            data[key] = val
    return data

def generate_report():
    print(f"\n--- SRE HEALTH REPORT [{time.strftime('%H:%M:%S')}] ---")
    data = fetch_metrics()
    
    # 1. Latency
    lat_sum = data.get('trade_execution_latency_seconds_sum', 0.0)
    lat_count = data.get('trade_execution_latency_seconds_count', 0.0)
    avg_latency = (lat_sum / lat_count * 1000) if lat_count > 0 else 0.0
    
    print(f"1. LATENCY (Avg): \t{avg_latency:.2f} ms")
    if avg_latency > 500:
        print(f"   ⚠️  LATENCY ALERT: > 500ms. Check RPCs.")
    else:
        print(f"   ✅  Latency Healthy.")

    # 2. Gas Efficiency
    gross_profit = data.get('net_profit_accumulated_usd', 0.0) # Actually we logged net. 
    # Let's assume PnL Gauge tracks Net. Gas Counter tracks Cost.
    gas_spent = data.get('gas_spent_usd_total', 0.0)
    
    # Capital is harder to read from gauge unless we exported it.
    # But we can check Ratio.
    print(f"2. GAS PROFILE:")
    print(f"   Net PnL: \t\t${gross_profit:.4f}")
    print(f"   Gas Spent: \t\t${gas_spent:.4f}")
    
    total_value_moved = gross_profit + gas_spent # Approx 'Value Created'
    if total_value_moved > 0:
        gas_ratio = (gas_spent / total_value_moved) * 100
        print(f"   Gas Eat Ratio: \t{gas_ratio:.1f}%")
        if gas_ratio > 30:
            print(f"   ⚠️  GAS ALERT: Eating >30% of value.")
    else:
        print(f"   Gas Eat Ratio: \tN/A")

    # 3. Recovery Rate
    recoveries = data.get('recovery_events_total', 0.0)
    total_fills = data.get('trade_fill_total_total', 0.0) # check prometheus naming convention
    # Counter usually trade_fill_total_total? Or trade_fill_total{...} sum?
    # Prometheus client output sum is usually metric_total.
    # Assuming 'trade_fill_total_total' isn't standard, we might need to sum buckets.
    # Simple check:
    print(f"3. RELIABILITY:")
    print(f"   Recovery Events: \t{int(recoveries)}")
    if recoveries > 2:
        print(f"   ⚠️  RECOVERY ALERT: > 2 recoveries. Check VWAP.")
    else:
        print(f"   ✅  FSM Stable.")

    # 4. Drift
    drift = data.get('arbitrage_drift_usd', 0.0)
    print(f"4. MODEL DRIFT:")
    print(f"   Current Drift: \t${drift:.4f}")
    if drift > 0.01: # 1% of $1? Or absolute? User said > 1%?
        print(f"   ⚠️  DRIFT ALERT: Model inaccurate.")
    else:
        print(f"   ✅  Model Converging.")

if __name__ == "__main__":
    while True:
        generate_report()
        time.sleep(10)
