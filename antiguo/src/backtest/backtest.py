import pandas as pd
import os
from src.utils.normalization import decimal_to_probability

class Backtester:
    def __init__(self, csv_path, initial_capital=1000):
        self.csv_path = csv_path
        self.capital = initial_capital
        self.history = []
        self.min_ev = 0.05 # 5%

    def load_data(self):
        if not os.path.exists(self.csv_path):
            print(f"File not found: {self.csv_path}")
            return pd.DataFrame()
        return pd.read_csv(self.csv_path)

    def simulate_polymarket_price(self, true_prob, inefficiency=0.1):
        """
        Simulates a Polymarket price based on true probability (Bookie) 
        plus some market inefficiency/noise.
        :param true_prob: The 'true' probability from sharp bookies.
        :param inefficiency: How much 'dumb money' skews the price.
        """
        # Simple simulation: Polymarket price is skewed towards 0.50
        # If true_prob is 0.60, Poly might be 0.55 (undervaluing the favorite)
        skew = (0.5 - true_prob) * inefficiency
        return true_prob + skew

    def run(self):
        df = self.load_data()
        if df.empty:
            return

        print(f"Starting backtest with ${self.capital}...")
        
        # Assuming Football-Data.co.uk format
        # Columns: Date, HomeTeam, AwayTeam, FTR (H, D, A), B365H, B365D, B365A
        
        required_cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTR', 'B365H', 'B365D', 'B365A']
        if not all(col in df.columns for col in required_cols):
            print("CSV missing required columns.")
            return

        for index, row in df.iterrows():
            # 1. Get Bookie Probability (Home Win)
            odds_home = row['B365H']
            prob_home = decimal_to_probability(odds_home)
            
            # 2. Get/Simulate Polymarket Price
            # In a real backtest, we would look up historical Poly price here.
            # For now, we simulate it to test the logic.
            poly_price = self.simulate_polymarket_price(prob_home)
            
            # 3. Calculate EV
            delta = prob_home - poly_price
            
            if delta > self.min_ev:
                # Place Bet
                bet_size = 50 # Fixed bet size for now
                if self.capital < bet_size:
                    break
                
                self.capital -= bet_size
                
                # Check Result
                result = row['FTR'] # 'H', 'D', 'A'
                won = (result == 'H')
                
                payout = 0
                if won:
                    payout = bet_size / poly_price # If we bought "Yes" shares at price
                    # Wait, Polymarket payout is $1 per share.
                    # Shares = bet_size / poly_price
                    # Payout = Shares * $1 = bet_size / poly_price
                    # Profit = Payout - bet_size
                
                self.capital += payout
                
                self.history.append({
                    "Date": row['Date'],
                    "Match": f"{row['HomeTeam']} vs {row['AwayTeam']}",
                    "Type": "Home Win",
                    "BookieProb": round(prob_home, 3),
                    "PolyPrice": round(poly_price, 3),
                    "Delta": round(delta, 3),
                    "Result": "Win" if won else "Loss",
                    "PnL": round(payout - bet_size, 2),
                    "Capital": round(self.capital, 2)
                })

        print(f"Backtest complete. Final Capital: ${self.capital:.2f}")
        print(f"Total Trades: {len(self.history)}")
        
        # Save results
        pd.DataFrame(self.history).to_csv("backtest_results.csv", index=False)

if __name__ == "__main__":
    # Example usage
    # Create a dummy CSV for testing
    data = {
        'Date': ['01/01/2023', '02/01/2023'],
        'HomeTeam': ['Team A', 'Team C'],
        'AwayTeam': ['Team B', 'Team D'],
        'FTR': ['H', 'A'],
        'B365H': [1.5, 2.0],
        'B365D': [4.0, 3.5],
        'B365A': [6.0, 3.8]
    }
    df = pd.DataFrame(data)
    df.to_csv("dummy_data.csv", index=False)
    
    tester = Backtester("dummy_data.csv")
    tester.run()
