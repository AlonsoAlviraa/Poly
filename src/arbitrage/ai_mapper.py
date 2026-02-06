
import logging
import json
import os
from typing import Dict, Tuple, Optional
from src.utils.http_client import get_httpx_client

logger = logging.getLogger(__name__)

class AIMapper:
    """
    LLM-powered Entity Matcher.
    Uses an external LLM to verify if two event/team names are the same entity.
    """
    
    def __init__(self, api_key: str = None):
        if not api_key:
            api_key = os.getenv("API_LLM")
        self.api_key = api_key
        # OpenRouter/LiteLLM style base (common for sk-or... keys)
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.enabled = bool(self.api_key)
        
    async def check_similarity(self, 
                               poly_name: str, 
                               exch_name: str, 
                               sport: str) -> Tuple[bool, float]:
        """
        Ask the LLM if two names refer to the same sports entity.
        Returns (is_match, confidence).
        """
        if not self.enabled:
            return False, 0.0
            
        prompt = f"""
Are these two names referring to the SAME '{sport}' entity (team or player)?
Polymarket Name: "{poly_name}"
Exchange Name: "{exch_name}"

CRITICAL RULES:
1. Match ONLY if the primary entities are the same. 
2. BEWARE of city rivals (e.g., Paris FC vs Paris St-G are NOT the same).
3. BEWARE of "Both Teams to Score", "Over/Under" or "Handicap" questions being mixed with "Winner" markets. If one name is a "Both Teams to Score" question and the other is just a team name/event, it is NOT a match for trading purposes.
4. "Real Madrid" matches "Madrid", but "Real Madrid B" does NOT match "Real Madrid".

Return ONLY a JSON object: {{"match": bool, "confidence": float, "canonical": "standard name"}}
Confidence should be between 0.0 and 1.0.
"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/AlonsoAlviraa/Poly", # Optional for OpenRouter
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "google/gemini-2.0-flash-001", # High speed, low cost
            "messages": [
                {"role": "system", "content": "You are a professional sports data auditor. Match entities across platforms. Be strict but recognize common abbreviations and city/franchise differences."},
                {"role": "user", "content": prompt}
            ],
            "response_format": { "type": "json_object" }
        }
        
        try:
            with get_httpx_client(timeout=10.0) as client:
                resp = client.post(self.base_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                
                content = data['choices'][0]['message']['content']
                result = json.loads(content)
                
                # Robustness: Handle if LLM returns a list [ { "match": ... } ]
                if isinstance(result, list):
                    if len(result) > 0 and isinstance(result[0], dict):
                        result = result[0]
                    else:
                        result = {}

                is_match = result.get('match', False)
                confidence = result.get('confidence', 0.0)
                
                if is_match:
                    logger.info(f"🤖 [AI Mapper] Match Predicted: '{poly_name}' == '{exch_name}' (Conf: {confidence})")
                
                return is_match, confidence
                
        except Exception as e:
            logger.error(f"AI Mapper Error: {e}")
            return False, 0.0

_ai_mapper = None

def get_ai_mapper():
    global _ai_mapper
    if _ai_mapper is None:
        _ai_mapper = AIMapper()
    return _ai_mapper
