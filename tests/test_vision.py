"""Unit tests: vision baselines on synthetic images."""
import numpy as np
import cv2

from src.vision import blur_score, brightness


def test_blur_detects_blur(tmp_path):
    sharp = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    blurry = cv2.GaussianBlur(sharp, (21, 21), 0)
    p1, p2 = str(tmp_path / "s.png"), str(tmp_path / "b.png")
    cv2.imwrite(p1, sharp)
    cv2.imwrite(p2, blurry)
    assert blur_score(p1) > blur_score(p2)


def test_brightness_orders(tmp_path):
    dark = np.zeros((50, 50, 3), dtype=np.uint8)
    bright = np.full((50, 50, 3), 255, dtype=np.uint8)
    p1, p2 = str(tmp_path / "d.png"), str(tmp_path / "w.png")
    cv2.imwrite(p1, dark)
    cv2.imwrite(p2, bright)
    assert brightness(p2) > brightness(p1)
