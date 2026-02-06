
import json
import os
import logging
import unicodedata
import re
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_text(text: str) -> str:
    """Normaliza texto (acentos, minúsculas, caracteres especiales)."""
    text = text.lower().strip()
    # Quitar acentos
    text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

def is_garbage(alias: str, canonical: str) -> bool:
    """Detecta si un alias es basura obvia."""
    garbage_proxies = {'id', 'sport', 'metadata', 'unknown', 'null', 'undefined', 'n/a'}
    if alias.lower() in garbage_proxies:
        return True
    if len(alias) < 2:
        return True
    return False

def clean_mappings_file(file_path: str):
    if not os.path.exists(file_path):
        logger.error(f"Archivo no encontrado: {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cleaned_data = {}
    total_removed = 0
    total_normalized = 0

    for sport, categories in data.items():
        cleaned_data[sport] = {}
        for canonical, aliases in categories.items():
            new_aliases = []
            normalized_canonical = canonical # Mantener el canónico original como clave pero limpiar sus alias
            
            for alias in aliases:
                if is_garbage(alias, canonical):
                    total_removed += 1
                    continue
                
                # Normalización (opcionalmente guardar una versión limpia)
                norm_alias = normalize_text(alias)
                if norm_alias not in [normalize_text(a) for a in new_aliases]:
                    new_aliases.append(alias) # Guardamos el original por legibilidad
                    total_normalized += 1
            
            if new_aliases:
                cleaned_data[sport][canonical] = list(set(new_aliases))

    # Guardar backup
    backup_path = file_path + ".bak"
    with open(backup_path, "w", encoding="utf-8") as fb:
        json.dump(data, fb, indent=4, ensure_ascii=False)
    
    # Guardar limpio
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

    logger.info(f"✨ Limpieza completada.")
    logger.info(f"🗑️ Alias basura eliminados: {total_removed}")
    logger.info(f"🔄 Alias normalizados/mantenidos: {total_normalized}")
    logger.info(f"📦 Backup creado en: {backup_path}")

if __name__ == "__main__":
    path = os.path.join("src", "data", "mappings.json")
    clean_mappings_file(path)
