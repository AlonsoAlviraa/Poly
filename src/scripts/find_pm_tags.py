import requests
import json

def find_tags():
    url = "https://gamma-api.polymarket.com/tags?limit=1000"
    resp = requests.get(url)
    tags = resp.json()
    
    targets = ['Basketball', 'NBA', 'NCAA', 'Endesa', 'Liga ACB', 'Euroleague', 'WNBA', 'Tennis', 'ATP', 'WTA', 'ITF']
    found = []
    
    print(f"Total tags received: {len(tags)}")
    for t in tags:
        label = str(t.get('label', '')).lower()
        id_ = t.get('id')
        # Print everything that looks like a sport
        if any(x in label for x in ['ball', 'tennis', 'nba', 'ncaa', 'soccer', 'league', 'atp', 'wta']):
            print(f"{id_}: {t['label']} ({t['slug']})")

if __name__ == "__main__":
    find_tags()
