"""Streamlit labeling app: human review for the 300-image POD quality benchmark.

Quality labels (multi-label; a photo can have several defects):
  good, package_obscured, blurry, wrong_location, unsafe_placement,
  low_light, no_package

Run: streamlit run src/vision/labeling_app.py -- --images data/raw/openimages
Labels append to labels.csv. Images already labeled are skipped.
"""
import argparse
import csv
import os

LABELS = ["good", "package_obscured", "blurry", "wrong_location",
          "unsafe_placement", "low_light", "no_package"]


def collect_images(root: str) -> list:
    out = []
    for dp, _, files in os.walk(root):
        for f in sorted(files):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                out.append(os.path.join(dp, f))
    return out


def load_done(csv_path: str) -> set:
    done = set()
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                done.add(row["image"])
    return done


def main():
    import streamlit as st
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default="data/raw/openimages")
    ap.add_argument("--out", default="evals/vision/labels.csv")
    args, _ = ap.parse_known_args()

    st.title("POD quality labeling")
    st.write("Check ALL defects that apply. Be strict: this is the eval benchmark.")
    images = collect_images(args.images)
    done = load_done(args.out)
    todo = [p for p in images if p not in done]
    st.write(f"{len(done)} labeled, {len(todo)} remaining")
    if not todo:
        st.success("All images labeled.")
        return
    path = todo[0]
    st.image(path, width=500)
    st.caption(path)
    cols = st.columns(4)
    checked = {lab: cols[i % 4].checkbox(lab) for i, lab in enumerate(LABELS)}
    if st.button("Save and next"):
        chosen = [lab for lab, v in checked.items() if v] or ["good"]
        new_file = not os.path.exists(args.out)
        with open(args.out, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["image", "labels"])
            if new_file:
                w.writeheader()
            w.writerow({"image": path, "labels": ";".join(chosen)})
        st.rerun()


if __name__ == "__main__":
    main()
