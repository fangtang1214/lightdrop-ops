from pathlib import Path

from PIL import Image


def compute_dhash(path: str | Path, hash_size: int = 8) -> str:
    with Image.open(path) as image:
        return compute_dhash_from_image(image, hash_size=hash_size)


def compute_dhash_from_image(image: Image.Image, hash_size: int = 8) -> str:
    prepared = image.convert("L").resize(
        (hash_size + 1, hash_size),
        Image.Resampling.LANCZOS,
    )
    pixels = list(prepared.getdata())

    value = 0
    for row in range(hash_size):
        row_start = row * (hash_size + 1)
        for col in range(hash_size):
            left = pixels[row_start + col]
            right = pixels[row_start + col + 1]
            value = (value << 1) | int(left > right)

    return f"{value:0{hash_size * hash_size // 4}x}"


def hamming_distance(hash_a: str | None, hash_b: str | None) -> int:
    if not hash_a or not hash_b:
        return 65
    return (int(hash_a, 16) ^ int(hash_b, 16)).bit_count()
