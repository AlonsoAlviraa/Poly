
import json
import logging
import os
import random
import asyncio
from typing import Dict, List, Tuple
from dotenv import load_dotenv
load_dotenv()
from src.arbitrage.ai_mapper import get_ai_mapper
from src.data.cache_manager import CacheManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIJudge:
    def __init__(self):
        self.ai = get_ai_mapper()
        self.cache_mgr = CacheManager()
        self.mappings_path = os.path.join("src", "data", "mappings.json")

    async def audit_entry(self, alias: str, canonical: str, sport: str) -> int:
        """
        Actúa como un juez deportivo.
        Devuelve un score de 0 a 100.
        """
        if alias.lower() == canonical.lower():
            return 100

        prompt = f"""
        Actúa como un juez experto en datos deportivos. 
        Evalúa si el siguiente ALIAS se refiere indiscutiblemente al mismo EQUIPO/ENTIDAD que el nombre CANÓNICO.
        
        Deporte: {sport}
        Nombre Canónico: "{canonical}"
        Alias a evaluar: "{alias}"
        
        REGLAS DE ORO:
        - 100: Es el mismo equipo (ej: "Man Utd" vs "Manchester United").
        - 80-90: Muy probable, pero podría haber ambigüedad menor.
        - < 50: Diferentes equipos (ej: "Paris FC" vs "PSG") o conceptos distintos.
        - 0: Basura o error fatal.
        
        Responde exclusivamente con un objeto JSON: {{"score": int, "reason": "breve explicación"}}
        """
        
        # Reutilizamos la infraestructura de AI Mapper pero con un prompt custom
        # Para simplificar, usaremos el método check_similarity y adaptaremos o crearemos uno nuevo.
        # Por ahora, simulamos la llamada directa para tener control del prompt del Juez.
        
        try:
            # Usamos el cliente HTTP de ai_mapper.py si es posible
            from src.utils.http_client import get_httpx_client
            
            headers = {
                "Authorization": f"Bearer {self.ai.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "google/gemini-2.0-flash-001",
                "messages": [
                    {"role": "system", "content": "Eres un auditor de calidad de datos deportivos."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": { "type": "json_object" }
            }
            
            with get_httpx_client(timeout=15.0) as client:
                resp = client.post(self.ai.base_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = json.loads(data['choices'][0]['message']['content'])
                return content.get('score', 0)
        except Exception as e:
            logger.error(f"Error juzgando {alias} vs {canonical}: {e}")
            return 50 # Neutral en caso de error

    async def run_audit(self, sample_size: int = 20):
        if not os.path.exists(self.mappings_path):
            logger.error("No se encontró mappings.json")
            return

        with open(self.mappings_path, "r", encoding="utf-8") as f:
            all_mappings = json.load(f)

        flat_list = []
        for sport, categories in all_mappings.items():
            for canonical, aliases in categories.items():
                for alias in aliases:
                    if alias.lower() != canonical.lower():
                        flat_list.append((alias, canonical, sport))

        logger.info(f"🔍 Auditoría iniciada. Total mapeos no triviales: {len(flat_list)}")
        
        if sample_size > 0:
            sample = random.sample(flat_list, min(sample_size, len(flat_list)))
        else:
            sample = flat_list

        results = []
        for alias, canonical, sport in sample:
            score = await self.audit_entry(alias, canonical, sport)
            results.append({
                "alias": alias,
                "canonical": canonical,
                "sport": sport,
                "score": score
            })
            logger.info(f"[{score}] {alias} -> {canonical} ({sport})")
            await asyncio.sleep(1) # Rate limit protection

        # Resumen
        low_quality = [r for r in results if r['score'] < 90]
        logger.info(f"\n--- REPORTE DE CALIDAD ---")
        logger.info(f"Total auditados: {len(results)}")
        logger.info(f"Promedio Score: {sum(r['score'] for r in results)/len(results):.1f}")
        logger.info(f"Potenciales errores detectados: {len(low_quality)}")
        
        for bad in low_quality:
            logger.warning(f"❌ BAJA CALIDAD: '{bad['alias']}' -> '{bad['canonical']}' (Score: {bad['score']})")

if __name__ == "__main__":
    judge = AIJudge()
    asyncio.run(judge.run_audit(sample_size=15))
