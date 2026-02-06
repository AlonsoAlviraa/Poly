
import asyncio
import sys
import os

# Ensure src is in path
sys.path.append(os.getcwd())

from src.arbitrage.cross_platform_mapper import perform_real_scan

if __name__ == "__main__":
    print("🚀 Launching Real Scanner (Paper Mode)...")
    print("   - Duration: 2 Hours")
    print("   - Mode: Live Data, Mock Execution")
    print("   - AI: Auto-fallback if OOM")
    
    try:
        asyncio.run(perform_real_scan(120))
    except KeyboardInterrupt:
        print("\n🛑 Scanner stopped by user.")
    except Exception as e:
        print(f"\n❌ Scanner crashed: {e}")
        input("Press Enter to exit...")
