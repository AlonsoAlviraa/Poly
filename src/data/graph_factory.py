import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class GraphFactory:
    """
    Automates dependency generation using LLM (Context 2026).
    Parses market descriptions -> Constraints.
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client # e.g., DeepSeek-R1 API wrapper

    def generate_constraints(self, markets: List[Dict]) -> List[Dict]:
        """
        Input: List of market dicts [{'question': 'Will Trump win?', 'id': '0x1'}, ...]
        Output: List of constraint relations for Polytope.
        """
        # 1. Prompt Engineering (Concept)
        descriptions = [m['question'] for m in markets]
        prompt = f"""
        Analyze the following prediction markets and identify logical correlations.
        Markets: {json.dumps(descriptions)}
        
        Output JSON format:
        [
           {{ "type": "subset", "parent": "id_A", "child": "id_B" }},
           {{ "type": "mutually_exclusive", "group": ["id_A", "id_B"] }}
        ]
        """
        
        logger.info("🤖 Sending descriptions to LLM for graph inference...")
        
        # 2. Mock Response (Since we don't have real LLM connected yet)
        # Simulating: Market A "GOP Win" implies Market B "Trump Win"? No, Trump implies GOP.
        # Market A: "Will a Republican win 2024?"
        # Market B: "Will Trump win 2024?"
        # Logic: Trump -> Republican. B <= A.
        
        # In this mock, we assume the user provides a formatted list for now or we return strict structure.
        inferred_relations = self._mock_llm_inference(descriptions)
        
        # 3. Compiler: Relations -> Polytope Constraints (Ax <= b)
        constraints = []
        for rel in inferred_relations:
            if rel['type'] == 'implication':
                # A implies B => A <= B => A - B <= 0
                # Index mapping needed
                # constraints.append(...)
                pass
                
        return inferred_relations

    def _mock_llm_inference(self, descriptions: List[str]) -> List[Dict]:
        return [
            {"type": "implication", "source_idx": 1, "target_idx": 0, "reason": "Candidate implies Party victory"}
        ]

    def get_live_theta(self, executor, market_ids: List[str]) -> tuple:
        """
        Fetches live orderbooks for given market_ids and constructs the cost vector theta.
        Returns: (theta_array, min_timestamp)
        """
        import numpy as np
        import time
        
        prices = []
        timestamps = []
        
        for mid in market_ids:
            try:
                # 1. Fetch Book
                book = None
                try:
                    book = executor.get_order_book(mid)
                except Exception as e:
                    # Fallback: Try Hex logic if ID is decimal string
                    if isinstance(mid, str) and mid.isdigit():
                        try:
                            hex_id = hex(int(mid))
                            book = executor.get_order_book(hex_id)
                        except: 
                            pass
                    if book is None:
                        logger.warning(f"⚠️ Could not fetch book for {mid}: {e}")
                        prices.append(0.0)
                        continue

                # 2. Extract Bids/Asks (Handle Object or Dict)
                bids = []
                asks = []
                
                if hasattr(book, 'bids'):
                    # OrderBookSummary object
                    bids = book.bids if book.bids else []
                    asks = book.asks if book.asks else []
                elif isinstance(book, dict):
                    bids = book.get('bids', [])
                    asks = book.get('asks', [])
                else:
                    logger.warning(f"⚠️ Unknown book type for {mid}: {type(book)}")
                    prices.append(0.0)
                    continue
                
                # 3. Validate Depth (Ghost Liquidity Filter)
                if not bids or not asks:
                    logger.warning(f"⚠️ Empty Book for {mid} (Bids: {len(bids)}, Asks: {len(asks)})")
                    prices.append(0.0)
                    continue
                
                # 4. Extract Best Bid/Ask (Handle Object or Dict entries)
                try:
                    # Check if entries are dicts or objects
                    first_bid = bids[0]
                    first_ask = asks[0]
                    
                    if hasattr(first_bid, 'price'):
                        best_bid = float(first_bid.price)
                        best_ask = float(first_ask.price)
                    elif isinstance(first_bid, dict):
                        best_bid = float(first_bid.get('price', first_bid.get('p', 0)))
                        best_ask = float(first_ask.get('price', first_ask.get('p', 0)))
                    elif isinstance(first_bid, (list, tuple)):
                        # [price, size] format
                        best_bid = float(first_bid[0])
                        best_ask = float(first_ask[0])
                    else:
                        best_bid = float(first_bid)
                        best_ask = float(first_ask)
                except (IndexError, KeyError, TypeError, ValueError) as e:
                    logger.error(f"❌ Price extraction failed for {mid}: {e}")
                    prices.append(0.0)
                    continue
                
                # 5. Calculate Mid Price
                if best_bid <= 0 or best_ask <= 0:
                    logger.warning(f"⚠️ Invalid price for {mid}: Bid={best_bid}, Ask={best_ask}")
                    prices.append(0.0)
                    continue
                    
                mid_price = (best_bid + best_ask) / 2.0
                prices.append(mid_price)
                timestamps.append(time.time())
                
            except Exception as e:
                logger.error(f"❌ Critical error fetching price for {mid}: {e}")
                prices.append(0.0)
        
        return np.array(prices), min(timestamps) if timestamps else 0.0
