"""Make the benchmark set of the downloader: benchmarks/downloader/dois.csv.

Run it from the repository root (it uses the network: OpenAlex):

    python benchmarks/downloader/make_set.py --email you@lab.org

The set has two parts (column "set"):
    references  the 100 reference DOIs of the sample papers (the first version of the set)
    random      a random sample of N_RANDOM journal articles in psychology and the social sciences,
                published in YEARS, from OpenAlex (fixed seed, so a new run gives the same DOIs)

For each DOI the file gives the title, the open-access status, the publisher and the year (OpenAlex).
"""

import argparse
import csv
import json
import os
import time
import urllib.request
from urllib.parse import quote

SET_CSV = "benchmarks/downloader/dois.csv"
COLUMNS = ["doi", "set", "title", "is_oa", "oa_status", "publisher", "year"]
N_RANDOM = 200          # the size of the random part
SEED = 7                # the OpenAlex sample seed; keep it, so the set stays the same
YEARS = "2000-2024"
FIELDS = "fields/32|fields/33"      # OpenAlex fields: 32 Psychology, 33 Social Sciences
SAMPLE_URL = ("https://api.openalex.org/works?filter=primary_topic.field.id:{fields},type:article,"
              "has_doi:true,publication_year:{years}&sample={n}&seed={seed}&per-page={n}&mailto={email}")


def get_json(url):
    """Return the JSON of a GET request."""
    request = urllib.request.Request(url, headers={"User-Agent": "theoryminer benchmark"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def row_of(work, part):
    """Return one set row from an OpenAlex work."""
    open_access = work.get("open_access") or {}
    source = (work.get("primary_location") or {}).get("source") or {}
    return {"doi": work["doi"].replace("https://doi.org/", "").lower(), "set": part,
            "title": " ".join((work.get("title") or "").split()),
            "is_oa": open_access.get("is_oa", False), "oa_status": open_access.get("oa_status", ""),
            "publisher": source.get("host_organization_name") or "", "year": work.get("publication_year", "")}


def reference_rows():
    """Return the reference part of the existing set (the first 100 rows of the first version)."""
    with open(SET_CSV, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    kept = []
    for row in rows:
        if row.get("set", "references") == "references":
            row["set"] = "references"
            kept.append(row)
    return kept


def random_rows(email, known):
    """Return N_RANDOM random articles from OpenAlex that are not in the known DOIs."""
    url = SAMPLE_URL.format(fields=FIELDS, years=YEARS, n=N_RANDOM, seed=SEED, email=quote(email))
    rows = []
    for work in get_json(url)["results"]:
        row = row_of(work, "random")
        if row["doi"] not in known:
            rows.append(row)
    time.sleep(1)
    return rows


def main():
    """Read the reference part, add the random part, write the set."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", default=os.environ.get("UNPAYWALL_EMAIL", ""), help="the email for OpenAlex")
    args = parser.parse_args()
    rows = reference_rows()
    known = {row["doi"] for row in rows}
    rows += random_rows(args.email, known)
    with open(SET_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    n_open = len([row for row in rows if str(row["is_oa"]) == "True"])
    print(f"{SET_CSV}: {len(rows)} DOIs, {n_open} open access")


if __name__ == "__main__":
    main()
