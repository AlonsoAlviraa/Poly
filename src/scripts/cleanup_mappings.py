
import json
import os
import re

def cleanup_mappings(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    trash_patterns = [
        r'O/U', r'Over/Under', r'Total', r'Handicap', r'3\.5', r'2\.5', r'9\.5', r'10\.5', 
        r'Set \d', r'Games', r'Sets', r'Asian', r'Score', r'Line', r'O / U',
        r'Election', r'Governor', r'Senate', r'House', r'Race', r'Gubernatorial', r'D to win', r'C win', r'outright'
    ]
    trash_regex = re.compile('|'.join(trash_patterns), re.IGNORECASE)

    clean_data = {}
    removed_count = 0

    for shard, entities in data.items():
        if shard == "_metadata":
            clean_data[shard] = entities
            continue
            
        clean_entities = {}
        for canonical, aliases in entities.items():
            # Skip if canonical itself is trash
            if trash_regex.search(canonical) or canonical.strip() == "" or (shard == 'soccer' and 'win' in canonical.lower() and len(canonical.split()) < 4):
                removed_count += 1
                continue
                
            # If it's the specific Newcastle Knights case in soccer
            if shard == "soccer" and ("Knights" in canonical or any("Knights" in a for a in aliases)):
                removed_count += 1
                continue

            if isinstance(aliases, list):
                clean_aliases = [a for a in aliases if not trash_regex.search(a) and a.strip() != ""]
                if clean_aliases:
                    clean_entities[canonical] = clean_aliases
                else:
                    removed_count += 1
            else:
                clean_entities[canonical] = aliases

        clean_data[shard] = clean_entities

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, indent=4, ensure_ascii=False)

    print(f"Cleanup complete. Removed approximately {removed_count} trash entries/aliases.")

if __name__ == "__main__":
    cleanup_mappings("src/data/mappings.json")
