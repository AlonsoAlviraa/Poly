from config import MIN_EV
from src.utils.normalization import decimal_to_probability

class ArbitrageAnalyzer:
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.rejection_count = 0
        self.max_verbose_logs = 10  # Only log first 10 rejections

    def calculate_vwap(self, asks, target_size=10):
        """
        Calculates Volume Weighted Average Price for a target size.
        Default: $10 USDC to protect against fake liquidity.
        """
        accumulated_cost = 0
        accumulated_size = 0
        
        for ask in asks:
            price = float(ask.get("price", 0))
            size = float(ask.get("size", 0))
            
            needed = target_size - accumulated_size
            
            if size >= needed:
                accumulated_cost += needed * price
                accumulated_size += needed
                break
            else:
                accumulated_cost += size * price
                accumulated_size += size
        
        if accumulated_size < target_size:
            return None # Not enough liquidity to fill order
            
        return accumulated_cost / accumulated_size

    def calculate_arbitrage(self, bookie_event, poly_event, poly_asks=None):
        """
        Calculates arbitrage with VWAP and Liquidity checks.
        NOW WITH VERBOSE LOGGING for debugging.
        """
        b_name = f"{bookie_event.get('home_team')} vs {bookie_event.get('away_team')}"
        p_title = poly_event.get("title", "Unknown")
        
        # If no poly_asks provided, try to get from poly_event markets
        if not poly_asks:
            # Try to extract from poly_event structure
            markets = poly_event.get("markets", [])
            if not markets:
                if self.verbose and self.rejection_count < self.max_verbose_logs:
                    print(f"[REJECT #{self.rejection_count + 1}] {b_name} <-> {p_title}")
                    print(f"  REASON: No Polymarket markets found in event")
                    self.rejection_count += 1
                return None
            
            # For now, we don't have orderbook depth integrated in qa_sweep
            # This is expected - we need to fetch orderbook separately
            if self.verbose and self.rejection_count < self.max_verbose_logs:
                print(f"[REJECT #{self.rejection_count + 1}] {b_name} <-> {p_title}")
                print(f"  REASON: Orderbook depth not fetched (poly_asks=None)")
                print(f"  NOTE: This is expected - orderbook fetching not integrated yet")
                self.rejection_count += 1
            return None

        # 1. Liquidity Check (Top of Book > $100)
        best_ask = poly_asks[0]
        top_liquidity = float(best_ask.get("price", 0)) * float(best_ask.get("size", 0))
        
        if top_liquidity < 100:
            if self.verbose and self.rejection_count < self.max_verbose_logs:
                print(f"[REJECT #{self.rejection_count + 1}] {b_name} <-> {p_title}")
                print(f"  REASON: Low liquidity")
                print(f"  Top Liquidity: ${top_liquidity:.2f} (Need: $100)")
                self.rejection_count += 1
            return None

        # 2. VWAP Calculation ($10 bet to protect against fake liquidity)
        poly_vwap = self.calculate_vwap(poly_asks, target_size=10)
        if not poly_vwap:
            if self.verbose and self.rejection_count < self.max_verbose_logs:
                print(f"[REJECT #{self.rejection_count + 1}] {b_name} <-> {p_title}")
                print(f"  REASON: Insufficient orderbook depth for $10 bet")
                self.rejection_count += 1
            return None

        # 3. Bookie Probability
        # Find best odds for Home Win
        best_bookie_price = 0
        for bookmaker in bookie_event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") == "h2h":
                    for outcome in market.get("outcomes", []):
                        if outcome.get("name") == bookie_event.get("home_team"):
                            if outcome.get("price") > best_bookie_price:
                                best_bookie_price = outcome.get("price")
        
        if best_bookie_price == 0:
            if self.verbose and self.rejection_count < self.max_verbose_logs:
                print(f"[REJECT #{self.rejection_count + 1}] {b_name} <-> {p_title}")
                print(f"  REASON: No H2H odds found for home team")
                self.rejection_count += 1
            return None

        p_bookie = decimal_to_probability(best_bookie_price)
        p_poly = poly_vwap  # VWAP is already a price (0-1), not odds
        
        # Calculate EV (Expected Value)
        # If Poly price < Bookie implied probability -> Poly underpriced -> Buy Poly
        delta = p_bookie - p_poly
        ev_percent = (delta / p_poly) * 100 if p_poly > 0 else 0
        
        if self.verbose and self.rejection_count < self.max_verbose_logs:
            print(f"🔍 [MATH CHECK] {b_name} <-> {p_title}")
            print(f"  Poly Price: {poly_vwap:.4f} | Bookie Implied Prob: {p_bookie:.4f} (from odds {best_bookie_price:.2f})")
            print(f"  Delta: {delta:.4f} | EV: {ev_percent:+.2f}% | Liquidity: ${top_liquidity:.2f}")
            
            if ev_percent > 2.5:
                print(f"  ✅ ACTIONABLE ARB!")
            else:
                print(f"  ❌ EV too low (need >2.5%)")
                self.rejection_count += 1
        
        # Lowered threshold from 2.5 to 1.5 for more opportunities
        if ev_percent > 1.5 and top_liquidity > 50:
            return {
                "event": b_name,
                "bet_team": bookie_event.get("home_team"),
                "bookie_odds": best_bookie_price,
                "bookie_prob": round(p_bookie, 4),
                "poly_price": round(poly_vwap, 4), # VWAP
                "ev_percent": round(ev_percent, 2),
                "poly_liquidity": round(top_liquidity, 2),
                "poly_link": f"https://polymarket.com/event/{poly_event.get('slug', '')}"
            }
        
        return None
