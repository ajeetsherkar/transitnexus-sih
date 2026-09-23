from pathlib import Path
from collections import Counter

ROOT = Path.home() / "Downloads" / "Multi-Weather Pothole Detection (MWPD)" / "MWPD"


def audit(split):
    c = Counter()
    image_dir = ROOT / split / "images"
    label_dir = ROOT / split / "labels"

    for im in sorted(image_dir.glob("*.*")):
        c["images"] += 1
        lab = label_dir / f"{im.stem}.txt"

        if not lab.exists():
            c["no_label_file"] += 1
            continue

        rows = [
            line.split()
            for line in lab.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        if not rows:
            c["empty_label_background"] += 1
            continue

        for p in rows:
            if len(p) != 5:
                c["not_5_values"] += 1
                continue

            cls = p[0]
            try:
                x, y, w, h = map(float, p[1:5])
            except ValueError:
                c["non_numeric_values"] += 1
                continue

            c["boxes"] += 1
            c["class_not_0"] += cls != "0"
            c["out_of_range"] += not (
                0 <= x <= 1
                and 0 <= y <= 1
                and 0 < w <= 1
                and 0 < h <= 1
            )
            c["tiny_box"] += w * h < 0.0005

    return c


def source(name):
    return name.split(".rf.")[0]


train_src = {
    source(p.name)
    for p in (ROOT / "train" / "images").glob("*.*")
}

print(f"Dataset root: {ROOT}")
print()

for split in ("train", "valid", "test"):
    print(split, dict(audit(split)))

print()

for split in ("valid", "test"):
    split_src = {
        source(p.name)
        for p in (ROOT / split / "images").glob("*.*")
    }
    shared = train_src & split_src
    print(
        f"{split} images sharing a source with train: {len(shared)}"
    )

    if shared:
        print("  WARNING: potential source leakage detected")
        for item in sorted(shared)[:20]:
            print(f"  - {item}")
