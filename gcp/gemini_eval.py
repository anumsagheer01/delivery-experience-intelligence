#!/usr/bin/env python3
"""Gemini structured POD eval via Vertex AI + OpenCV baselines, same 114 images.

Weak labels: box/ = package likely visible (positive), neg/ = negative.
Compares Gemini SOP verdict vs OpenCV heuristic on the SAME images.
"""
import json
import os
import urllib.request

import vertexai
from vertexai.generative_models import GenerativeModel, Part

PROJECT = "delivery-experience-511901"
LOCATION = "us-central1"
IMG_DIR = "/home/anumsagheer3/dei-data/openimages"
os.makedirs(IMG_DIR, exist_ok=True)

LABELS = {'0c8f84c8315e1d50': 'box', '6f77c153f44d6168': 'box', 'a5896d580f0b6e68': 'box', '2e1ba5d780612dd2': 'box', '0c9c9ebe5c9aff0b': 'box', '3030fcc2b2c9e66c': 'box', 'eb816b440550f451': 'box', '7571f21c28d4f46d': 'box', '98ba97deb0feb657': 'box', 'da923c37ba25ba5e': 'box', '3b533045f8b16660': 'box', 'c242cbc0c16ee376': 'box', 'e3f991d2c5cafb5c': 'box', 'f187717e68a02c4b': 'box', 'e8788a121e93ff6b': 'box', '0e06a2c8ec61797b': 'box', '403251bc562cd579': 'box', '23a4a86fcab629c5': 'box', 'fef817805b4d939b': 'box', '93761b495f38db5a': 'box', 'c3585cbb08eac734': 'box', '3244bcda9de87cdf': 'box', '3d93458d9b114321': 'box', '04e310af546ec9d0': 'box', 'c3335fdccbcfb26e': 'box', '6977321487797845': 'box', '632d572ccfd5602a': 'box', '7a18cc3a0bb314fe': 'box', '2e402ae4b2addb7e': 'box', 'df6dd70f7cc1aee6': 'box', '2a3ab4239291c1f8': 'box', '92b35794b20fe67d': 'box', '6be461921a2b69f1': 'box', 'ca8a0cd3e9161134': 'box', 'a17f85e33b8bbeb5': 'box', 'bfd453a9345ee0fc': 'box', 'c657ecb44d0b48ea': 'box', '7d19c6655ae82c10': 'box', '72b13048f15f513c': 'box', '805c7d693fd2f5ba': 'box', '77dfca8654540b7c': 'box', 'ffcd9304121e8870': 'box', '2bca762eac2f0975': 'box', '4dbb7abda583bbaa': 'box', 'beafcc5909c27004': 'box', '6f27874f5bb62e71': 'box', '16374cbdb62f53de': 'box', 'd8ae9d468540bf23': 'box', '9c54662ca0b0074f': 'box', '480aaba6e5555261': 'box', '9a52929f906f2729': 'box', '0de5621ed7b01e19': 'box', 'a362901a8fd28363': 'box', '1d1afe76705ba499': 'box', '405c5aa475390e50': 'box', 'fd21435721d28b95': 'box', '950374cc711e4ed2': 'box', '3c9d7e3daa57dbbc': 'box', 'ea37bb8ce97f36d2': 'box', 'cc687f4313e3fa71': 'box', 'a13666039be9102d': 'box', 'a041215905cbc83c': 'box', '5cc53ecdb01c9a42': 'box', '83492346f87d201e': 'box', 'b1d714080c40f4d6': 'box', '5feee9cc4477d5bd': 'box', '09ebcee57699eb98': 'box', '107f15212a86a661': 'box', '42498a88ba8df18e': 'box', '1f423f368aebf7f3': 'box', 'fa4d75b0728a87cc': 'box', '7c2c087a24f4edd0': 'box', '002b0dc60b1068a9': 'box', 'fc68014ad98b3486': 'box', '29e23996d8976a2b': 'box', '90d070d5cbc8dd9a': 'box', '6f56fe1c76385554': 'box', '136486a8ec13f164': 'box', '665cac5fd1cc2186': 'box', 'bd07e6458690f347': 'box', '53b4f49b09747d35': 'box', '92a0a6e90840355f': 'box', '6d4e234692694cd4': 'box', '995243986ca2dd84': 'box', '59e42831e9150601': 'box', '5563f792d702bdbd': 'box', '1c15b52782e87852': 'box', 'a5dc9b8e19130d1e': 'box', '0d8806337b963d80': 'box', 'ba82c70cc6cdf449': 'neg', '7d00af2927a57eeb': 'neg', '914dd6fb5eb17e85': 'neg', 'eb59a7a5d5518d31': 'neg', '4ea213d7e78c2d41': 'neg', '392e97d541b21104': 'neg', '2673e8f3d459e3bf': 'neg', '2519f63ec4883bd2': 'neg', '61ead689dba1ebc5': 'neg', '2f9ea40fc5161426': 'neg', '6a5a69bc0ed96330': 'neg', '2fed663b4eb60fc8': 'neg', '9728bc1301475043': 'neg', '1a229f63f9f03f91': 'neg', '63e3c93d6afbdbde': 'neg', '9c7e8b7f827cf707': 'neg', 'f337b78b051260cb': 'neg', 'b0a63dfc85045447': 'neg', 'ac64309938699c5f': 'neg', '25a694ee730ba3c2': 'neg', '2db95c7de25d0142': 'neg', 'c40a139fa37b26e6': 'neg', '2f6f39b9c34f5377': 'neg', 'f70e3e9e09d8f672': 'neg', 'b502185ab84ddf0f': 'neg'}

PROMPT = """You are a delivery quality inspector. Look at this proof-of-delivery photo and return JSON only: {"package_visible": true/false, "quality": "good|package_obscured|blurry|wrong_location|unsafe_placement|low_light|no_package", "confidence": 0.0-1.0, "rationale": "one sentence"} A POD photo must show the delivered package at the customer's door."""

def download_images():
    ok, failed = 0, []
    for img_id in LABELS:
        dest = os.path.join(IMG_DIR, img_id + ".jpg")
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            ok += 1
            continue
        url = "https://storage.googleapis.com/openimages/v6/train/" + img_id + ".jpg"
        try:
            urllib.request.urlretrieve(url, dest)
            ok += 1
        except Exception:
            failed.append(img_id)
    print("downloaded: %d failed: %d" % (ok, len(failed)))
    return failed

def opencv_score(path):
    import cv2
    import numpy as np
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    b = float(cv2.Laplacian(img, cv2.CV_64F).var())
    br = float(np.mean(img))
    return {"laplacian_var": round(b, 1), "brightness": round(br, 1),
            "package_visible": bool(b > 50.0 and br > 25.0)}

def main():
    failed = download_images()
    vertexai.init(project=PROJECT, location=LOCATION)
    model = GenerativeModel("gemini-2.0-flash")
    rows, gem_ok, gem_fail = [], 0, 0
    for img_id, weak in LABELS.items():
        if img_id in failed:
            continue
        path = os.path.join(IMG_DIR, img_id + ".jpg")
        cv = opencv_score(path)
        truth = (weak == "box")
        row = {"image_id": img_id, "weak_label": weak, "weak_positive": truth, "opencv": cv}
        try:
            with open(path, "rb") as f:
                img_part = Part.from_data(f.read(), mime_type="image/jpeg")
            resp = model.generate_content([PROMPT, img_part])
            text = resp.text.strip().strip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()
            g = json.loads(text)
            row["gemini"] = g
            gem_ok += 1
        except Exception as e:
            row["gemini"] = {"error": str(e)[:200]}
            gem_fail += 1
        rows.append(row)
        if (gem_ok + gem_fail) % 20 == 0:
            print("progress: %d ok, %d failed" % (gem_ok, gem_fail), flush=True)
    out = "/home/anumsagheer3/dei-data/gemini_eval.json"
    with open(out, "w") as f:
        json.dump(rows, f)
    tp = fp = tn = fn = 0
    gtp = gfp = gtn = gfn = 0
    for r in rows:
        t = r["weak_positive"]
        if r["opencv"]:
            p = r["opencv"]["package_visible"]
            if t and p: tp += 1
            elif t: fn += 1
            elif p: fp += 1
            else: tn += 1
        g = r.get("gemini") or {}
        if "package_visible" in g:
            p = bool(g["package_visible"])
            if t and p: gtp += 1
            elif t: gfn += 1
            elif p: gfp += 1
            else: gtn += 1
    print("gemini calls ok: %d failed: %d" % (gem_ok, gem_fail))
    print("opencv vs weak labels: tp=%d fp=%d tn=%d fn=%d" % (tp, fp, tn, fn))
    print("gemini vs weak labels: tp=%d fp=%d tn=%d fn=%d" % (gtp, gfp, gtn, gfn))
    print("results: " + out)

main()
