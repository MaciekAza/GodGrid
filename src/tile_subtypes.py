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
}


def resolve_subtype(mapa, x: int, y: int) -> str:
    return mapa[y][x]


def build_subtype_map(mapa):
    return [[resolve_subtype(mapa, x, y) for x in range(len(mapa[0]))] for y in range(len(mapa))]


def refresh_subtypes_around(mapa, subtype_map, changed_tiles, radius: int = 1):
    if not changed_tiles:
        return

    h = len(mapa)
    w = len(mapa[0])
    min_x = max(0, min(x for x, _ in changed_tiles) - radius)
    max_x = min(w - 1, max(x for x, _ in changed_tiles) + radius)
    min_y = max(0, min(y for _, y in changed_tiles) - radius)
    max_y = min(h - 1, max(y for _, y in changed_tiles) + radius)

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            subtype_map[y][x] = resolve_subtype(mapa, x, y)


def tile_draw_color(tile_id: str, subtype_id: str, fallback_colors):
    return SUBTYPE_COLORS.get(subtype_id, fallback_colors.get(tile_id, (255, 0, 255)))
