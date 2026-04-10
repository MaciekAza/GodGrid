from __future__ import annotations


# Explicit terrain palette used by rendering and game logic.
# No hidden conversion for water/mountains - what is on the map is what the game reads.
SUBTYPE_COLORS = {
    "grass": (50, 200, 50),
    "forest": (20, 120, 20),
    "water": (50, 50, 200),
    "deep_ocean": (18, 36, 125),
    "highland": (108, 134, 88),
    "mountain_high": (122, 122, 122),
    "mountain_peak": (198, 198, 198),
    "coal_ore": (70, 70, 78),
    "iron_ore": (153, 122, 92),
    "copper_ore": (178, 102, 62),
    "clay": (154, 112, 92),
    "gold_ore": (216, 172, 36),
}

# Per-type shade multipliers used for temporary color variants.
# This is also the place to define target variant counts once tile assets are split into folders.
SUBTYPE_SHADE_VARIANTS = {
    "grass": (0.97, 1.00, 1.03),
    "forest": (0.96, 1.00, 1.03),
    "water": (0.97, 1.00, 1.02),
    "deep_ocean": (0.98, 1.00, 1.02),
    "highland": (0.97, 1.00, 1.03),
    "mountain_high": (0.96, 1.00, 1.03),
    "mountain_peak": (0.98, 1.00, 1.02),
    "coal_ore": (0.98, 1.00, 1.02),
    "iron_ore": (0.98, 1.00, 1.03),
    "copper_ore": (0.98, 1.00, 1.03),
    "clay": (0.98, 1.00, 1.02),
    "gold_ore": (0.99, 1.00, 1.02),
}


def _hash_tile_variant(x: int, y: int, subtype_id: str) -> int:
    # Deterministic tile hash so visual variants stay stable between frames.
    h = 2166136261
    for ch in subtype_id:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    h ^= x * 374761393
    h ^= y * 668265263
    h = (h ^ (h >> 13)) * 1274126177
    h ^= h >> 16
    return h & 0xFFFFFFFF


def tile_variant_index(x: int, y: int, subtype_id: str, variant_count: int) -> int:
    if variant_count <= 1:
        return 0
    return _hash_tile_variant(x, y, subtype_id) % variant_count


def _shade_color(color, factor: float):
    r, g, b = color
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
    )


def resolve_subtype(mapa, x: int, y: int) -> str:
    return mapa[y][x]


def _bounds_around_changed(mapa, changed_tiles, radius: int):
    h = len(mapa)
    w = len(mapa[0])
    min_x = max(0, min(x for x, _ in changed_tiles) - radius)
    max_x = min(w - 1, max(x for x, _ in changed_tiles) + radius)
    min_y = max(0, min(y for _, y in changed_tiles) - radius)
    max_y = min(h - 1, max(y for _, y in changed_tiles) + radius)
    return min_x, max_x, min_y, max_y


def build_subtype_map(mapa):
    return [[resolve_subtype(mapa, x, y) for x in range(len(mapa[0]))] for y in range(len(mapa))]


def refresh_subtypes_around(mapa, subtype_map, changed_tiles, radius: int = 1):
    if not changed_tiles:
        return

    min_x, max_x, min_y, max_y = _bounds_around_changed(mapa, changed_tiles, radius)

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            subtype_map[y][x] = resolve_subtype(mapa, x, y)


def tile_draw_color(tile_id: str, subtype_id: str, fallback_colors, x: int, y: int):
    base = SUBTYPE_COLORS.get(subtype_id, fallback_colors.get(tile_id, (255, 0, 255)))
    shades = SUBTYPE_SHADE_VARIANTS.get(subtype_id)
    if not shades:
        return base

    variant = tile_variant_index(x, y, subtype_id, len(shades))
    return _shade_color(base, shades[variant])


def build_color_map(mapa, subtype_map, fallback_colors):
    h = len(mapa)
    w = len(mapa[0])
    color_map = [[(0, 0, 0)] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            tile_id = mapa[y][x]
            subtype_id = subtype_map[y][x]
            color_map[y][x] = tile_draw_color(tile_id, subtype_id, fallback_colors, x, y)
    return color_map


def refresh_colors_around(mapa, subtype_map, color_map, changed_tiles, fallback_colors, radius: int = 1):
    if not changed_tiles:
        return

    min_x, max_x, min_y, max_y = _bounds_around_changed(mapa, changed_tiles, radius)

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            tile_id = mapa[y][x]
            subtype_id = subtype_map[y][x]
            color_map[y][x] = tile_draw_color(tile_id, subtype_id, fallback_colors, x, y)
