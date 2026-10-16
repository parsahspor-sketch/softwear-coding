import io
import struct
from pathlib import Path

from PIL import Image, ImageChops


ICON_FILE = Path(__file__).with_name("QuietHoursMonitor.ico")
SOURCE_FILE = Path(__file__).with_name("QuietHoursLogo.png")
TRANSPARENT_LOGO_FILE = Path(__file__).with_name("QuietHoursLogoTransparent.png")
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def create_transparent_logo():
    with Image.open(SOURCE_FILE) as source:
        logo = source.convert("RGBA")
    red, green, blue, _ = logo.split()
    brightness = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    alpha = brightness.point(
        lambda value: round(max(0, min(1, (value - 48) / 44)) * 255)
    )
    logo.putalpha(alpha)

    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError(f"No visible logo artwork found in {SOURCE_FILE}.")
    left, top, right, bottom = bounds
    padding = round(max(right - left, bottom - top) * 0.06)
    crop_bounds = (
        max(0, left - padding),
        max(0, top - padding),
        min(logo.width, right + padding),
        min(logo.height, bottom + padding),
    )
    logo = logo.crop(crop_bounds)
    logo.save(TRANSPARENT_LOGO_FILE, optimize=True)
    return logo


def encode_ico(images):
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    image_data = bytearray()
    image_offset = 6 + 16 * len(images)
    for size, image in images.items():
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                0 if size == 256 else size,
                0 if size == 256 else size,
                0,
                0,
                1,
                32,
                len(image),
                image_offset,
            )
        )
        image_data.extend(image)
        image_offset += len(image)
    return bytes(directory + image_data)


def render_icon_images(logo):
    images = {}
    for size in ICON_SIZES:
        resized = logo.resize((size, size), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        resized.save(buffer, format="PNG", optimize=True)
        images[size] = buffer.getvalue()
    return images


if __name__ == "__main__":
    logo = create_transparent_logo()
    ICON_FILE.write_bytes(encode_ico(render_icon_images(logo)))
    print(f"Created {TRANSPARENT_LOGO_FILE}")
    print(f"Created {ICON_FILE}")
