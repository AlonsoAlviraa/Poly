
import requests

base_url = "https://raw.githubusercontent.com/footballcsv"
sources = [
    # Top 5
    f"{base_url}/england/master/2020s/2020-21/eng.1.csv",
    f"{base_url}/spain/master/2020s/2020-21/es.1.csv",
    f"{base_url}/germany/master/2020s/2020-21/de.1.csv",
    f"{base_url}/italy/master/2020s/2020-21/it.1.csv",
    f"{base_url}/france/master/2020s/2020-21/fr.1.csv",
    
    # Second Tiers
    f"{base_url}/england/master/2020s/2020-21/eng.2.csv",
    f"{base_url}/spain/master/2020s/2020-21/es.2.csv",
    f"{base_url}/germany/master/2020s/2020-21/de.2.csv",
    f"{base_url}/italy/master/2020s/2020-21/it.2.csv",
    f"{base_url}/france/master/2020s/2020-21/fr.2.csv",
]

for url in sources:
    r = requests.head(url)
    print(f"{url}: {r.status_code}")
