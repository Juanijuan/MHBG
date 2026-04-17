import argparse
from pathlib import Path

from PIL import Image


INPUT = Path("sheet.png")
COLS = 3
ROWS = 2


def cut_image_sheet(input_path: Path, cols: int, rows: int, output_dir: Path | None = None) -> list[Path]:
    if cols <= 0 or rows <= 0:
        raise ValueError("Rows and columns must be greater than zero.")
    if not input_path.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")

    output_dir = output_dir or (input_path.parent / f"{input_path.stem}_cards")
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as image:
        width, height = image.size
        card_width = width // cols
        card_height = height // rows

        created_files = []
        counter = 1

        for row in range(rows):
            for col in range(cols):
                left = col * card_width
                top = row * card_height
                right = left + card_width
                bottom = top + card_height

                card = image.crop((left, top, right, bottom))
                out_file = output_dir / f"card_{counter:02d}.png"
                card.save(out_file)
                created_files.append(out_file)
                print(f"Saved: {out_file}")
                counter += 1

    print(f"\nTotal cards generated: {len(created_files)}")
    print(f"Output: {output_dir}")
    return created_files


def parse_args():
    parser = argparse.ArgumentParser(
        description="Cut a sheet image into a fixed grid."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT,
        help="Path to the image to cut.",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=COLS,
        help="Number of columns.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=ROWS,
        help="Number of rows.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output folder. Defaults to <image>_cards.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cut_image_sheet(
        input_path=args.input,
        cols=args.cols,
        rows=args.rows,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
