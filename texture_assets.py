from __future__ import annotations

from math import ceil, sin
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw


TEXTURE_SIZE = 16
TEXTURE_DIR = Path(__file__).resolve().parent / "assets" / "textures"
ATLAS_COLUMNS = 4
ATLAS_ROWS = ceil(12 / ATLAS_COLUMNS)
ATLAS_PATH = TEXTURE_DIR / "blocks_atlas.png"
TEXTURE_NAMES = (
    "grass_top",
    "grass_side",
    "dirt",
    "stone",
    "sand",
    "log_side",
    "log_top",
    "planks",
    "leaves",
    "glass",
    "water",
    "bedrock",
)


def _clamp(value: int) -> int:
    return max(0, min(255, value))


def _jitter(rgb: tuple[int, int, int], rng: Random, amount: int) -> tuple[int, int, int]:
    return tuple(_clamp(channel + rng.randint(-amount, amount)) for channel in rgb)


def _noise_tile(
    base: tuple[int, int, int],
    seed: int,
    amount: int,
    alpha: int = 255,
) -> Image.Image:
    rng = Random(seed)
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE))
    pixels = image.load()

    for y in range(TEXTURE_SIZE):
        for x in range(TEXTURE_SIZE):
            pixels[x, y] = (*_jitter(base, rng, amount), alpha)

    return image


def _grass_top() -> Image.Image:
    rng = Random(11)
    image = _noise_tile((84, 156, 75), 12, 18)
    draw = ImageDraw.Draw(image)

    for _ in range(34):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        blade_color = rng.choice(((55, 127, 58), (68, 148, 63), (104, 175, 76), (43, 109, 49)))
        draw.rectangle(
            (x, y, min(TEXTURE_SIZE - 1, x + rng.choice((0, 1))), min(TEXTURE_SIZE - 1, y + rng.choice((0, 1)))),
            fill=(*_jitter(blade_color, rng, 8), 255),
        )

    for _ in range(10):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        draw.point((x, y), fill=(*_jitter((136, 190, 84), rng, 12), 255))

    return image


def _grass_side() -> Image.Image:
    image = _dirt()
    draw = ImageDraw.Draw(image)
    rng = Random(13)

    for y in range(0, 4):
        for x in range(TEXTURE_SIZE):
            green = rng.choice(((62, 143, 60), (75, 166, 67), (94, 184, 75), (48, 122, 52)))
            draw.point((x, y), fill=(*_jitter(green, rng, 7), 255))

    for x in range(0, TEXTURE_SIZE, 2):
        drop = rng.randrange(1, 4)
        green = _jitter((57, 132, 55), rng, 8)
        draw.line((x, 3, x, min(TEXTURE_SIZE - 1, 3 + drop)), fill=(*green, 255))

    return image


def _dirt() -> Image.Image:
    rng = Random(22)
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE), (111, 72, 45, 255))
    draw = ImageDraw.Draw(image)

    layer_colors = (
        (92, 58, 38),
        (126, 80, 47),
        (103, 66, 43),
        (145, 94, 53),
        (82, 54, 38),
    )
    y = 0
    while y < TEXTURE_SIZE:
        height = rng.randrange(2, 5)
        base = _jitter(layer_colors[(y // 5) % len(layer_colors)], rng, 7)
        draw.rectangle((0, y, TEXTURE_SIZE, min(TEXTURE_SIZE, y + height)), fill=(*base, 255))
        for x in range(0, TEXTURE_SIZE, rng.randrange(3, 6)):
            draw.line(
                (x, y + height - 1, min(TEXTURE_SIZE, x + rng.randrange(2, 5)), y + height - 1),
                fill=(*_jitter((68, 44, 33), rng, 5), 255),
            )
        y += height

    for _ in range(18):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        radius = rng.choice((0, 1, 1))
        pebble = _jitter(rng.choice(((73, 52, 40), (158, 111, 67), (96, 66, 45))), rng, 8)
        draw.rectangle(
            (x, y, min(TEXTURE_SIZE - 1, x + radius), min(TEXTURE_SIZE - 1, y + radius)),
            fill=(*pebble, 255),
        )

    for _ in range(5):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(5, TEXTURE_SIZE - 3)
        length = rng.randrange(3, 7)
        root = _jitter((54, 39, 30), rng, 5)
        draw.line((x, y, min(TEXTURE_SIZE - 1, x + length), y + rng.choice((-1, 0, 1))), fill=(*root, 255))

    return image


def _stone() -> Image.Image:
    rng = Random(33)
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE), (112, 116, 120, 255))
    draw = ImageDraw.Draw(image)

    slabs = (
        (0, 0, 6, 4, (128, 132, 135)),
        (6, 0, 15, 5, (99, 103, 108)),
        (0, 5, 4, 10, (105, 110, 114)),
        (4, 5, 11, 11, (136, 139, 141)),
        (11, 5, 15, 10, (91, 96, 102)),
        (0, 11, 7, 15, (121, 124, 128)),
        (7, 11, 15, 15, (106, 110, 116)),
    )
    for left, top, right, bottom, base in slabs:
        fill = _jitter(base, rng, 8)
        draw.rectangle((left, top, right, bottom), fill=(*fill, 255))
        draw.line((left, bottom, right, bottom), fill=(67, 71, 78, 255))
        draw.line((right, top, right, bottom), fill=(75, 79, 84, 255))
        draw.line((left, top, right, top), fill=(153, 156, 158, 255))

    crack_paths = (
        ((3, 0), (4, 3), (4, 6), (6, 8)),
        ((10, 2), (9, 5), (11, 8), (10, 11), (12, 14)),
        ((2, 13), (5, 12), (7, 14), (10, 13)),
    )
    for points in crack_paths:
        draw.line(points, fill=(55, 58, 64, 255), width=1)

    for _ in range(10):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        if rng.random() < 0.6:
            draw.point((x, y), fill=(*_jitter((164, 166, 168), rng, 7), 255))
        else:
            draw.point((x, y), fill=(*_jitter((75, 78, 84), rng, 7), 255))

    return image


def _sand() -> Image.Image:
    rng = Random(44)
    image = _noise_tile((205, 190, 126), 45, 16)
    draw = ImageDraw.Draw(image)

    for _ in range(42):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        grain = rng.choice(((177, 157, 96), (232, 219, 151), (194, 174, 112)))
        draw.point((x, y), fill=(*_jitter(grain, rng, 8), 255))

    return image


def _log_side() -> Image.Image:
    rng = Random(55)
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE), (122, 78, 40, 255))
    draw = ImageDraw.Draw(image)

    for x in range(TEXTURE_SIZE):
        band = int(14 * sin(x * 0.7) + 8 * sin(x * 1.7))
        tone = _clamp(118 + band + rng.randint(-5, 5))
        draw.line((x, 0, x, TEXTURE_SIZE), fill=(tone, _clamp(77 + band // 2), 38, 255))

    for _ in range(4):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        draw.ellipse((x - 3, y - 1, x + 4, y + 2), outline=(78, 49, 27, 255))

    return image


def _log_top() -> Image.Image:
    rng = Random(56)
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE), (152, 108, 63, 255))
    draw = ImageDraw.Draw(image)
    center = TEXTURE_SIZE // 2

    for radius, shade in ((7, (97, 61, 35)), (5, (180, 132, 76)), (3, (129, 82, 43)), (1, (194, 147, 86))):
        offset = rng.choice((-1, 0, 1))
        draw.ellipse(
            (center - radius + offset, center - radius, center + radius + offset, center + radius),
            outline=(*_jitter(shade, rng, 6), 255),
        )

    for _ in range(18):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        draw.point((x, y), fill=(*_jitter((160, 111, 64), rng, 18), 255))

    return image


def _planks() -> Image.Image:
    rng = Random(57)
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE), (150, 98, 48, 255))
    draw = ImageDraw.Draw(image)

    for y in (0, 5, 10, 15):
        draw.line((0, y, TEXTURE_SIZE - 1, y), fill=(82, 51, 28, 255))

    for row, y0 in enumerate((0, 5, 10)):
        offset = 0 if row % 2 == 0 else 8
        for x in (offset, offset + 8):
            draw.line((x, y0, x, min(TEXTURE_SIZE - 1, y0 + 5)), fill=(96, 59, 31, 255))

    for _ in range(35):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        shade = rng.choice(((126, 76, 37), (178, 118, 58), (104, 63, 33)))
        draw.point((x, y), fill=(*_jitter(shade, rng, 8), 255))

    return image


def _leaves() -> Image.Image:
    rng = Random(66)
    image = _noise_tile((56, 138, 62), 67, 24)
    draw = ImageDraw.Draw(image)

    for _ in range(44):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        leaf = _jitter(rng.choice(((45, 111, 48), (83, 163, 72), (65, 146, 58))), rng, 13)
        draw.rectangle((x, y, min(TEXTURE_SIZE - 1, x + 1), min(TEXTURE_SIZE - 1, y + 1)), fill=(*leaf, 255))

    return image


def _glass() -> Image.Image:
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE), (154, 219, 238, 72))
    draw = ImageDraw.Draw(image)
    edge = (219, 249, 255, 150)
    shine = (244, 255, 255, 190)
    shade = (80, 165, 190, 95)

    draw.rectangle((0, 0, TEXTURE_SIZE - 1, TEXTURE_SIZE - 1), outline=edge, width=1)
    draw.line((3, 1, 1, 3), fill=shine)
    draw.line((7, 1, 1, 7), fill=shine)
    draw.line((14, 8, 8, 14), fill=shade)
    draw.line((14, 12, 12, 14), fill=shade)

    return image


def _water() -> Image.Image:
    rng = Random(77)
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE), (44, 111, 197, 132))
    draw = ImageDraw.Draw(image)

    for y in range(2, TEXTURE_SIZE, 4):
        points = []
        for x in range(-2, TEXTURE_SIZE + 3):
            wave = y + int(2 * sin((x + y) * 0.55))
            points.append((x, wave))
        draw.line(points, fill=(106, 178, 235, 130), width=1)

    for _ in range(12):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        draw.point((x, y), fill=(150, 212, 249, 120))

    return image


def _bedrock() -> Image.Image:
    rng = Random(88)
    image = _noise_tile((38, 38, 44), 89, 18)
    draw = ImageDraw.Draw(image)

    for _ in range(22):
        x = rng.randrange(TEXTURE_SIZE)
        y = rng.randrange(TEXTURE_SIZE)
        size = rng.choice((1, 2, 3))
        patch = _jitter(rng.choice(((22, 22, 27), (62, 62, 71), (48, 46, 55))), rng, 8)
        draw.rectangle((x, y, min(TEXTURE_SIZE - 1, x + size), min(TEXTURE_SIZE - 1, y + size)), fill=(*patch, 255))

    return image


BUILDERS = {
    "grass_top": _grass_top,
    "grass_side": _grass_side,
    "dirt": _dirt,
    "stone": _stone,
    "sand": _sand,
    "log_side": _log_side,
    "log_top": _log_top,
    "planks": _planks,
    "leaves": _leaves,
    "glass": _glass,
    "water": _water,
    "bedrock": _bedrock,
}


def ensure_texture_assets(force: bool = False) -> list[Path]:
    TEXTURE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name in TEXTURE_NAMES:
        path = TEXTURE_DIR / f"{name}.png"
        if path.exists() and not force:
            continue
        BUILDERS[name]().save(path)
        written.append(path)

    return written


def ensure_texture_atlas(force: bool = False) -> Path:
    ensure_texture_assets(force=force)
    if ATLAS_PATH.exists() and not force:
        return ATLAS_PATH

    atlas = Image.new(
        "RGBA",
        (ATLAS_COLUMNS * TEXTURE_SIZE, ATLAS_ROWS * TEXTURE_SIZE),
        (0, 0, 0, 0),
    )

    for index, name in enumerate(TEXTURE_NAMES):
        source = Image.open(TEXTURE_DIR / f"{name}.png").convert("RGBA")
        col = index % ATLAS_COLUMNS
        row = index // ATLAS_COLUMNS
        atlas.paste(source, (col * TEXTURE_SIZE, row * TEXTURE_SIZE))

    atlas.save(ATLAS_PATH)
    return ATLAS_PATH


if __name__ == "__main__":
    created = ensure_texture_assets(force=True)
    atlas_path = ensure_texture_atlas(force=True)
    for texture in created:
        print(texture)
    print(atlas_path)
