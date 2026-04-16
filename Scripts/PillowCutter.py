from PIL import Image
from pathlib import Path

INPUT = Path(r"C:\Users\juani\Documents\MHBG\TTS_Extract\kushala_assets\cortar\armfront.jpg")
OUTPUT_DIR = INPUT.parent / (INPUT.stem + "_cards")
OUTPUT_DIR.mkdir(exist_ok=True)

COLS = 3
ROWS = 2

img = Image.open(INPUT)
width, height = img.size

card_w = width // COLS
card_h = height // ROWS

counter = 1

for row in range(ROWS):
    for col in range(COLS):
        left = col * card_w
        top = row * card_h
        right = left + card_w
        bottom = top + card_h

        card = img.crop((left, top, right, bottom))

        out_file = OUTPUT_DIR / f"card_{counter:02d}.png"
        card.save(out_file)
        print("Guardada:", out_file)

        counter += 1