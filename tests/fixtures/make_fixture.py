"""Generates tests/fixtures/tiny_paper.pdf — a 2-page paper used by integration and system tests."""

import os

import fitz

PAGES = [
    ("Gated Memory Networks for Short Text Classification",
     "Abstract. Short texts such as tweets and search queries carry little context, which makes them hard "
     "to classify. We propose Gated Memory Networks (GMN), a model that stores word representations in an "
     "external memory and uses a learned gate to decide how much of the memory to read at each step. "
     "On three benchmark datasets GMN improves accuracy by 2.1 points on average over strong recurrent "
     "baselines while using 40 percent fewer parameters.\n\n"
     "1 Introduction. Recurrent neural networks read a sentence one word at a time and compress it into a "
     "single hidden vector. For short texts this compression loses rare but decisive words. A memory "
     "network instead keeps every word vector accessible, so the classifier can attend directly to the "
     "words that matter. However, plain memory networks read the whole memory at every step, which adds "
     "noise when most words are irrelevant."),
    ("",
     "2 Method. The gate is a sigmoid unit computed from the current query and the memory summary. When "
     "the gate value is close to zero the model ignores the memory and relies on the recurrent state. "
     "We train the whole network end to end with cross entropy loss and dropout of 0.3.\n\n"
     "3 Results. GMN reaches 88.4 percent accuracy on the TREC question dataset, compared with 86.1 "
     "percent for the best recurrent baseline. Ablation shows that removing the gate costs 1.7 points, "
     "which confirms that selective reading is the key ingredient.\n\n"
     "4 Limitations. The memory grows linearly with the text length, so GMN is not suited to long "
     "documents. We also only evaluate on English datasets."),
]


def build(path: str) -> None:
    doc = fitz.open()
    for title, body in PAGES:
        page = doc.new_page(width=595, height=842)
        y = 72
        if title:
            page.insert_textbox(fitz.Rect(72, y, 523, y + 60), title, fontsize=18, fontname="helv", align=1)
            y += 70
        page.insert_textbox(fitz.Rect(72, y, 523, 780), body, fontsize=11, fontname="helv")
    doc.set_metadata({"title": PAGES[0][0]})
    doc.save(path)


if __name__ == "__main__":
    build(os.path.join(os.path.dirname(__file__), "tiny_paper.pdf"))
