"""Tests for harvest(): one PDF, a folder of PDFs, and bad files.

Run them from the repository root:

    pytest tests/

The tests use the papers in sample_files/. They make the bad files in a
temporary folder. No test loads a model, so the tests take seconds.
"""

import json
import os
import shutil

import pytest

from theoryminer import harvest

SAMPLE_DIR = "sample_files"


def sample_pdfs():
    """Return the paths of the PDF files in sample_files/, sorted."""
    paths = []
    for name in sorted(os.listdir(SAMPLE_DIR)):
        if name.lower().endswith(".pdf"):
            paths.append(os.path.join(SAMPLE_DIR, name))
    return paths


def reasons_by_doc(data):
    """Return {doc_id: drop_reason} for the rows that skip a whole file (page 0)."""
    reasons = {}
    for row in data["dropped"]:
        if row["page"] == 0:
            reasons[row["doc_id"]] = row["drop_reason"]
    return reasons


def make_bad_folder(folder):
    """Put one good PDF and four bad files in the folder."""
    good = sample_pdfs()[0]
    shutil.copy(good, os.path.join(folder, "good.pdf"))
    with open(os.path.join(folder, "notes.txt"), "w") as fh:
        fh.write("A text file, not a PDF.")
    with open(os.path.join(folder, "webpage.pdf"), "w") as fh:
        fh.write("<!DOCTYPE html><html><body>Access denied</body></html>")
    with open(os.path.join(folder, "empty.pdf"), "w") as fh:
        fh.write("")
    with open(good, "rb") as fh:
        start = fh.read(5000)
    with open(os.path.join(folder, "truncated.pdf"), "wb") as fh:
        fh.write(start)


def test_folder_with_bad_files_does_not_stop(tmp_path):
    make_bad_folder(tmp_path)
    data = harvest(str(tmp_path), cache=False)

    reasons = reasons_by_doc(data)
    assert reasons == {"notes": "not_pdf",
                       "webpage": "unreadable_pdf",
                       "empty": "unreadable_pdf",
                       "truncated": "unreadable_pdf"}

    doc_ids = set()
    for sentence in data["sentences"]:
        doc_ids.add(sentence["doc_id"])
    assert doc_ids == {"good"}
    assert len(data["sentences"]) > 50


def test_skipped_file_row_gives_the_error_message(tmp_path):
    make_bad_folder(tmp_path)
    data = harvest(str(tmp_path), cache=False)
    for row in data["dropped"]:
        if row["doc_id"] == "webpage":
            assert row["text"] == "webpage.pdf: Not a PDF: file appears to be HTML"


def test_one_bad_file_raises(tmp_path):
    make_bad_folder(tmp_path)
    for name in ["webpage.pdf", "empty.pdf", "truncated.pdf", "notes.txt"]:
        with pytest.raises(ValueError):
            harvest(os.path.join(tmp_path, name), cache=False)


def test_missing_path_raises():
    with pytest.raises(ValueError, match="no file or folder"):
        harvest("no/such/folder")


def test_folder_without_pdf_raises(tmp_path):
    with open(os.path.join(tmp_path, "notes.txt"), "w") as fh:
        fh.write("text")
    with pytest.raises(ValueError, match="no PDF file"):
        harvest(str(tmp_path))


def test_one_pdf_gives_document_zero():
    data = harvest(sample_pdfs()[0])
    for sentence in data["sentences"]:
        assert sentence["sent_id"].startswith("d000p")


def test_sample_folder_ids_are_unique():
    data = harvest(SAMPLE_DIR)

    sent_ids = []
    doc_ids = set()
    for sentence in data["sentences"]:
        sent_ids.append(sentence["sent_id"])
        doc_ids.add(sentence["doc_id"])
    assert len(sent_ids) == len(set(sent_ids))
    assert len(doc_ids) == len(sample_pdfs())

    # Each document number belongs to one document only.
    doc_of_number = {}
    for sentence in data["sentences"]:
        number = sentence["sent_id"][:4]
        doc_of_number.setdefault(number, sentence["doc_id"])
        assert doc_of_number[number] == sentence["doc_id"]


def test_broken_cache_is_rebuilt(tmp_path):
    pdf = os.path.join(tmp_path, "paper.pdf")
    shutil.copy(sample_pdfs()[0], pdf)
    with open(pdf + ".pages.json", "w") as fh:
        fh.write('{"1": "half a fi')
    data = harvest(pdf)
    assert len(data["sentences"]) > 50
    with open(pdf + ".pages.json") as fh:
        assert fh.read().startswith('{"1":')


def test_page_cache_stands_in_for_a_missing_pdf(tmp_path):
    fake_pdf = os.path.join(tmp_path, "toy.pdf")
    with open(fake_pdf + ".pages.json", "w") as fh:
        fh.write('{"1": "Autonomy support increases intrinsic motivation in students.\\n"}')
    data = harvest(fake_pdf)
    assert data["sentences"][0]["clean"] == "Autonomy support increases intrinsic motivation in students."
    assert data["sentences"][0]["sent_id"] == "d000p0000s000"


def test_sidebar_text_gets_the_front_matter_flag(tmp_path):
    fake_pdf = os.path.join(tmp_path, "toy.pdf")
    page = ("Support increased EFL Reviewed by: Zhengdong Gan, University of Macau, motivation.\n"
            "\n"
            "Autonomy support increases intrinsic motivation in students.\n")
    with open(fake_pdf + ".pages.json", "w") as fh:
        json.dump({"1": page}, fh)
    data = harvest(fake_pdf)
    flags = [s["flag"] for s in data["sentences"]]
    assert flags == ["front_matter", ""]
