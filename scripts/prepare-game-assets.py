"""Deterministic preparation of reusable game sprites from the approved asset sheets.

This script performs extraction only: it crops an approved sheet region, trims to the
visible alpha bounds, adds a small transparent pad, and verifies the edges. It never
synthesises or repaints artwork. Every output is recorded in the manifest with the
source hash, the exact crop box, the output hash and the measured alpha edge quality, so
prepared files can be reproduced byte-for-byte from the approved source sheets.

Preview artefacts are written next to the manifest:

* ``<name>-checker.png``  the sprite on a checkerboard, to expose transparency and halos
* ``<name>-scene.png``    the sprite at interaction size over its approved scene
* ``<name>-edge.png``     a 3x magnification of the four corners, to inspect cut edges
* ``<group>-contact.png`` every sprite of one group on a single reviewable sheet

Usage (from the repository root):
    .venv/Scripts/python.exe scripts/prepare-game-assets.py [--only memory] [--no-previews]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "output" / "visual-design-review-2026-10-19"
OUT_DIR = ROOT / "frontend" / "src" / "redesign" / "games" / "assets" / "prepared"
MANIFEST = ROOT / "output" / "verification" / "ui-rebuild" / "games" / "asset-manifest.json"
PREVIEW_DIR = ROOT / "output" / "verification" / "ui-rebuild" / "games" / "asset-previews"

ALPHA_TRIM = 8
ALPHA_EDGE = 12
PAD = 10
# Any material on the outer ring means the crop crossed artwork, so the gate is zero.
EDGE_WARN = 0.0

CHECKER_LIGHT = (246, 247, 249, 255)
CHECKER_DARK = (214, 220, 228, 255)
CHECKER_STEP = 16


@dataclass(frozen=True)
class Spec:
    """One extracted sprite: approved sheet, crop region and intended consumer."""

    sheet: str
    group: str
    name: str
    crop: tuple[int, int, int, int]
    consumers: tuple[str, ...]


# Approved scenes used to preview each group at interaction size.
SCENES = {
    "planning": "38-scene-garden.png",
    "memory": "34-scene-grove.png",
    "reasoning": "35-scene-atelier.png",
    "attention": "36-scene-harbor.png",
    "flexibility": "37-scene-gallery.png",
    "hybrid": "36-scene-harbor.png",
}

# Approved art that is referenced by the accepted scope but is not present in the approved
# library. These are recorded rather than invented: a missing sprite stays visibly absent
# (or is replaced by native geometry) until human-approved artwork exists.
MISSING: list[dict[str, str]] = [
    {
        "name": "hybrid-tide-dial",
        "group": "hybrid",
        "needed_by": "HY-02 Tidekeeper (frontend/src/redesign/hybrid/HybridPage.tsx)",
        "reason": "The approved library has boats, a buoy and crates (sheet 31) but no tide gauge or dial artwork.",
        "handling": "Native SVG dial geometry until human-approved artwork is supplied; no replacement is generated.",
    },
    {
        "name": "hybrid-market-goods",
        "group": "hybrid",
        "needed_by": "HY-03 Market of Changing Rules (frontend/src/redesign/hybrid/HybridPage.tsx)",
        "reason": "Sheet 30 supplies envelopes, parcels, keys and medallions but no market stall or tradable goods set.",
        "handling": "Approved parcel, envelope and medallion objects stand in as counters; no artwork is generated.",
    },
    {
        "name": "memory-tile-stack",
        "group": "memory",
        "needed_by": "Memory M4 perspective slab (frontend/src/redesign/games/MemoryGame.tsx)",
        "reason": "Sheet 28 supplies single slabs; no pre-rendered perspective stack exists in the approved library.",
        "handling": "Composed with a native CSS perspective transform over the extracted slab sprite.",
    },
]

# (sheet, group, name, crop box, consumers) - crop boxes are the empty-space gaps between
# approved objects, so no shadow, glow or ivy leaf is clipped by an arbitrary tight box.
SPECS: list[Spec] = [
    Spec("16-assets-planning.png", "planning", "planning-paver-1", (0, 0, 466, 407), ("frontend/src/redesign/games/PlanningGame.tsx",)),
    Spec("16-assets-planning.png", "planning", "planning-paver-2", (466, 0, 896, 407), ("frontend/src/redesign/games/PlanningGame.tsx",)),
    Spec("16-assets-planning.png", "planning", "planning-paver-3", (896, 0, 1297, 407), ("frontend/src/redesign/games/PlanningGame.tsx",)),
    Spec("16-assets-planning.png", "planning", "planning-paver-4", (1297, 0, 1774, 407), ("frontend/src/redesign/games/PlanningGame.tsx",)),
    Spec("16-assets-planning.png", "planning", "planning-boulder-1", (0, 407, 466, 887), ("frontend/src/redesign/games/PlanningGame.tsx",)),
    Spec("16-assets-planning.png", "planning", "planning-boulder-2", (466, 407, 896, 887), ("frontend/src/redesign/games/PlanningGame.tsx",)),
    Spec("16-assets-planning.png", "planning", "planning-pawn", (896, 407, 1297, 887), ("frontend/src/redesign/games/PlanningGame.tsx",)),
    Spec("16-assets-planning.png", "planning", "planning-portal", (1297, 407, 1774, 887), ("frontend/src/redesign/games/PlanningGame.tsx",)),
    # Memory: sheet 28 repeats the six objects of sheet 17 with cleaner cut edges, so the
    # clean-cutout sheet is the extraction source and sheet 17 stays the presentation reference.
    Spec("28-memory-clean-cutouts.png", "memory", "memory-tile-plain", (40, 20, 530, 482), ("frontend/src/redesign/games/MemoryGame.tsx",)),
    Spec("28-memory-clean-cutouts.png", "memory", "memory-tile-gold", (515, 20, 1015, 482), ("frontend/src/redesign/games/MemoryGame.tsx",)),
    Spec("28-memory-clean-cutouts.png", "memory", "memory-tile-teal", (1000, 20, 1500, 482), ("frontend/src/redesign/games/MemoryGame.tsx",)),
    Spec("28-memory-clean-cutouts.png", "memory", "memory-ivy-corner", (20, 478, 535, 1010), ("frontend/src/redesign/games/MemoryGame.tsx",)),
    Spec("28-memory-clean-cutouts.png", "memory", "memory-lantern", (610, 478, 930, 1020), ("frontend/src/redesign/games/MemoryGame.tsx",)),
    Spec("28-memory-clean-cutouts.png", "memory", "memory-flower-rock", (1010, 478, 1525, 1010), ("frontend/src/redesign/games/MemoryGame.tsx",)),
    # Reasoning: sheet 29 is the clean-edge repeat of sheet 18.
    Spec("29-reasoning-clean-cutouts.png", "reasoning", "reasoning-plaque-square", (20, 30, 465, 495), ("frontend/src/redesign/games/ReasoningGame.tsx",)),
    # The plaque row ends at y=423 and the slab row below starts at y=502, so the crop must
    # stop inside that empty band: y=505 used to slice six pixels off the slab below.
    Spec("29-reasoning-clean-cutouts.png", "reasoning", "reasoning-plaque-wide", (485, 20, 1110, 498), ("frontend/src/redesign/games/ReasoningGame.tsx",)),
    Spec("29-reasoning-clean-cutouts.png", "reasoning", "reasoning-crystal-blue", (1200, 20, 1470, 505), ("frontend/src/redesign/games/ReasoningGame.tsx",)),
    Spec("29-reasoning-clean-cutouts.png", "reasoning", "reasoning-crystal-amber", (85, 480, 365, 980), ("frontend/src/redesign/games/ReasoningGame.tsx",)),
    # The bracket ends at x=819 and the floating slab starts at x=842, so the empty band is
    # 820-841: x=845 used to pick up nine pixels of the slab's left edge.
    Spec("29-reasoning-clean-cutouts.png", "reasoning", "reasoning-bracket", (455, 480, 838, 1005), ("frontend/src/redesign/games/ReasoningGame.tsx",)),
    Spec("29-reasoning-clean-cutouts.png", "reasoning", "reasoning-slab", (820, 480, 1536, 1005), ("frontend/src/redesign/games/ReasoningGame.tsx",)),
    Spec("39-crystal-cutout.png", "reasoning", "reasoning-crystal-cutout", (430, 175, 845, 1080), ("frontend/src/redesign/games/ReasoningGame.tsx",)),
    Spec("19-assets-attention.png", "attention", "attention-porthole", (95, 0, 700, 514), ("frontend/src/redesign/games/AttentionGame.tsx",)),
    Spec("19-assets-attention.png", "attention", "attention-dais", (785, 180, 1435, 520), ("frontend/src/redesign/games/AttentionGame.tsx",)),
    Spec("19-assets-attention.png", "attention", "attention-lighthouse", (120, 514, 690, 1045), ("frontend/src/redesign/games/AttentionGame.tsx",)),
    Spec("19-assets-attention.png", "attention", "attention-railing", (780, 520, 1475, 1040), ("frontend/src/redesign/games/AttentionGame.tsx",)),
    Spec("20-assets-flexibility.png", "flexibility", "flexibility-plaque-a", (40, 45, 465, 475), ("frontend/src/redesign/games/FlexibilityGame.tsx",)),
    Spec("20-assets-flexibility.png", "flexibility", "flexibility-plaque-b", (540, 50, 955, 477), ("frontend/src/redesign/games/FlexibilityGame.tsx",)),
    Spec("20-assets-flexibility.png", "flexibility", "flexibility-plaque-wide", (985, 85, 1742, 455), ("frontend/src/redesign/games/FlexibilityGame.tsx",)),
    Spec("20-assets-flexibility.png", "flexibility", "flexibility-token-blue-round", (75, 473, 430, 830), ("frontend/src/redesign/games/FlexibilityGame.tsx",)),
    Spec("20-assets-flexibility.png", "flexibility", "flexibility-token-red-square", (590, 478, 932, 818), ("frontend/src/redesign/games/FlexibilityGame.tsx",)),
    Spec("20-assets-flexibility.png", "flexibility", "flexibility-token-blue-square", (1195, 478, 1540, 818), ("frontend/src/redesign/games/FlexibilityGame.tsx",)),
    # Hybrid object library (sheet 30) and harbor/bridge library (sheet 31) for HY-02..HY-06.
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-envelope", (0, 10, 375, 372), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-parcel", (368, 10, 730, 372), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-key", (735, 10, 1062, 372), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-mailbox", (1092, 0, 1425, 375), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-bell", (30, 360, 305, 715), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-gate", (345, 360, 745, 715), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-tablet", (725, 370, 1088, 715), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-tablet-envelope", (1075, 372, 1440, 715), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-medallion-lantern", (5, 700, 368, 1050), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-medallion-leaf", (365, 700, 715, 1050), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-medallion-crystal", (720, 700, 1066, 1050), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("30-assets-hybrid-objects.png", "hybrid", "hybrid-tray", (1060, 705, 1448, 1035), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-boat-blue", (50, 0, 368, 372), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-boat-red", (410, 0, 730, 372), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-crate", (775, 80, 1046, 368), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-buoy", (1145, 15, 1395, 370), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-bridge-straight", (0, 370, 392, 712), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-bridge-bend", (392, 372, 726, 728), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-bridge-junction", (730, 375, 1072, 720), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-gate", (1100, 382, 1448, 700), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-flag-blue", (60, 705, 345, 1065), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    # The bend bridge above ends at y=705 and the flag starts at y=728, so the crop must
    # start inside that band: y=705 used to include four faint pixels of the bridge.
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-flag-ivory", (420, 720, 705, 1065), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-plaque", (725, 720, 1075, 1058), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
    Spec("31-assets-harbor-bridges.png", "hybrid", "harbor-ribbon", (1080, 735, 1448, 1040), ("frontend/src/redesign/hybrid/HybridPage.tsx",)),
]

# Sheets that were reviewed and deliberately not extracted into new sprites.
ALTERNATES = [
    {
        "sheet": "17-assets-memory.png",
        "relation": "Presentation repeat of sheet 28 (same six objects).",
        "decision": "Extraction source is 28-memory-clean-cutouts.png; sheet 17 stays unmodified as the approved presentation reference.",
    },
    {
        "sheet": "18-assets-reasoning.png",
        "relation": "Presentation repeat of sheet 29 (same six objects).",
        "decision": "Extraction source is 29-reasoning-clean-cutouts.png; sheet 18 stays unmodified as the approved presentation reference.",
    },
    {
        "sheet": "21-assets-shared.png",
        "relation": "Shared world medallions for Home and Insights.",
        "decision": "Already delivered as frontend/public/art/adventure/world-*.png plus game-landscape; not re-extracted in this batch.",
    },
    {
        "sheet": "32 and 33",
        "relation": "Rejected by the human.",
        "decision": "Excluded from the library and never referenced.",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def edge_report(sprite: Image.Image) -> dict[str, float]:
    """Measure how much non-transparent material touches the outer ring.

    The outer ring of a finished sprite is the pad plus transparent margin, so any
    material there means the crop crossed neighbouring artwork or a baked backdrop.
    Counts are reported alongside the fractions so a small ring is still quotable.
    """
    alpha = sprite.getchannel("A")
    width, height = sprite.size
    ring = []
    for x in range(width):
        ring.extend((alpha.getpixel((x, 0)), alpha.getpixel((x, height - 1))))
    for y in range(height):
        ring.extend((alpha.getpixel((0, y)), alpha.getpixel((width - 1, y))))
    solid = sum(1 for value in ring if value > ALPHA_EDGE)
    soft = sum(1 for value in ring if ALPHA_TRIM < value <= 254)
    return {
        "ring_opaque_fraction": round(solid / len(ring), 4),
        "ring_soft_fraction": round(soft / len(ring), 4),
        "ring_opaque_pixels": solid,
        "ring_pixels": len(ring),
    }


def crop_edge_report(crop: Image.Image) -> dict[str, int]:
    """Material on the requested crop boundary, measured before trimming.

    A non-zero value here is the extraction defect itself: the crop box cut through
    artwork instead of stopping in the empty gap between objects.
    """
    alpha = crop.getchannel("A")
    width, height = crop.size
    hits = 0
    peak = 0
    for x in range(width):
        for y in (0, height - 1):
            value = alpha.getpixel((x, y))
            if value > ALPHA_EDGE:
                hits += 1
                peak = max(peak, value)
    for y in range(height):
        for x in (0, width - 1):
            value = alpha.getpixel((x, y))
            if value > ALPHA_EDGE:
                hits += 1
                peak = max(peak, value)
    return {"crop_edge_pixels": hits, "crop_edge_peak_alpha": peak}


def checkerboard(size: tuple[int, int], step: int = CHECKER_STEP) -> Image.Image:
    board = Image.new("RGBA", size, CHECKER_LIGHT)
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2 == 0:
                draw.rectangle([x, y, x + step - 1, y + step - 1], fill=CHECKER_DARK)
    return board


def fit(sprite: Image.Image, box: tuple[int, int]) -> Image.Image:
    scale = min(box[0] / sprite.width, box[1] / sprite.height, 1.0)
    return sprite.resize((max(1, int(sprite.width * scale)), max(1, int(sprite.height * scale))), Image.LANCZOS)


def write_previews(name: str, group: str, sprite: Image.Image) -> dict[str, str]:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    tile = (320, 240)
    paths: dict[str, str] = {}

    checker = checkerboard(tile)
    placed = fit(sprite, (tile[0] - 24, tile[1] - 24))
    checker.alpha_composite(placed, ((tile[0] - placed.width) // 2, (tile[1] - placed.height) // 2))
    checker_path = PREVIEW_DIR / f"{name}-checker.png"
    checker.convert("RGB").save(checker_path, optimize=True)
    paths["checker"] = str(checker_path.relative_to(ROOT)).replace("\\", "/")

    scene_name = SCENES.get(group)
    if scene_name:
        scene_source = SOURCE_DIR / scene_name
        if scene_source.exists():
            with Image.open(scene_source) as opened:
                scene = opened.convert("RGBA").resize((640, 400), Image.LANCZOS)
            placed = fit(sprite, (300, 260))
            scene.alpha_composite(placed, ((640 - placed.width) // 2, (400 - placed.height) // 2))
            scene_path = PREVIEW_DIR / f"{name}-scene.png"
            scene.convert("RGB").save(scene_path, optimize=True)
            paths["scene"] = str(scene_path.relative_to(ROOT)).replace("\\", "/")

    band = min(72, sprite.width // 3, sprite.height // 3)
    corners = [
        (0, 0, band, band),
        (sprite.width - band, 0, sprite.width, band),
        (0, sprite.height - band, band, sprite.height),
        (sprite.width - band, sprite.height - band, sprite.width, sprite.height),
    ]
    zoom = 3
    edge = checkerboard((band * zoom * 2 + 12, band * zoom * 2 + 12), step=12)
    for index, box in enumerate(corners):
        piece = sprite.crop(box).resize((band * zoom, band * zoom), Image.LANCZOS)
        edge.alpha_composite(piece, (6 + (index % 2) * band * zoom, 6 + (index // 2) * band * zoom))
    edge_path = PREVIEW_DIR / f"{name}-edge.png"
    edge.convert("RGB").save(edge_path, optimize=True)
    paths["edge"] = str(edge_path.relative_to(ROOT)).replace("\\", "/")
    return paths


def prepare(spec: Spec) -> dict:
    source = SOURCE_DIR / spec.sheet
    if not source.exists():
        raise SystemExit(f"missing approved source sheet: {source}")
    with Image.open(source) as opened:
        crop = opened.convert("RGBA").crop(spec.crop)
    bounds = crop.getchannel("A").point(lambda value: 255 if value > ALPHA_TRIM else 0).getbbox()
    if bounds is None:
        raise SystemExit(f"{spec.name}: crop region contains no visible pixels")
    left = max(0, bounds[0] - PAD)
    top = max(0, bounds[1] - PAD)
    right = min(crop.width, bounds[2] + PAD)
    bottom = min(crop.height, bounds[3] + PAD)
    sprite = crop.crop((left, top, right, bottom))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / f"{spec.name}.png"
    sprite.save(target, format="PNG", optimize=True)
    alpha = sprite.getchannel("A")
    histogram = alpha.histogram()
    total = sprite.width * sprite.height
    return {
        "name": spec.name,
        "group": spec.group,
        "source": spec.sheet,
        "source_sha256": sha256(source),
        "crop_box": list(spec.crop),
        "trimmed_box": [left + spec.crop[0], top + spec.crop[1], right + spec.crop[0], bottom + spec.crop[1]],
        "output": str(target.relative_to(ROOT)).replace("\\", "/"),
        "output_sha256": sha256(target),
        "size": [sprite.width, sprite.height],
        "alpha0_fraction": round(histogram[0] / total, 4),
        "consumers": list(spec.consumers),
        **crop_edge_report(crop),
        **edge_report(sprite),
    }


def contact_sheet(group: str, entries: list[dict]) -> str | None:
    sprites = [entry for entry in entries if entry["group"] == group]
    if not sprites:
        return None
    cell = (330, 250)
    columns = 4
    rows = (len(sprites) + columns - 1) // columns
    sheet = checkerboard((columns * cell[0], rows * cell[1]), step=20)
    draw = ImageDraw.Draw(sheet)
    for index, entry in enumerate(sprites):
        with Image.open(ROOT / entry["output"]) as opened:
            sprite = opened.convert("RGBA")
        placed = fit(sprite, (cell[0] - 30, cell[1] - 60))
        x = (index % columns) * cell[0] + (cell[0] - placed.width) // 2
        y = (index // columns) * cell[1] + 14
        sheet.alpha_composite(placed, (x, y))
        origin_x = (index % columns) * cell[0]
        origin_y = (index // columns) * cell[1]
        draw.rectangle([origin_x + 4, origin_y + 4, origin_x + cell[0] - 4, origin_y + cell[1] - 4], outline=(150, 158, 170, 255))
        draw.text((origin_x + 10, origin_y + cell[1] - 26), entry["name"], fill=(20, 24, 32, 255))
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    sheet_path = PREVIEW_DIR / f"{group}-contact.png"
    sheet.convert("RGB").save(sheet_path, optimize=True)
    return str(sheet_path.relative_to(ROOT)).replace("\\", "/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None, help="restrict to one asset group")
    parser.add_argument("--no-previews", action="store_true", help="skip preview artefacts")
    args = parser.parse_args()

    selected = [spec for spec in SPECS if args.only in (None, spec.group)]
    entries = [prepare(spec) for spec in selected]
    if not args.no_previews:
        for entry in entries:
            with Image.open(ROOT / entry["output"]) as opened:
                entry["previews"] = write_previews(entry["name"], entry["group"], opened.convert("RGBA"))

    loaded = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    existing = {item["name"]: item for item in loaded.get("assets", [])}
    for entry in entries:
        existing[entry["name"]] = entry
    groups = sorted({item["group"] for item in existing.values()})
    contacts: dict[str, str] = {}
    if not args.no_previews:
        for group in groups:
            written = contact_sheet(group, list(existing.values()))
            if written:
                contacts[group] = written

    counts_by_group = {group: sum(1 for item in existing.values() if item["group"] == group) for group in groups}
    preview_paths = [path for item in existing.values() for path in item.get("previews", {}).values()]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(
            {
                "generated_by": "scripts/prepare-game-assets.py",
                "policy": "Extraction only. Approved source sheets are never modified and no artwork is generated.",
                "source_dir": str(SOURCE_DIR.relative_to(ROOT)).replace("\\", "/"),
                "asset_count": len(existing),
                "counts_by_group": counts_by_group,
                "preview_count": len(preview_paths),
                "contact_sheet_count": len(contacts),
                "consumers_note": "The consumers field lists intended modules. Only the planning sprites and the memory tile surfaces are imported by a module today.",
                "contact_sheets": contacts,
                "assets": list(existing.values()),
                "alternates_reviewed": ALTERNATES,
                "missing": MISSING,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    warned = False
    for entry in entries:
        flag = ""
        if entry["ring_opaque_fraction"] > EDGE_WARN or entry["crop_edge_pixels"] > 0:
            flag = "  <-- EDGE WARNING: crop crossed artwork"
            warned = True
        print(
            f"{entry['name']:<28} {entry['size'][0]:>4}x{entry['size'][1]:<4} "
            f"alpha0={entry['alpha0_fraction']:<7} ring={entry['ring_opaque_fraction']:<7} "
            f"ring_px={entry['ring_opaque_pixels']:<4} soft={entry['ring_soft_fraction']:<7} "
            f"crop_edge={entry['crop_edge_pixels']}{flag}"
        )
    print(f"\n{len(entries)} sprite(s) written to {OUT_DIR.relative_to(ROOT)}; manifest at {MANIFEST.relative_to(ROOT)}")
    print(f"manifest total assets: {len(existing)} across groups: {', '.join(f'{name} {count}' for name, count in counts_by_group.items())}")
    print(f"previews: {len(preview_paths)} per-asset files, {len(contacts)} group contact sheets")
    return 1 if warned else 0


if __name__ == "__main__":
    sys.exit(main())
