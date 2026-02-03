
import requests

base = "https://raw.githubusercontent.com/footballcsv"
# (repo_name, filename_prefix)
repos = [
    ("england", "eng"),
    ("espana", "es"),
    ("deutschland", "de"),
    ("italia", "it"),
    ("france", "fr"),
    ("nederland", "nl"),
    ("portugal", "pt"),
    ("turkiye", "tr"),
    ("belgie", "be"),
    ("austria", "at"),
    ("scotland", "sc"),
    ("brasil", "br"),
    ("argentina", "ar"),
    ("mexico", "mx"),
    ("usa", "us")
]

for repo, prefix in repos:
    # Try different year formats
    years = ["2020-21", "2020"]
    found = False
    for year in years:
        url = f"{base}/{repo}/master/2020s/{year}/{prefix}.1.csv"
        r = requests.head(url)
        if r.status_code == 200:
            print(f"MATCH: {repo} -> {url}")
            found = True
            break
    if not found:
        print(f"FAIL: {repo}")
