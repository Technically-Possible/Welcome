import os
import json
from PIL import Image

PHOTOGRAPHY_DIR = "photography"
THUMBNAIL_DIR = "thumbnails"
THUMB_MAX_WIDTH = 300  # Max width for thumbnails (keeps original aspect ratio)
JPEG_QUALITY = 85  # Compression quality (lower = smaller file size)

def create_thumbnail(source_path, thumb_path):
    """ Generate a thumbnail with the same aspect ratio but reduced width. """
    if not os.path.exists(os.path.dirname(thumb_path)):
        os.makedirs(os.path.dirname(thumb_path))

    with Image.open(source_path) as img:
        # Calculate new size while keeping aspect ratio
        width_percent = THUMB_MAX_WIDTH / float(img.size[0])
        new_height = int(float(img.size[1]) * width_percent)

        # Resize and save thumbnail
        img = img.resize((THUMB_MAX_WIDTH, new_height), Image.LANCZOS)
        img.save(thumb_path, "JPEG", quality=JPEG_QUALITY)

def generate_json():
    """ Scan the photography folder, generate thumbnails, and create photography.json """
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

                            # Generate thumbnail if it doesn't exist
                            if not os.path.exists(thumb_image_path):
                                create_thumbnail(full_image_path, thumb_image_path)

                            event_data["images"].append({
                                "thumb": f"{thumb_event_path}/{image}",
                                "full": f"{event_path}/{image}"
                            })

                    year_data["events"].append(event_data)

            data["years"].append(year_data)

    with open("photography.json", "w") as json_file:
        json.dump(data, json_file, indent=4)

if __name__ == "__main__":
    generate_json()
    print("✅ Thumbnails generated & photography.json created!")
