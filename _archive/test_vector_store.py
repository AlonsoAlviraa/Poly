
import sys
import os

sys.path.append(os.getcwd())
from src.arbitrage.vector_matcher import VectorMatcher

print("Initializing VectorMatcher (Numpy Engine)...")
vm = VectorMatcher()
try:
    vm._load_models()
    print("✅ Models Loaded Successfully!")
    
    # Quick index test
    events = [{'id': '123', 'name': 'Real Madrid vs Barcelona'}]
    vm.index_events(events)
    print("✅ Indexing Successful!")
    
    matches = vm.find_matches("Real Madrid v Barca")
    print(f"✅ Match Found: {matches[0] if matches else 'None'}")
    
except Exception as e:
    print(f"❌ Failed: {e}")
