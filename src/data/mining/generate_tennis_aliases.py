"""
Tennis Alias Generator
Generates common name variations for top tennis players to solve the "J. Sinner" vs "Jannik Sinner" problem.
Updates mapping_cache/entities.json directly.
"""
import json
import os

ENTITIES_FILE = "mapping_cache/entities.json"

# Top Players (ATP & WTA) - Knowledge Base
# We can expand this list or fetch it dynamically later.
PLAYERS = [
    # ATP Top
    "Jannik Sinner", "Carlos Alcaraz", "Novak Djokovic", "Daniil Medvedev", "Alexander Zverev",
    "Andrey Rublev", "Holger Rune", "Hubert Hurkacz", "Casper Ruud", "Alex de Minaur",
    "Stefanos Tsitsipas", "Taylor Fritz", "Grigor Dimitrov", "Tommy Paul", "Ben Shelton",
    "Frances Tiafoe", "Karen Khachanov", "Sebastian Baez", "Ugo Humbert", "Adrian Mannarino",
    "Lorenzo Musetti", "Alexander Bublik", "Felix Auger-Aliassime", "Arthur Fils", "Gael Monfils",
    "Sebastian Korda", "Cameron Norrie", "Jack Draper", "Matteo Berrettini", "Andy Murray",
    "Stan Wawrinka", "Dominic Thiem", "Rafael Nadal", "Kei Nishikori", "Denis Shapovalov",
    "Thanasi Kokkinakis", "Nick Kyrgios", "Borna Coric", "Lorenzo Sonego", "Fabian Marozsan",
    "Jakub Mensik", "Tomas Machac", "Flavio Cobolli", "Mariano Navone", "Luciano Darderi",
    
    # WTA Top
    "Iga Swiatek", "Aryna Sabalenka", "Coco Gauff", "Elena Rybakina", "Jessica Pegula",
    "Marketa Vondrousova", "Qinwen Zheng", "Maria Sakkari", "Ons Jabeur", "Jelena Ostapenko",
    "Daria Kasatkina", "Danielle Collins", "Beatriz Haddad Maia", "Jasmine Paolini",
    "Madison Keys", "Liudmila Samsonova", "Ekaterina Alexandrova", "Elina Svitolina",
    "Veronika Kudermetova", "Caroline Garcia", "Barbara Krejcikova", "Anastasia Pavlyuchenkova",
    "Marta Kostyuk", "Victoria Azarenka", "Dayana Yastremska", "Sorana Cirstea",
    "Linda Noskova", "Katie Boulter", "Mirra Andreeva", "Sloane Stephens", "Naomi Osaka",
    "Angelique Kerber", "Caroline Wozniacki", "Simona Halep", "Paula Badosa", "Emma Raducanu",
    "Bianca Andreescu", "Karolina Pliskova", "Petra Kvitova", "Belinda Bencic", "Leylah Fernandez",
    "Camila Osorio", "Camila Giorgi", "Anna Kalinskaya", "Anastasia Potapova", "Sara Bejlek", 
    "Clara Tauson" # Added from our finding
]

def generate_aliases(full_name):
    """Generate list of aliases for a full name 'First Last'."""
    parts = full_name.split()
    if len(parts) < 2:
        return []
    
    first, last = parts[0], parts[-1]
    
    aliases = [
        last,                      # "Sinner"
        f"{first[0]}. {last}",     # "J. Sinner"
        f"{first[0]} {last}",      # "J Sinner"
        f"{last}, {first[0]}.",    # "Sinner, J."
        f"{last} {first[0]}",      # "Sinner J"
        full_name.lower(),         # "jannik sinner"
    ]
    
    # Handle hyphens? "Smith-Njigba" -> "Smith Njigba"? Maybe, but riskier.
    
    return [a.lower() for a in aliases]

def run_generator():
    print(f">> Generating aliases for {len(PLAYERS)} tennis players...")
    
    # Load existing
    if os.path.exists(ENTITIES_FILE):
        with open(ENTITIES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}
        
    if "tennis" not in data:
        data["tennis"] = {}
        
    count = 0
    for p in PLAYERS:
        canonical = p
        aliases = generate_aliases(p)
        
        for alias in aliases:
            # Danger: "Sinner" is unique? Usually yes for top tier. 
            # If "Williams" (Serena vs Venus), we have a problem.
            # For now, simplistic approach implies checking conflicts manually later.
            # We overwrite if specific.
            
            # Skip short aliases if they might be common words (e.g. "Paul")
            if len(alias) < 4 and alias not in ['Li', 'Na']: 
                continue
                
            if alias not in data["tennis"]:
                data["tennis"][alias] = canonical
                count += 1
                
    # Save
    with open(ENTITIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, sort_keys=True)
        
    print(f">> Injected {count} new tennis aliases into {ENTITIES_FILE}")

if __name__ == "__main__":
    run_generator()
