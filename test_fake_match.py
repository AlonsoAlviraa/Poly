import asyncio
from src.core.arbitrage_detector import ArbitrageDetector

async def test_fake_match():
    detector = ArbitrageDetector()
    
    # Fake Poly event
    poly_event = {
        "title": "Real Madrid vs Barcelona",
        "startDate": 1700000000,
        "markets": [{
            "clobTokenIds": ["1", "2"],
            "outcomes": ["Yes", "No"]
        }]
    }
    
    # Fake SX event
    sx_event = {
        "label": "Real Madrid vs Barcelona",
        "outcomeOneName": "Real Madrid",
        "outcomeTwoName": "Barcelona",
        "marketHash": "0x123",
        "sportLabel": "Soccer"
    }
    
    matches = detector.match_events([poly_event], [sx_event])
    print(f"Match found: {len(matches)}")
    if matches:
        print(f"Matched Titles: {matches[0][0]['title']} <-> {matches[0][1]['label']}")

if __name__ == "__main__":
    asyncio.run(test_fake_match())
