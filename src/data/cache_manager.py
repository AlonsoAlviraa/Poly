
import json
import os
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from src.arbitrage.models import MarketMapping

logger = logging.getLogger("CacheManager")

class CacheManager:
    """
    Abstrae el almacenamiento de mapeos y entidades.
    Implementa Fast-Path en RAM para acceso O(1) y persistencia atómica.
    """
    def __init__(self, 
                 mapping_path: str = "mapping_cache/active_mappings.json",
                 entity_path: str = "mapping_cache/entities.json"):
        self.mapping_path = mapping_path
        self.entity_path = entity_path
        
        # Estructuras en RAM (O(1))
        self._mappings: Dict[str, MarketMapping] = {}
        self._entities: Dict[str, Dict[str, str]] = {} # sport -> {alias: canonical}
        
        # Inicialización
        os.makedirs(os.path.dirname(self.mapping_path), exist_ok=True)
        self._load_all()

    def _load_all(self):
        """Carga masiva a RAM."""
        # 1. Cargar Mapeos de Mercado
        if os.path.exists(self.mapping_path):
            try:
                with open(self.mapping_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for mid, mdata in data.items():
                        self._mappings[mid] = MarketMapping(**mdata)
                logger.info(f"[Cache] RAM Loaded: {len(self._mappings)} market mappings")
            except Exception as e:
                logger.error(f"[Cache] Error loading mappings: {e}")

        # 2. Cargar Entidades (Equipos/Jugadores)
        if os.path.exists(self.entity_path):
            try:
                with open(self.entity_path, 'r', encoding='utf-8') as f:
                    self._entities = json.load(f)
                count = sum(len(v) for v in self._entities.values())
                logger.info(f"[Cache] RAM Loaded: {count} entities across {len(self._entities)} sports")
            except Exception as e:
                logger.error(f"[Cache] Error loading entities: {e}")

    def get_entity(self, name: str, sport: str) -> Optional[str]:
        """
        Busca primero en RAM. Si falla, devuelve None.
        Evita lógica costosa; el AI resolverá los fallos.
        """
        if not name or not sport:
            return None
            
        sport_cache = self._entities.get(sport.lower(), {})
        # Exact match (normalized)
        return sport_cache.get(name.lower())

    def save_entity(self, alias: str, canonical: str, sport: str):
        """Guarda entidad en RAM y persiste atómicamente."""
        s = sport.lower()
        if s not in self._entities:
            self._entities[s] = {}
        
        self._entities[s][alias.lower()] = canonical
        self._persist_entities()

    def lookup_mapping(self, poly_id: str) -> Optional[MarketMapping]:
        """Lookup rápido de mapeo de mercado."""
        return self._mappings.get(poly_id)

    def save_mapping(self, mapping: MarketMapping):
        """Persistencia de mapeo."""
        self._mappings[mapping.polymarket_id] = mapping
        self._persist_mappings()

    def get_all_mappings(self) -> List[MarketMapping]:
        return list(self._mappings.values())

    def bulk_save(self, mappings: List[MarketMapping]):
        """Ahorra I/O guardando múltiples mapeos a la vez."""
        for m in mappings:
            self._mappings[m.polymarket_id] = m
        self._persist_mappings()

    def bulk_save_entities(self, entries: List[Dict[str, Any]]):
        """Guardado masivo de entidades (sport, alias, canonical)."""
        for item in entries:
            s = item['sport'].lower()
            if s not in self._entities:
                self._entities[s] = {}
            self._entities[s][item['alias'].lower()] = item['canonical']
        self._persist_entities()

    def _persist_mappings(self):
        try:
            temp_path = self.mapping_path + ".tmp"
            data = {}
            for mid, m in self._mappings.items():
                m_dict = m.to_dict() if hasattr(m, 'to_dict') else m.__dict__.copy()
                # Ensure mapped_at is string
                if 'mapped_at' in m_dict and isinstance(m_dict['mapped_at'], datetime):
                    m_dict['mapped_at'] = m_dict['mapped_at'].isoformat()
                data[mid] = m_dict
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            os.replace(temp_path, self.mapping_path)
        except Exception as e:
            logger.error(f"Persist Mappings Failed: {e}")

    def _persist_entities(self):
        try:
            temp_path = self.entity_path + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self._entities, f, indent=4)
            os.replace(temp_path, self.entity_path)
        except Exception as e:
            logger.error(f"Persist Entities Failed: {e}")

    def get_all_mappings(self) -> List[MarketMapping]:
        return list(self._mappings.values())
