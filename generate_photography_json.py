import os
import json
from PIL import Image

# Base directory where the script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define absolute paths
PHOTOGRAPHY_DIR = os.path.join(BASE_DIR, "photography")
THUMBNAIL_DIR = os.path.join(BASE_DIR, "thumbnails")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "photography.json")

THUMB_MAX_WIDTH = 300  # Max width for thumbnails
JPEG_QUALITY = 85  # JPEG compression quality


def create_thumbnail(source_path, thumb_path):
    """ Generate a thumbnail with the same aspect ratio but reduced width. """
    if not os.path.exists(os.path.dirname(thumb_path)):
        os.makedirs(os.path.dirname(thumb_path))

    with Image.open(source_path) as img:
        width_percent = THUMB_MAX_WIDTH / float(img.size[0])
        new_height = int(float(img.size[1]) * width_percent)

        img = img.resize((THUMB_MAX_WIDTH, new_height), Image.LANCZOS)
        img.save(thumb_path, "JPEG", quality=JPEG_QUALITY)


def generate_json():
    """ Scan the photography folder, generate thumbnails, and create photography.json """
    if not os.path.exists(PHOTOGRAPHY_DIR):
        raise FileNotFoundError(f"🚫 Photography directory not found: {PHOTOGRAPHY_DIR}")

    data = {"years": []}

    for year in sorted(os.listdir(PHOTOGRAPHY_DIR)):
        year_path = os.path.join(PHOTOGRAPHY_DIR, year)
        if os.path.isdir(year_path):
            year_data = {"year": year, "events": []}

            for event in sorted(os.listdir(year_path)):
                event_path = os.path.join(year_path, event)
                thumb_event_path = os.path.join(THUMBNAIL_DIR, year, event)

                if os.path.isdir(event_path):
                    event_data = {"name": event, "images": []}

                    for image in sorted(os.listdir(event_path)):
                        if image.lower().endswith((".jpg", ".jpeg", ".png")):
                            full_image_path = os.path.join(event_path, image)
                            thumb_image_path = os.path.join(thumb_event_path, image)

                            if not os.path.exists(thumb_image_path):
                                create_thumbnail(full_image_path, thumb_image_path)

                            event_data["images"].append({
                                "thumb": os.path.relpath(thumb_image_path, BASE_DIR).replace("\\", "/"),
                                "full": os.path.relpath(full_image_path, BASE_DIR).replace("\\", "/")
                            })

                    year_data["events"].append(event_data)

            data["years"].append(year_data)

    with open(OUTPUT_JSON_PATH, "w") as json_file:
        json.dump(data, json_file, indent=4)

    print("✅ Thumbnails generated & photography.json created!")


if __name__ == "__main__":
    generate_json()
