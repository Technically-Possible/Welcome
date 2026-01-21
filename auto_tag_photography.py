#!/usr/bin/env python3
"""Auto-tag photos in photography.json with 3 simple, human-ish tags.

Goal
----
- Runs *locally* (no API calls).
- Adds a `tags` field to each image entry in photography.json, e.g.
    {"thumb": "...", "full": "...", "tags": ["nature", "landscape", "sunset"]}

How it works
------------
Uses an open-source CLIP model locally to score your images against a
*fixed list of candidate tags* (nature, landscape, archaeology, etc.), then
chooses the top N tags per image.

Important note about "no external services"
------------------------------------------
This script will NOT download model weights by itself.
You must provide a local CLIP checkpoint file via --clip-checkpoint.
(You can download the checkpoint manually once and then run fully offline.)

Example
-------
python auto_tag_photography.py \
  --json photography.json \
  --image-root . \
  --clip-checkpoint models/open_clip_vit_b32_laion2b_s34b_b79k.pt

Tip: create a `models/` folder at the repo root and keep your checkpoint there.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

from PIL import Image

import torch

try:
    import open_clip
except ImportError as e:
    raise SystemExit(
        "Missing dependency: open_clip_torch\n\n"
        "Install with: pip install open_clip_torch\n"
    ) from e


DEFAULT_TAGS = [
    # Broad scene tags
    "nature",
    "landscape",
    "cityscape",
    "architecture",
    "street",
    "interior",
    "night",
    "sunset",
    "sunrise",
    "seascape",
    "mountains",
    "forest",
    "waterfall",
    "beach",
    "river",
    "lake",
    "garden",
    "flowers",
    "macro",

    # Subjects
    "people",
    "portrait",
    "wildlife",
    "bird",
    "cat",
    "dog",

    # Culture / history
    "archaeology",
    "ruins",
    "museum",
    "statue",
    "church",
    "castle",

    # Mood / style
    "black and white",
    "minimalism",
    "abstract",
]


TEMPLATES = [
    "a photo of {tag}",
    "a photograph of {tag}",
    "{tag}",
]


@dataclass
class ClipBundle:
    model: torch.nn.Module
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


def load_clip(model_name: str, pretrained: str | None, checkpoint_path: str, device: str) -> ClipBundle:
    # Create model skeleton (no weight download)
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name,
        pretrained=pretrained,
        device=device,
    )

    # Load weights from local file
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            f"CLIP checkpoint not found: {checkpoint_path}\n\n"
            "Download a checkpoint manually and pass it with --clip-checkpoint."
        )

    sd = torch.load(checkpoint_path, map_location=device)
    # Many checkpoints store {'state_dict': ...}
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


@torch.inference_mode()
def build_text_features(bundle: ClipBundle, tags: List[str], device: str) -> Tuple[List[str], torch.Tensor]:
    """Returns (tags, features) where features is [num_tags, dim], normalized."""
    all_prompts: List[str] = []
    tag_slices: List[slice] = []

    start = 0
    for tag in tags:
        prompts = [tpl.format(tag=tag) for tpl in TEMPLATES]
        all_prompts.extend(prompts)
        tag_slices.append(slice(start, start + len(prompts)))
        start += len(prompts)

    tokens = bundle.tokenizer(all_prompts).to(device)
    text_features = bundle.model.encode_text(tokens)
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    # Average template prompts per tag
    per_tag: List[torch.Tensor] = []
    for s in tag_slices:
        v = text_features[s].mean(dim=0)
        v = v / v.norm()
        per_tag.append(v)

    return tags, torch.stack(per_tag, dim=0)


@torch.inference_mode()
def predict_tags_for_image(
    bundle: ClipBundle,
    image_path: str,
    tag_names: List[str],
    tag_features: torch.Tensor,
    topk: int,
    device: str,
) -> List[str]:
    img = Image.open(image_path).convert("RGB")
    image_input = bundle.preprocess(img).unsqueeze(0).to(device)

    image_features = bundle.model.encode_image(image_input)
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)

    # cosine similarity
    sims = (image_features @ tag_features.T).squeeze(0)
    top_vals, top_idx = torch.topk(sims, k=min(topk, sims.shape[0]))

    out = []
    for i in top_idx.tolist():
        out.append(tag_names[i])
    return out


def iter_images(json_data: Dict) -> List[Tuple[Dict, str]]:
    """Return list of (image_obj, full_rel_path) references."""
    out: List[Tuple[Dict, str]] = []
    for year in json_data.get("years", []):
        for event in year.get("events", []):
            for img in event.get("images", []):
                full = img.get("full")
                if isinstance(full, str):
                    out.append((img, full))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-tag images in photography.json using local CLIP.")
    parser.add_argument("--json", default="photography.json", help="Path to photography.json")
    parser.add_argument(
        "--image-root",
        default=".",
        help="Root folder used to resolve each image's `full` path (default: repo root).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: overwrite input --json).",
    )
    parser.add_argument("--tags", default=None, help="Optional text file with one tag per line.")
    parser.add_argument("--topk", type=int, default=3, help="Number of tags per image (default: 3)")

    parser.add_argument(
        "--model",
        default="ViT-B-32",
        help="OpenCLIP model architecture name (default: ViT-B-32)",
    )
    parser.add_argument(
        "--pretrained",
        default=None,
        help=(
            "OpenCLIP pretrained identifier (leave empty when you provide a checkpoint). "
            "Example: laion2b_s34b_b79k"
        ),
    )
    parser.add_argument(
        "--clip-checkpoint",
        required=True,
        help="Path to a local CLIP checkpoint (.pt) file. Script will not download weights.",
    )

    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "mps"],
        help="Device to run on (default: cpu)",
    )

    args = parser.parse_args()

    json_path = args.json
    out_path = args.output or json_path

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tags = load_tags(args.tags)

    # Device handling
    device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        print("[warn] CUDA not available; falling back to CPU")
        device = "cpu"
    if device == "mps" and not torch.backends.mps.is_available():
        print("[warn] MPS not available; falling back to CPU")
        device = "cpu"

    bundle = load_clip(args.model, args.pretrained, args.clip_checkpoint, device)
    tag_names, tag_features = build_text_features(bundle, [t.lower() for t in tags], device)

    images = iter_images(data)
    if not images:
        print("No images found in the JSON.")
        return 0

    # Tag each image
    try:
        from tqdm import tqdm  # type: ignore
    except ImportError:
        def tqdm(x, **_):
            return x

    num_tagged = 0
    num_missing = 0

    for img_obj, full_rel in tqdm(images, desc="Tagging", unit="img"):
        full_path = os.path.join(args.image_root, full_rel)
        if not os.path.exists(full_path):
            num_missing += 1
            continue

        try:
            pred = predict_tags_for_image(
                bundle=bundle,
                image_path=full_path,
                tag_names=tag_names,
                tag_features=tag_features,
                topk=args.topk,
                device=device,
            )
        except Exception as e:
            print(f"[warn] Failed tagging {full_rel}: {e}")
            continue

        img_obj["tags"] = pred
        num_tagged += 1

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"✅ Tagged {num_tagged} images → {out_path}")
    if num_missing:
        print(
            f"⚠️  Skipped {num_missing} images because the file wasn't found.\n"
            "    Check --image-root and that your `full` paths point to real files."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
