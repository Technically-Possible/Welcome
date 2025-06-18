import json
import os
import sys
from pathlib import Path
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import generate_photography_json as gpj


def test_create_thumbnail_no_upscale(tmp_path):
    src = tmp_path / "small.jpg"
    width, height = gpj.THUMB_MAX_WIDTH - 50, 80
    Image.new("RGB", (width, height)).save(src)

    dst = tmp_path / "thumb.jpg"
    gpj.create_thumbnail(str(src), str(dst))

    with Image.open(dst) as img:
        assert img.width == width
        assert img.height == height

def test_generate_json(tmp_path, monkeypatch):
    photography_dir = tmp_path / "photography"
    event_dir = photography_dir / "2022" / "party"
    event_dir.mkdir(parents=True)

    img1 = event_dir / "img1.jpg"
    img2 = event_dir / "img2.jpg"
    Image.new("RGB", (400, 300)).save(img1)
    Image.new("RGB", (400, 300)).save(img2)

    thumbnails_dir = tmp_path / "thumbnails"
    output_json = tmp_path / "photography.json"

    monkeypatch.setattr(gpj, "PHOTOGRAPHY_DIR", str(photography_dir))
    monkeypatch.setattr(gpj, "THUMBNAIL_DIR", str(thumbnails_dir))
    monkeypatch.setattr(gpj, "OUTPUT_JSON_PATH", str(output_json))
    monkeypatch.setattr(gpj, "BASE_DIR", str(tmp_path))

    gpj.generate_json()

    assert output_json.exists()
    data = json.loads(output_json.read_text())

    assert data["years"][0]["year"] == "2022"
    event = data["years"][0]["events"][0]
    assert event["name"] == "party"
    images = event["images"]
    assert len(images) == 2

    for entry in images:
        thumb_path = tmp_path / entry["thumb"]
        full_path = tmp_path / entry["full"]
        assert thumb_path.exists()
        assert full_path.exists()
