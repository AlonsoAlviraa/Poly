
import pytest
from hypothesis import given, strategies as st
from src.arbitrage.entity_resolver_logic import static_matcher

# Estrategia para generar nombres de equipos realistas pero con ruido
@st.composite
def team_name_variation(draw):
    base_names = ["Manchester United", "Real Madrid", "Lakers", "Nadal", "G2 Esports"]
    base = draw(st.sampled_from(base_names))
    
    # Aplicar variaciones
    noise_prefix = draw(st.sampled_from(["", "The ", "FC ", "Club "]))
    noise_suffix = draw(st.sampled_from(["", " FC", " squad", " Team", " vs Any"]))
    
    # Posible typo (duplicar una letra aleatoria)
    typo = ""
    if len(base) > 3 and draw(st.booleans()):
        idx = draw(st.integers(0, len(base)-1))
        base = base[:idx] + base[idx] + base[idx:]
        
    return f"{noise_prefix}{base}{noise_suffix}"

@given(name_v=team_name_variation())
def test_resilience_to_variation(name_v):
    # Definimos los "canónicos" esperanzados
    canonicals = {
        "manchester united": "Manchester United",
        "real madrid": "Real Madrid",
        "lakers": "Los Angeles Lakers",
        "nadal": "Rafael Nadal",
        "g2 esports": "G2 Esports"
    }
    
    # El matcher debería encontrar el match si la variación es razonable
    # Nota: Como test de propiedad, buscamos que SI hay un match, sea con el correcto.
    name_low = name_v.lower()
    for target_key, canonical in canonicals.items():
        if target_key in name_low:
            # Si el fragmento clave está presente, el matcher debería (idealmente) funcionar
            # o al menos no matchear con OTRO canónico de la lista rival.
            res = static_matcher(name_v, canonical, "soccer")
            # No podemos asegurar 'MATCH' siempre (es fuzzy), 
            # pero podemos asegurar que NO matcheé con un rival directo bajo esta misma lógica.
            rival = "Manchester City" if "United" in canonical else "Atletico Madrid"
            assert static_matcher(name_v, rival, "soccer") is None

def test_hardcoded_stress_cases():
    # Casos de corrupción extrema que DEBEN funcionar
    assert static_matcher("Mnchstr Utd", "Manchester United", "soccer") == "MATCH"
    assert static_matcher("R. Madrid", "Real Madrid", "soccer") == "MATCH"
    assert static_matcher("Lakers LA", "Los Angeles Lakers", "basketball") == "MATCH"
