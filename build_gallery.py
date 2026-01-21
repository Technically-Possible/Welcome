#!/usr/bin/env python3
"""
build_gallery.py

Creates thumbnails + photography.json, with portraits placed at the end
of each city/event list (so order is consistent for gallery + lightbox).

Optional: add CLIP tags locally if --clip-checkpoint is provided.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

from PIL import Image, ImageOps

# -----------------------------
# Defaults
# -----------------------------
THUMB_MAX_WIDTH = 300
JPEG_QUALITY = 85

DEFAULT_TAGS = [
    "nature", "landscape", "cityscape", "architecture", "street", "interior",
    "night", "sunset", "sunrise", "seascape", "mountains", "forest", "waterfall",
    "beach", "river", "lake", "garden", "flowers", "macro",
    "people", "portrait", "wildlife", "bird", "cat", "dog",
    "archaeology", "ruins", "museum", "statue", "church", "castle",
    "black and white", "minimalism", "abstract",
]

TEMPLATES = [
    "a photo of {tag}",
    "a photograph of {tag}",
    "{tag}",
]

# -----------------------------
# Orientation helpers
# -----------------------------
def get_orientation(path: str) -> str:
    """
    Returns 'portrait' if height > width AFTER EXIF transpose,
    else 'landscape'. (Square treated as landscape)
    """
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            return "portrait" if img.height > img.width else "landscape"
    except Exception:
        # If unreadable, don't push it to the end
        return "landscape"


def create_thumbnail(source_path: str, thumb_path: str, max_width: int, jpeg_quality: int) -> None:
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)

    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)

        if img.width > max_width:
            scale = max_width / float(img.width)
            new_w = max_width
            new_h = int(img.height * scale)
        else:
            new_w, new_h = img.width, img.height

        img = img.resize((new_w, new_h), Image.LANCZOS)

        ext = os.path.splitext(thumb_path)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            img = img.convert("RGB")
            img.save(thumb_path, "JPEG", quality=jpeg_quality, optimize=True)
        elif ext == ".png":
            img.save(thumb_path, "PNG", optimize=True)
        else:
            img = img.convert("RGB")
            img.save(thumb_path, "JPEG", quality=jpeg_quality, optimize=True)

# -----------------------------
# Tagging (OpenCLIP) - optional
# -----------------------------
@dataclass
class ClipBundle:
    model: "torch.nn.Module"
    preprocess: object
    tokenizer: object


def load_tags(path: str | None) -> List[str]:
    if not path:
        return DEFAULT_TAGS
    tags: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if not t or t.startswith("#"):
                continue
            tags.append(t)
    if not tags:
        raise ValueError(f"No tags found in {path}")
    return tags


def safe_torch_load(checkpoint_path: str, device: str):
    import torch
    # PyTorch 2.6+ changed default weights_only; be explicit.
    try:
        return torch.load(checkpoint_path, map_location=device, weights_only=False)  # type: ignore[arg-type]
    except TypeError:
        return torch.load(checkpoint_path, map_location=device)


def load_clip(model_name: str, pretrained: str | None, checkpoint_path: str, device: str) -> ClipBundle:
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name,
        pretrained=pretrained,
        device=device,
    )

    sd = safe_torch_load(checkpoint_path, device)
    if isinstance(sd, dict) and "state_dict" in sd:
        sd = sd["state_dict"]

    missing, unexpected = model.load_state_dict(sd, strict=False)
    if missing:
        print(f"[warn] Missing keys when loading checkpoint: {len(missing)}")
    if unexpected:
        print(f"[warn] Unexpected keys when loading checkpoint: {len(unexpected)}")

    tokenizer = open_clip.get_tokenizer(model_name)
    model.eval()
    return ClipBundle(model=model, preprocess=preprocess, tokenizer=tokenizer)


def build_text_features(bundle: ClipBundle, tags: List[str], device: str):
    import torch

    all_prompts: List[str] = []
    slices: List[slice] = []

    start = 0
    for tag in tags:
        prompts = [tpl.format(tag=tag) for tpl in TEMPLATES]
        all_prompts.extend(prompts)
        slices.append(slice(start, start + len(prompts)))
        start += len(prompts)

    tokens = bundle.tokenizer(all_prompts).to(device)
    text_features = bundle.model.encode_text(tokens)
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    per_tag: List[torch.Tensor] = []
    for s in slices:
        v = text_features[s].mean(dim=0)
        v = v / v.norm()
        per_tag.append(v)

    return torch.stack(per_tag, dim=0)


def predict_tags_for_image(bundle: ClipBundle, image_path: str, tag_names: List[str], tag_features, topk: int, device: str) -> List[str]:
    import torch

    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    image_input = bundle.preprocess(img).unsqueeze(0).to(device)

    with torch.inference_mode():
        image_features = bundle.model.encode_image(image_input)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        sims = (image_features @ tag_features.T).squeeze(0)
        _, top_idx = torch.topk(sims, k=min(topk, sims.shape[0]))

    return [tag_names[i] for i in top_idx.tolist()]


# -----------------------------
# Build JSON (PORTRAIT LAST)
# -----------------------------
def build_json(base_dir: str, photography_dir: str, thumbnails_dir: str, output_json: str, thumb_max_width: int, jpeg_quality: int) -> Dict:
    if not os.path.exists(photography_dir):
        raise FileNotFoundError(f"Photography directory not found: {photography_dir}")

    data: Dict = {"years": []}

    for year in sorted(os.listdir(photography_dir)):
        year_path = os.path.join(photography_dir, year)
        if not os.path.isdir(year_path):
            continue

        year_data = {"year": year, "events": []}

        for event in sorted(os.listdir(year_path)):
            event_path = os.path.join(year_path, event)
            if not os.path.isdir(event_path):
                continue

            thumb_event_path = os.path.join(thumbnails_dir, year, event)

            # Keep a stable base ordering by filename
            filenames = sorted(
                [f for f in os.listdir(event_path) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            )

            # ✅ Partition by orientation (EXIF-correct)
            landscape_files: List[str] = []
            portrait_files: List[str] = []

            for fname in filenames:
                full_path = os.path.join(event_path, fname)
                o = get_orientation(full_path)
                if o == "portrait":
                    portrait_files.append(fname)
                else:
                    landscape_files.append(fname)

            # ✅ GUARANTEE: portraits are last in this city/event
            ordered = landscape_files + portrait_files

            images_out: List[Dict] = []
            for fname in ordered:
                full_path = os.path.join(event_path, fname)
                thumb_path = os.path.join(thumb_event_path, fname)

                if not os.path.exists(thumb_path):
                    create_thumbnail(full_path, thumb_path, thumb_max_width, jpeg_quality)

                images_out.append(
                    {
                        "thumb": os.path.relpath(thumb_path, base_dir).replace("\\", "/"),
                        "full": os.path.relpath(full_path, base_dir).replace("\\", "/"),
                        "orientation": get_orientation(full_path),
                    }
                )

            year_data["events"].append({"name": event, "images": images_out})

        data["years"].append(year_data)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"✅ Thumbnails generated & photography.json created! → {output_json}")
    return data


def tag_json_in_place(data: Dict, base_dir: str, image_root: str, model: str, pretrained: str | None, checkpoint: str, tags_file: str | None, topk: int, device: str) -> None:
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        print("[warn] CUDA not available; falling back to CPU")
        device = "cpu"
    if device == "mps" and not torch.backends.mps.is_available():
        print("[warn] MPS not available; falling back to CPU")
        device = "cpu"

    try:
        import open_clip  # noqa: F401
    except ImportError as e:
        raise SystemExit("Missing dependency: open_clip_torch\nInstall: pip install open_clip_torch\n") from e

    tag_names = [t.strip().lower() for t in load_tags(tags_file)]
    bundle = load_clip(model, pretrained, checkpoint, device)
    tag_features = build_text_features(bundle, tag_names, device)

    try:
        from tqdm import tqdm  # type: ignore
    except ImportError:
        def tqdm(x, **_): return x

    num_tagged = 0
    for year in data.get("years", []):
        for event in year.get("events", []):
            for img in tqdm(event.get("images", []), desc=f"Tagging {year.get('year','')}/{event.get('name','')}", unit="img"):
                full_rel = img.get("full")
                if not isinstance(full_rel, str):
                    continue

                full_path = os.path.join(image_root, full_rel)
                if not os.path.exists(full_path):
                    alt = os.path.join(base_dir, full_rel)
                    if os.path.exists(alt):
                        full_path = alt
                    else:
                        continue

                try:
                    img["tags"] = predict_tags_for_image(bundle, full_path, tag_names, tag_features, topk, device)
                    num_tagged += 1
                except Exception as e:
                    print(f"[warn] Failed tagging {full_rel}: {e}")

    print(f"✅ Tagged {num_tagged} images")


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument("--photography-dir", default="photography")
    parser.add_argument("--thumbnails-dir", default="thumbnails")
    parser.add_argument("--output-json", default="photography.json")
    parser.add_argument("--thumb-max-width", type=int, default=THUMB_MAX_WIDTH)
    parser.add_argument("--jpeg-quality", type=int, default=JPEG_QUALITY)

    # Optional tagging
    parser.add_argument("--clip-checkpoint", default=None)
    parser.add_argument("--tags", default=None)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--model", default="ViT-B-32")
    parser.add_argument("--pretrained", default=None)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"])
    parser.add_argument("--image-root", default=".")

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    photography_dir = os.path.join(base_dir, args.photography_dir)
    thumbnails_dir = os.path.join(base_dir, args.thumbnails_dir)
    output_json = os.path.join(base_dir, args.output_json)

    data = build_json(
        base_dir=base_dir,
        photography_dir=photography_dir,
        thumbnails_dir=thumbnails_dir,
        output_json=output_json,
        thumb_max_width=args.thumb_max_width,
        jpeg_quality=args.jpeg_quality,
    )

    if args.clip_checkpoint:
        checkpoint = args.clip_checkpoint
        if not os.path.isabs(checkpoint):
            checkpoint = os.path.join(base_dir, checkpoint)

        tag_json_in_place(
            data=data,
            base_dir=base_dir,
            image_root=args.image_root,
            model=args.model,
            pretrained=args.pretrained,
            checkpoint=checkpoint,
            tags_file=args.tags,
            topk=args.topk,
            device=args.device,
        )

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"✅ Updated JSON (with tags) saved → {output_json}")
    else:
        print("ℹ️  Tagging skipped (no --clip-checkpoint provided).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#python .\build_gallery.py --clip-checkpoint "site\models\vit_b_32-quickgelu-laion400m_e32-46683a32.pt" --model "ViT-B-32-quickgelu" --device cpu
