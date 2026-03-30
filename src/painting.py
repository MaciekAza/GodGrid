brush_offsets_cache = {}


def screen_to_tile(mouse_x, mouse_y, camera_x, camera_y, tile_draw_size, map_width, map_height):
    if tile_draw_size <= 0:
        return None

    tile_x = int((mouse_x - camera_x) / tile_draw_size)
    tile_y = int((mouse_y - camera_y) / tile_draw_size)

    if 0 <= tile_x < map_width and 0 <= tile_y < map_height:
        return tile_x, tile_y
    return None


def get_brush_offsets(brush_size):
    if brush_size in brush_offsets_cache:
        return brush_offsets_cache[brush_size]

    radius = max(0.5, brush_size / 2.0)
    start = int(-radius) - 1
    end = int(radius) + 1
    offsets = []
    for dy in range(start, end + 1):
        for dx in range(start, end + 1):
            if dx * dx + dy * dy <= radius * radius:
                offsets.append((dx, dy))

    brush_offsets_cache[brush_size] = offsets
    return offsets


def apply_brush(mapa, tile_pos, tile_id, brush_size):
    x, y = tile_pos
    map_height = len(mapa)
    map_width = len(mapa[0])
    offsets = get_brush_offsets(brush_size)

    for dx, dy in offsets:
        xx = x + dx
        yy = y + dy
        if 0 <= xx < map_width and 0 <= yy < map_height:
            mapa[yy][xx] = tile_id


def apply_brush_line(mapa, start_tile, end_tile, tile_id, brush_size):
    start_x, start_y = start_tile
    end_x, end_y = end_tile

    dx = end_x - start_x
    dy = end_y - start_y
    steps = max(abs(dx), abs(dy))

    if steps == 0:
        apply_brush(mapa, start_tile, tile_id, brush_size)
        return

    for i in range(1, steps + 1):
        ix = round(start_x + (dx * i) / steps)
        iy = round(start_y + (dy * i) / steps)
        apply_brush(mapa, (ix, iy), tile_id, brush_size)
