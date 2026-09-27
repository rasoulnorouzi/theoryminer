"""Tests for extract_dois(). No test loads a model, so the tests take seconds.

The answer key was made by hand: each DOI was read from page 1 of the PDF itself.
"""

import csv
import json
import os
import shutil

import pytest

from theoryminer import extract_dois

SAMPLE_DIR = "sample_files"

# The DOI printed on page 1 of each sample paper, read by a person.
ANSWER_KEY = {
    "alrabai_2021_autonomy_supportive_teaching.pdf": "10.3389/fpsyg.2021.728657",
    "barrech_2018_job_insecurity_health.pdf": "10.1186/s12889-018-5621-4",
    "friesinger_2025_discrimination_health.pdf": "10.1186/s12889-025-23888-6",
    "gordesli_2024_social_media_mental_health.pdf": "10.1371/journal.pone.0316365",
    "pelikan_2021_needs_intrinsic_motivation.pdf": "10.1371/journal.pone.0257346",
    "schutz_2025_loneliness_social_support.pdf": "10.1186/s12889-025-23247-5",
    "stephany_2017_income_inequality_trust.pdf": "10.1007/s11205-016-1460-9",
}


def fake_pdf(folder, name, pages):
    """Write a page cache for a PDF that does not exist, and return the PDF path."""
    path = os.path.join(folder, name)
    with open(path + ".pages.json", "w") as fh:
        json.dump(pages, fh)
    return path


def test_every_sample_paper_gets_its_own_doi():
    rows = extract_dois(SAMPLE_DIR)
    found = {}
    for row in rows:
        if row["status"] == "found":
            found[row["file"]] = row["doi"]
    assert found == ANSWER_KEY


def test_one_pdf_gives_one_row():
    rows = extract_dois(os.path.join(SAMPLE_DIR, "stephany_2017_income_inequality_trust.pdf"))
    assert len(rows) == 1
    assert rows[0]["doi"] == "10.1007/s11205-016-1460-9"
    assert rows[0]["page"] == 1


def test_bad_files_get_a_status_and_do_not_stop_the_run(tmp_path):
    shutil.copy(os.path.join(SAMPLE_DIR, "barrech_2018_job_insecurity_health.pdf"), tmp_path / "good.pdf")
    (tmp_path / "notes.txt").write_text("A text file, not a PDF.")
    (tmp_path / "webpage.pdf").write_text("<!DOCTYPE html><html><body>Access denied</body></html>")
    (tmp_path / "empty.pdf").write_text("")
    rows = extract_dois(str(tmp_path), cache=False)
    status = {}
    for row in rows:
        status[row["file"]] = row["status"]
    assert status == {"good.pdf": "found", "notes.txt": "not_pdf",
                      "webpage.pdf": "unreadable_pdf", "empty.pdf": "unreadable_pdf"}


def test_doi_is_cleaned_and_lowercase(tmp_path):
    path = fake_pdf(tmp_path, "paper.pdf", {"1": "Front. Psychol. doi: 10.3389/FPSYG.2021.728657*\n"})
    assert extract_dois(path)[0]["doi"] == "10.3389/fpsyg.2021.728657"


def test_a_doi_only_in_the_references_is_not_the_paper_doi(tmp_path):
    pages = {"1": "A title\n\nAn abstract without a DOI.\n", "2": "Text.\n", "3": "References: 10.1016/j.x.2020.1\n"}
    path = fake_pdf(tmp_path, "paper.pdf", pages)
    row = extract_dois(path)[0]
    assert row["status"] == "not_found"
    assert row["doi"] == ""


def test_a_cover_page_moves_the_doi_to_page_2(tmp_path):
    pages = {"1": "Cover page of the repository\n", "2": "https://doi.org/10.1186/s12889-018-5621-4\n"}
    path = fake_pdf(tmp_path, "paper.pdf", pages)
    row = extract_dois(path)[0]
    assert (row["doi"], row["page"]) == ("10.1186/s12889-018-5621-4", 2)


def test_save_to_a_csv_file_and_to_a_folder(tmp_path):
    path = fake_pdf(tmp_path, "paper.pdf", {"1": "DOI 10.1007/s11205-016-1460-9\n"})

    extract_dois(path, save=str(tmp_path / "out" / "my_dois.csv"))
    with open(tmp_path / "out" / "my_dois.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["doi"] == "10.1007/s11205-016-1460-9"

    extract_dois(path, save=str(tmp_path / "results"))
    assert os.path.isfile(tmp_path / "results" / "dois.csv")


def test_missing_path_raises():
    with pytest.raises(ValueError, match="no file or folder"):
        extract_dois("no/such/folder")


def test_folder_without_pdf_raises(tmp_path):
    (tmp_path / "notes.txt").write_text("text")
    with pytest.raises(ValueError, match="no PDF file"):
        extract_dois(str(tmp_path))


# The first words of each title, as sample_files/SOURCES.md gives them (from the publisher pages).
TITLE_KEY = {
    "alrabai_2021_autonomy_supportive_teaching.pdf": "The Influence of Autonomy-Supportive Teaching on EFL Students",
    "barrech_2018_job_insecurity_health.pdf": "The impact of job insecurity on long-term self-rated health",
    "friesinger_2025_discrimination_health.pdf": "Associations between perceived discrimination and health",
    "gordesli_2024_social_media_mental_health.pdf": "Moderating effect of cultural differences on the association",
    "pelikan_2021_needs_intrinsic_motivation.pdf": "Distance learning in higher education during COVID-19",
    "schutz_2025_loneliness_social_support.pdf": "Lonely children and adolescents are less healthy",
    "stephany_2017_income_inequality_trust.pdf": "Who are Your Joneses? Socio-Specific Income Inequality and Trust",
}


def test_every_sample_paper_gets_its_title():
    for row in extract_dois(SAMPLE_DIR):
        if row["status"] == "found":
            assert row["title"].startswith(TITLE_KEY[row["file"]]), row["file"]


def test_a_page_cache_without_its_pdf_gives_no_title(tmp_path):
    path = fake_pdf(tmp_path, "paper.pdf", {"1": "doi: 10.1186/s12889-018-5621-4\n"})
    assert extract_dois(path)[0]["title"] == ""


def test_the_csv_has_a_title_column(tmp_path):
    extract_dois(os.path.join(SAMPLE_DIR, "stephany_2017_income_inequality_trust.pdf"), save=str(tmp_path))
    with open(tmp_path / "dois.csv", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    assert row["title"] == "Who are Your Joneses? Socio-Specific Income Inequality and Trust"
