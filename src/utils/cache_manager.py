import sqlite3
import hashlib
import time
import os
from typing import Optional

class CacheManager:
    """
    Manages deduplication of signals using SQLite.
    Implements TTL (Time To Live) to expire old signals.
    """
    
    def __init__(self, db_path="signals.db", ttl_seconds=3600):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _init_db(self):
        """Initialize SQLite table"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS sent_signals (
                    hash TEXT PRIMARY KEY,
                    timestamp REAL,
                    profit_snapshot REAL
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Cache DB Init Error: {e}")

    def _generate_hash(self, event_id: str, strategy_name: str, poly_market_id: str, sx_market_id: str) -> str:
        """Generate MD5 hash for the signal"""
        raw_string = f"{event_id}-{strategy_name}-{poly_market_id}-{sx_market_id}"
        return hashlib.md5(raw_string.encode()).hexdigest()

    def should_send_alert(self, event_id: str, strategy_name: str, poly_market_id: str, sx_market_id: str, current_profit: float) -> bool:
        """
        Check if alert should be sent.
        Returns True if:
        1. Signal is new (not in cache).
        2. Signal is old (expired TTL).
        3. Signal profitability increased significantly (> 5% difference).
        """
        signal_hash = self._generate_hash(event_id, strategy_name, poly_market_id, sx_market_id)
        now = time.time()
        
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute("SELECT timestamp, profit_snapshot FROM sent_signals WHERE hash=?", (signal_hash,))
            result = c.fetchone()
            
            should_send = False
            
            if result:
                timestamp, last_profit = result
                
                # Check TTL
                if now - timestamp > self.ttl_seconds:
                    should_send = True # Expired, treat as new
                
                # Check Profit Increase (e.g. was 3%, now 8% -> update)
                # User requirement: "si la rentabilidad cambia significativamente (ej. sube un 5% más)"
                elif current_profit >= (last_profit + 5.0):
                    should_send = True
            else:
                should_send = True # New signal
            
            if should_send:
                # Update/Insert
                c.execute('''
                    INSERT OR REPLACE INTO sent_signals (hash, timestamp, profit_snapshot)
                    VALUES (?, ?, ?)
                ''', (signal_hash, now, current_profit))
                conn.commit()
                
            conn.close()
            return should_send
            
        except Exception as e:
            print(f"Cache Error: {e}")
            return True # Fail open (send alert) if DB fails

    def cleanup(self):
        """Clean old entries"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            limit = time.time() - self.ttl_seconds
            c.execute("DELETE FROM sent_signals WHERE timestamp < ?", (limit,))
            conn.commit()
            conn.close()
        except:
            pass
