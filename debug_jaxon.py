
import json
from datetime import datetime
import dateutil.parser

def parse_date(d_str):
    if not d_str: return None
    try:
        if 'T' in d_str:
             return datetime.fromisoformat(d_str.replace('Z', '+00:00'))
        return dateutil.parser.parse(d_str)
    except:
        return None

def run():
    with open('dump_poly.json', 'r', encoding='utf-8') as f:
        poly = json.load(f)
    with open('dump_sx.json', 'r', encoding='utf-8') as f:
        sx = json.load(f)

    # Find Jaxon
    p_jaxon = next((p for p in poly if 'Jaxon' in p['question']), None)
    s_jaxon = next((s for s in sx if 'Jaxon' in s.get('name', '')), None)

    if p_jaxon and s_jaxon:
        print(f"Poly: {p_jaxon['question']}")
        print(f"Date Raw: {p_jaxon.get('_event_date_parsed') or p_jaxon.get('gameStartTime')}")
        pd = parse_date(p_jaxon.get('_event_date_parsed') or p_jaxon.get('gameStartTime'))
        print(f"Date Parsed: {pd}")

        print(f"SX: {s_jaxon.get('name')}")
        print(f"Date Raw: {s_jaxon.get('open_date')}")
        sd = parse_date(s_jaxon.get('open_date'))
        print(f"Date Parsed: {sd}")

        if pd and sd:
            diff = abs((pd - sd).total_seconds()) / 3600.0
            print(f"Diff Hours: {diff:.2f}")
            if diff > 24:
                print("BLOCKER: Diff > 24h")
            else:
                print("OK: Within 24h")
    else:
        print("Could not find Jaxon in both dumps.")

if __name__ == "__main__":
    run()
