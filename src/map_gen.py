from __future__ import annotations

import argparse
import os
import random
from collections import deque
from dataclasses import dataclass


MIN_WORLD_SIZE = 20
MAX_WORLD_SIZE = 300


@dataclass
class WorldConfig:
    width: int = 100
    height: int = 100
    seed: int = 0
    sea_level: float = 0.52
    mountain_strength: float = 0.55
    climate_bias: float = 0.0
    chunk_size: int = 64


def recommended_chunk_size(width: int, height: int) -> int:
    max_dim = max(width, height)
    if max_dim <= 200:
        return 32
    return 64


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _hash01(ix: int, iy: int, seed: int) -> float:
    n = ix * 374761393 + iy * 668265263 + seed * 144269
    n = (n ^ (n >> 13)) * 1274126177
    n = n ^ (n >> 16)
    return (n & 0xFFFFFFFF) / 4294967295.0


def _value_noise(x: float, y: float, seed: int) -> float:
    x0 = int(x)
    y0 = int(y)
    x1 = x0 + 1
    y1 = y0 + 1

    tx = x - x0
    ty = y - y0
    sx = _smoothstep(tx)
    sy = _smoothstep(ty)

    v00 = _hash01(x0, y0, seed)
    v10 = _hash01(x1, y0, seed)
    v01 = _hash01(x0, y1, seed)
    v11 = _hash01(x1, y1, seed)

    nx0 = _lerp(v00, v10, sx)
    nx1 = _lerp(v01, v11, sx)
    return _lerp(nx0, nx1, sy)


def _validate_config(config: WorldConfig) -> WorldConfig:
    if not (MIN_WORLD_SIZE <= config.width <= MAX_WORLD_SIZE):
        raise ValueError(f"width must be in range {MIN_WORLD_SIZE}-{MAX_WORLD_SIZE}")
    if not (MIN_WORLD_SIZE <= config.height <= MAX_WORLD_SIZE):
        raise ValueError(f"height must be in range {MIN_WORLD_SIZE}-{MAX_WORLD_SIZE}")

    config.sea_level = _clamp(config.sea_level, 0.30, 0.75)
    config.mountain_strength = _clamp(config.mountain_strength, 0.0, 1.0)
    config.climate_bias = _clamp(config.climate_bias, -1.0, 1.0)
    config.chunk_size = max(16, min(256, int(config.chunk_size)))
    return config


def _estimate_sea_threshold(elevation_map, sea_level: float) -> float:
    histogram = [0] * 256
    total = 0
    for row in elevation_map:
        for value in row:
            idx = int(_clamp(value, 0.0, 1.0) * 255.0)
            histogram[idx] += 1
            total += 1

    target = int(total * sea_level)
    running = 0
    for idx, count in enumerate(histogram):
        running += count
        if running >= target:
            return idx / 255.0
    return sea_level


def _build_water_prefix_sum(water_mask):
    h = len(water_mask)
    w = len(water_mask[0])
    prefix = [[0] * (w + 1) for _ in range(h + 1)]
    for y in range(h):
        running = 0
        for x in range(w):
            running += 1 if water_mask[y][x] else 0
            prefix[y + 1][x + 1] = prefix[y][x + 1] + running
    return prefix


def _water_cells_in_rect(prefix, x0: int, y0: int, x1: int, y1: int) -> int:
    return prefix[y1 + 1][x1 + 1] - prefix[y0][x1 + 1] - prefix[y1 + 1][x0] + prefix[y0][x0]


def _nearby_water_ratio(prefix, width: int, height: int, x: int, y: int, radius: int) -> float:
    x0 = max(0, x - radius)
    y0 = max(0, y - radius)
    x1 = min(width - 1, x + radius)
    y1 = min(height - 1, y + radius)
    total = (x1 - x0 + 1) * (y1 - y0 + 1) - 1
    if total <= 0:
        return 0.0
    water = _water_cells_in_rect(prefix, x0, y0, x1, y1)
    return _clamp(water / total, 0.0, 1.0)


def _generation_profile(width: int, height: int):
    area = width * height
    if area <= 30_000:
        return {"coast_radius": 2, "refine_passes": 2, "refine_stride": 1}
    if area <= 65_000:
        return {"coast_radius": 2, "refine_passes": 1, "refine_stride": 1}
    return {"coast_radius": 1, "refine_passes": 1, "refine_stride": 2}


def _refine_biomes(map_chars, water_mask, passes: int, stride: int):
    if passes <= 0:
        return map_chars

    h = len(map_chars)
    w = len(map_chars[0])
    result = map_chars

    for iteration in range(passes):
        updated = [row[:] for row in result]
        offset = iteration % max(1, stride)

        for y in range(1 + offset, h - 1, stride):
            for x in range(1 + offset, w - 1, stride):
                if water_mask[y][x]:
                    continue

                counts = {"W": 0, "G": 0, "F": 0, "M": 0}
                for yy in range(y - 1, y + 2):
                    for xx in range(x - 1, x + 2):
                        if xx == x and yy == y:
                            continue
                        counts[result[yy][xx]] += 1

                tile = result[y][x]
                if tile == "M" and counts["M"] <= 1:
                    updated[y][x] = "G" if counts["G"] >= counts["F"] else "F"
                elif tile in ("G", "F"):
                    if counts["W"] >= 6:
                        updated[y][x] = "W"
                    elif counts["F"] >= 6:
                        updated[y][x] = "F"
                    elif counts["G"] >= 6:
                        updated[y][x] = "G"

        result = updated

    return result


def _distance_from_land(water_mask):
    h = len(water_mask)
    w = len(water_mask[0])
    dist = [[-1] * w for _ in range(h)]
    q = deque()

    for y in range(h):
        for x in range(w):
            if not water_mask[y][x]:
                dist[y][x] = 0
                q.append((x, y))

    if not q:
        for x in range(w):
            dist[0][x] = 0
            dist[h - 1][x] = 0
            q.append((x, 0))
            q.append((x, h - 1))
        for y in range(h):
            dist[y][0] = 0
            dist[y][w - 1] = 0
            q.append((0, y))
            q.append((w - 1, y))

    while q:
        x, y = q.popleft()
        base = dist[y][x]
        if x > 0 and dist[y][x - 1] < 0:
            dist[y][x - 1] = base + 1
            q.append((x - 1, y))
        if x + 1 < w and dist[y][x + 1] < 0:
            dist[y][x + 1] = base + 1
            q.append((x + 1, y))
        if y > 0 and dist[y - 1][x] < 0:
            dist[y - 1][x] = base + 1
            q.append((x, y - 1))
        if y + 1 < h and dist[y + 1][x] < 0:
            dist[y + 1][x] = base + 1
            q.append((x, y + 1))

    return dist


def _distance_from_non_mountain(mountain_mask):
    h = len(mountain_mask)
    w = len(mountain_mask[0])
    dist = [[-1] * w for _ in range(h)]
    q = deque()

    for y in range(h):
        for x in range(w):
            if not mountain_mask[y][x]:
                dist[y][x] = 0
                q.append((x, y))

    if not q:
        for x in range(w):
            dist[0][x] = 0
            dist[h - 1][x] = 0
            q.append((x, 0))
            q.append((x, h - 1))
        for y in range(h):
            dist[y][0] = 0
            dist[y][w - 1] = 0
            q.append((0, y))
            q.append((w - 1, y))

    while q:
        x, y = q.popleft()
        base = dist[y][x]
        if x > 0 and dist[y][x - 1] < 0:
            dist[y][x - 1] = base + 1
            q.append((x - 1, y))
        if x + 1 < w and dist[y][x + 1] < 0:
            dist[y][x + 1] = base + 1
            q.append((x + 1, y))
        if y > 0 and dist[y - 1][x] < 0:
            dist[y - 1][x] = base + 1
            q.append((x, y - 1))
        if y + 1 < h and dist[y + 1][x] < 0:
            dist[y + 1][x] = base + 1
            q.append((x, y + 1))

    return dist


def _distance_to_water(water_mask):
    h = len(water_mask)
    w = len(water_mask[0])
    dist = [[-1] * w for _ in range(h)]
    q = deque()

    for y in range(h):
        for x in range(w):
            if water_mask[y][x]:
                dist[y][x] = 0
                q.append((x, y))

    while q:
        x, y = q.popleft()
        base = dist[y][x]
        if x > 0 and dist[y][x - 1] < 0:
            dist[y][x - 1] = base + 1
            q.append((x - 1, y))
        if x + 1 < w and dist[y][x + 1] < 0:
            dist[y][x + 1] = base + 1
            q.append((x + 1, y))
        if y > 0 and dist[y - 1][x] < 0:
            dist[y - 1][x] = base + 1
            q.append((x, y - 1))
        if y + 1 < h and dist[y + 1][x] < 0:
            dist[y + 1][x] = base + 1
            q.append((x, y + 1))

    return dist


def _distance_to_mountains(mountain_mask):
    h = len(mountain_mask)
    w = len(mountain_mask[0])
    dist = [[-1] * w for _ in range(h)]
    q = deque()

    for y in range(h):
        for x in range(w):
            if mountain_mask[y][x]:
                dist[y][x] = 0
                q.append((x, y))

    while q:
        x, y = q.popleft()
        base = dist[y][x]
        if x > 0 and dist[y][x - 1] < 0:
            dist[y][x - 1] = base + 1
            q.append((x - 1, y))
        if x + 1 < w and dist[y][x + 1] < 0:
            dist[y][x + 1] = base + 1
            q.append((x + 1, y))
        if y > 0 and dist[y - 1][x] < 0:
            dist[y - 1][x] = base + 1
            q.append((x, y - 1))
        if y + 1 < h and dist[y + 1][x] < 0:
            dist[y + 1][x] = base + 1
            q.append((x, y + 1))

    return dist


def _ocean_connected_water_mask(final_map):
    h = len(final_map)
    w = len(final_map[0])
    is_water = lambda t: t in ("W", "O")
    ocean = [[False] * w for _ in range(h)]
    q = deque()

    for x in range(w):
        if is_water(final_map[0][x]):
            ocean[0][x] = True
            q.append((x, 0))
        if is_water(final_map[h - 1][x]):
            ocean[h - 1][x] = True
            q.append((x, h - 1))
    for y in range(h):
        if is_water(final_map[y][0]):
            ocean[y][0] = True
            q.append((0, y))
        if is_water(final_map[y][w - 1]):
            ocean[y][w - 1] = True
            q.append((w - 1, y))

    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= w or ny >= h:
                continue
            if ocean[ny][nx]:
                continue
            if not is_water(final_map[ny][nx]):
                continue
            ocean[ny][nx] = True
            q.append((nx, ny))

    return ocean


def _smooth_river_shapes(final_map):
    h = len(final_map)
    w = len(final_map[0])
    ocean = _ocean_connected_water_mask(final_map)
    updated = [row[:] for row in final_map]

    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if ocean[y][x]:
                continue

            water_neighbors = 0
            for yy in range(y - 1, y + 2):
                for xx in range(x - 1, x + 2):
                    if xx == x and yy == y:
                        continue
                    if final_map[yy][xx] == "W" and not ocean[yy][xx]:
                        water_neighbors += 1

            tile = final_map[y][x]
            if tile == "W":
                if water_neighbors <= 1:
                    updated[y][x] = "G"
            elif tile in ("G", "F", "H", "M", "P"):
                if water_neighbors >= 5:
                    updated[y][x] = "W"

    for y in range(h):
        for x in range(w):
            if not ocean[y][x]:
                final_map[y][x] = updated[y][x]


def _add_rivers(final_map, elevation_map, seed: int, min_dim: int):
    h = len(final_map)
    w = len(final_map[0])
    rng = random.Random(seed + 424242)
    water_tiles = {"W", "O"}

    sources = [(x, y) for y in range(h) for x in range(w) if final_map[y][x] in ("H", "M")]
    ocean_targets = [(x, y) for y in range(h) for x in range(w) if final_map[y][x] == "O"]
    if not sources or not ocean_targets:
        return

    target_rivers = max(1, min(3, (w * h) // 40000 + 1))
    min_source_spacing = max(6, min_dim // 20)
    min_source_spacing_sq = min_source_spacing * min_source_spacing
    min_length = max(14, min_dim // 6)
    max_steps = (w + h) * 4

    rng.shuffle(sources)
    chosen_sources = []
    created = 0

    for sx, sy in sources:
        if created >= target_rivers:
            break
        if any((sx - ox) * (sx - ox) + (sy - oy) * (sy - oy) < min_source_spacing_sq for ox, oy in chosen_sources):
            continue

        tx, ty = rng.choice(ocean_targets)
        cx, cy = sx, sy
        prev_dx, prev_dy = 0, 0
        visited = set()
        path = []
        reached_ocean = False
        left_mountains = False

        for step in range(max_steps):
            path.append((cx, cy))
            visited.add((cx, cy))

            if step > 0 and final_map[cy][cx] == "O":
                reached_ocean = True
                break

            if not left_mountains and final_map[cy][cx] not in ("H", "M", "P"):
                left_mountains = True

            current_elev = elevation_map[cy][cx]
            candidates = []
            relaxed_candidates = []
            for ny in range(max(0, cy - 1), min(h, cy + 2)):
                for nx in range(max(0, cx - 1), min(w, cx + 2)):
                    if nx == cx and ny == cy:
                        continue

                    dx = nx - cx
                    dy = ny - cy
                    dist_target = abs(tx - nx) + abs(ty - ny)
                    elev = elevation_map[ny][nx]
                    if left_mountains and final_map[ny][nx] in ("H", "M", "P"):
                        continue

                    uphill_diff = elev - current_elev
                    if left_mountains and uphill_diff > 0.003:
                        if uphill_diff > 0.015:
                            continue
                    uphill_penalty = max(0.0, uphill_diff) * 2.6
                    visit_penalty = 0.65 if (nx, ny) in visited else 0.0
                    turn_penalty = 0.0
                    if prev_dx != 0 or prev_dy != 0:
                        turn_penalty = (abs(dx - prev_dx) + abs(dy - prev_dy)) * 0.02
                    water_bonus = -1.0 if final_map[ny][nx] in water_tiles else 0.0
                    jitter = (rng.random() - 0.5) * 0.95
                    score = dist_target * 0.42 + elev * 0.33 + uphill_penalty + turn_penalty + visit_penalty + water_bonus + jitter

                    if uphill_diff <= 0.003:
                        candidates.append((score, nx, ny, dx, dy))
                    else:
                        relaxed_candidates.append((score + uphill_diff * 6.0, nx, ny, dx, dy))

            if not candidates:
                if relaxed_candidates:
                    candidates = relaxed_candidates
                else:
                    break

            candidates.sort(key=lambda it: it[0])
            top_n = min(5, len(candidates))
            pick_index = min(top_n - 1, int((rng.random() ** 1.6) * top_n))
            pick = candidates[pick_index]
            _, nx, ny, dx, dy = pick
            cx, cy = nx, ny
            prev_dx, prev_dy = dx, dy

        if not reached_ocean or len(path) < min_length:
            continue

        chosen_sources.append((sx, sy))
        created += 1
        plen = max(1, len(path) - 1)
        for i, (px, py) in enumerate(path):
            frac = i / plen
            base_radius = 0 if frac < 0.30 else 1
            if frac > 0.80 and rng.random() > 0.50:
                base_radius = 2
            radius = base_radius if rng.random() > 0.25 else max(0, base_radius - 1)

            for yy in range(max(0, py - radius), min(h, py + radius + 1)):
                for xx in range(max(0, px - radius), min(w, px + radius + 1)):
                    if final_map[yy][xx] == "O":
                        continue
                    if (xx - px) * (xx - px) + (yy - py) * (yy - py) > radius * radius + 0.65:
                        continue
                    final_map[yy][xx] = "W"


def _grow_tree_clusters(final_map, dist_to_ocean, seed: int, min_dim: int):
    h = len(final_map)
    w = len(final_map[0])
    rng = random.Random(seed + 8181)

    for y in range(h):
        for x in range(w):
            if final_map[y][x] == "F":
                final_map[y][x] = "G"

    plain_cells = [(x, y) for y in range(h) for x in range(w) if final_map[y][x] == "G" and dist_to_ocean[y][x] >= 3]
    if not plain_cells:
        return

    target_trees = int(len(plain_cells) * 0.38)
    cluster_count = max(8, min(90, (w * h) // 2200))
    min_spacing = max(4, min_dim // 20)
    min_spacing_sq = min_spacing * min_spacing

    rng.shuffle(plain_cells)
    centers = []
    for x, y in plain_cells:
        if len(centers) >= cluster_count:
            break
        if any((x - cx) * (x - cx) + (y - cy) * (y - cy) < min_spacing_sq for cx, cy in centers):
            continue
        centers.append((x, y))

    tree_count = 0
    for cx, cy in centers:
        if tree_count >= target_trees:
            break

        cluster_target = rng.randint(max(25, min_dim // 2), max(70, min_dim * 2))
        cluster_cells = {(cx, cy)}
        frontier = [(cx, cy)]

        while frontier and len(cluster_cells) < cluster_target and tree_count < target_trees:
            idx = rng.randrange(len(frontier))
            px, py = frontier[idx]
            frontier[idx] = frontier[-1]
            frontier.pop()

            neighbors = [(px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1), (px - 1, py - 1), (px + 1, py + 1)]
            rng.shuffle(neighbors)
            for nx, ny in neighbors:
                if nx < 0 or ny < 0 or nx >= w or ny >= h:
                    continue
                if (nx, ny) in cluster_cells:
                    continue
                if final_map[ny][nx] != "G" or dist_to_ocean[ny][nx] < 3:
                    continue

                center_dist = abs(nx - cx) + abs(ny - cy)
                grow_chance = 0.74 - center_dist * 0.018 + (_value_noise(nx / 8.0, ny / 8.0, seed + 9111) - 0.5) * 0.16
                if rng.random() <= _clamp(grow_chance, 0.10, 0.88):
                    cluster_cells.add((nx, ny))
                    frontier.append((nx, ny))

        for tx, ty in cluster_cells:
            if tree_count >= target_trees:
                break
            if final_map[ty][tx] == "G":
                final_map[ty][tx] = "F"
                tree_count += 1


def _emit_progress(progress_callback, progress: float, label: str):
    if progress_callback is None:
        return
    progress_callback(_clamp(progress, 0.0, 1.0), label)


def generuj_mape(config: WorldConfig | None = None, progress_callback=None):
    if config is None:
        config = WorldConfig(seed=random.randint(0, 2_147_483_647))
    config = _validate_config(config)

    width = config.width
    height = config.height
    seed = config.seed
    chunk = config.chunk_size
    profile = _generation_profile(width, height)
    chunks_x = (width + chunk - 1) // chunk
    chunks_y = (height + chunk - 1) // chunk
    total_chunks = max(1, chunks_x * chunks_y)

    _emit_progress(progress_callback, 0.01, "Przygotowanie generatora")

    # Scale parameters adapt to world dimensions so 20x20 and 300x300 both look usable.
    min_dim = min(width, height)
    continent_scale = max(22.0, min_dim * 0.95)
    detail_scale = max(9.0, continent_scale * 0.28)
    ridge_scale = max(6.0, detail_scale * 0.65)

    elevation_map = [[0.0] * width for _ in range(height)]

    elevation_chunk_idx = 0
    for cy in range(0, height, chunk):
        y_end = min(height, cy + chunk)
        for cx in range(0, width, chunk):
            x_end = min(width, cx + chunk)
            for y in range(cy, y_end):
                for x in range(cx, x_end):
                    continent = _value_noise(x / continent_scale, y / continent_scale, seed + 17)
                    detail = _value_noise(x / detail_scale, y / detail_scale, seed + 71)
                    ridge = _value_noise(x / ridge_scale, y / ridge_scale, seed + 131)
                    elevation = continent * 0.66 + detail * 0.24 + ridge * 0.10
                    elevation_map[y][x] = _clamp(elevation, 0.0, 1.0)
            elevation_chunk_idx += 1
            _emit_progress(
                progress_callback,
                0.05 + (elevation_chunk_idx / total_chunks) * 0.35,
                "Generowanie wysokosci terenu",
            )

    sea_threshold = _estimate_sea_threshold(elevation_map, config.sea_level)
    water_mask = [[False] * width for _ in range(height)]

    for y in range(height):
        for x in range(width):
            water_mask[y][x] = elevation_map[y][x] <= sea_threshold
    dist_to_water_base = _distance_to_water(water_mask)
    mountain_coast_buffer = max(3, min_dim // 20)
    _emit_progress(progress_callback, 0.42, "Wyznaczanie linii brzegowej")

    mountain_cutoff = 0.77 - config.mountain_strength * 0.24
    map_chars = [["G"] * width for _ in range(height)]
    mountain_score_map = [[0.0] * width for _ in range(height)]

    biome_chunk_idx = 0
    for cy in range(0, height, chunk):
        y_end = min(height, cy + chunk)
        for cx in range(0, width, chunk):
            x_end = min(width, cx + chunk)
            for y in range(cy, y_end):
                for x in range(cx, x_end):
                    if water_mask[y][x]:
                        map_chars[y][x] = "W"
                        continue

                    elevation = elevation_map[y][x]
                    ridge = _value_noise(x / ridge_scale, y / ridge_scale, seed + 409)
                    mountain_score = elevation * 0.78 + ridge * 0.22
                    mountain_score_map[y][x] = mountain_score
                    if (
                        mountain_score >= mountain_cutoff
                        and elevation > sea_threshold + 0.02
                        and dist_to_water_base[y][x] >= mountain_coast_buffer
                    ):
                        map_chars[y][x] = "M"
                        continue
                    map_chars[y][x] = "G"
            biome_chunk_idx += 1
            _emit_progress(
                progress_callback,
                0.45 + (biome_chunk_idx / total_chunks) * 0.30,
                "Rozklad biomow",
            )

    mountain_count = sum(1 for row in map_chars for tile in row if tile == "M")
    non_water_count = sum(1 for row in water_mask for v in row if not v)
    min_mountain_count = int(non_water_count * 0.30)
    if mountain_count < min_mountain_count:
        candidates = []
        for y in range(height):
            for x in range(width):
                if water_mask[y][x]:
                    continue
                if map_chars[y][x] == "M":
                    continue
                if dist_to_water_base[y][x] < mountain_coast_buffer:
                    continue
                candidates.append((mountain_score_map[y][x], x, y))
        candidates.sort(reverse=True)
        needed = min_mountain_count - mountain_count
        for i in range(min(needed, len(candidates))):
            _, x, y = candidates[i]
            map_chars[y][x] = "M"
    _emit_progress(progress_callback, 0.78, "Balans pasm gorskich")

    _emit_progress(progress_callback, 0.82, "Balans lesistosci")

    # Step 2: lightweight refinement pass, adaptive for larger worlds.
    map_chars = _refine_biomes(
        map_chars,
        water_mask,
        passes=profile["refine_passes"],
        stride=profile["refine_stride"],
    )
    _emit_progress(progress_callback, 0.88, "Krok 2: wygladzanie mapy")
    refined_water_mask = [[map_chars[y][x] == "W" for x in range(width)] for y in range(height)]
    refined_mountain_mask = [[map_chars[y][x] == "M" for x in range(width)] for y in range(height)]

    water_depth = _distance_from_land(refined_water_mask)
    mountain_depth = _distance_from_non_mountain(refined_mountain_mask)

    deep_ocean_threshold = max(2, int(min_dim * 0.025) + 1)
    mountain_high_threshold = 2
    mountain_peak_threshold = max(3, int(min_dim * 0.012) + 1)
    ocean_noise_scale = max(12.0, min_dim * 0.25)

    final_map = [["G"] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            tile = map_chars[y][x]
            if tile == "W":
                depth = water_depth[y][x]
                ocean_noise = _value_noise(x / ocean_noise_scale, y / ocean_noise_scale, seed + 521)
                if depth >= deep_ocean_threshold and ocean_noise > 0.22:
                    final_map[y][x] = "O"
                else:
                    final_map[y][x] = "W"
                continue

            if tile == "M":
                depth = mountain_depth[y][x]
                score = mountain_score_map[y][x]
                if depth >= mountain_peak_threshold and score > mountain_cutoff + 0.025:
                    final_map[y][x] = "P"
                elif depth >= mountain_high_threshold:
                    final_map[y][x] = "M"
                else:
                    final_map[y][x] = "H"
                continue

            final_map[y][x] = tile
        if y % 8 == 0 or y == height - 1:
            _emit_progress(
                progress_callback,
                0.90 + ((y + 1) / height) * 0.09,
                "Finalizacja wysokosci gor i dna oceanu",
            )

    peak_count = sum(1 for row in final_map for tile in row if tile == "P")
    if peak_count == 0:
        peak_candidates = []
        for y in range(height):
            for x in range(width):
                if final_map[y][x] == "M":
                    peak_candidates.append((mountain_score_map[y][x], x, y))
        peak_candidates.sort(reverse=True)
        promote = min(max(1, len(peak_candidates) // 18), 40)
        for i in range(min(promote, len(peak_candidates))):
            _, x, y = peak_candidates[i]
            final_map[y][x] = "P"

    mountain_tiles = {"H", "M", "P"}
    adjusted = [row[:] for row in final_map]
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            tile = final_map[y][x]
            if tile not in mountain_tiles:
                continue
            mountain_neighbors = 0
            for yy in range(y - 1, y + 2):
                for xx in range(x - 1, x + 2):
                    if xx == x and yy == y:
                        continue
                    if final_map[yy][xx] in mountain_tiles:
                        mountain_neighbors += 1

            if tile == "P" and mountain_neighbors <= 6:
                adjusted[y][x] = "M"
            if tile in ("M", "P") and mountain_neighbors <= 7:
                adjusted[y][x] = "H"

    final_map = adjusted

    ocean_only_mask = [[final_map[y][x] == "O" for x in range(width)] for y in range(height)]
    if not any(any(row) for row in ocean_only_mask):
        ocean_only_mask = _ocean_connected_water_mask(final_map)
    dist_to_ocean = _distance_to_water(ocean_only_mask)
    for y in range(height):
        for x in range(width):
            if final_map[y][x] not in ("H", "M", "P"):
                continue
            if dist_to_ocean[y][x] > mountain_coast_buffer:
                continue
            final_map[y][x] = "G"

    _grow_tree_clusters(
        final_map,
        dist_to_ocean,
        seed,
        min_dim,
    )

    _emit_progress(progress_callback, 0.97, "Dodawanie rzek")
    _add_rivers(final_map, elevation_map, seed, min_dim)
    _smooth_river_shapes(final_map)

    _emit_progress(progress_callback, 1.0, "Mapa gotowa")
    return final_map


def zapisz_mape(mapa):
    base_path = os.path.dirname(os.path.dirname(__file__))
    map_path = os.path.join(base_path, "data", "map.txt")
    with open(map_path, "w") as f:
        for row in mapa:
            f.write("".join(row) + "\n")
    return map_path


def _ask_int(prompt: str, default: int, min_value: int, max_value: int) -> int:
    raw = input(f"{prompt} [{min_value}-{max_value}] (default: {default}): ").strip()
    if not raw:
        return default
    value = int(raw)
    return max(min_value, min(max_value, value))


def _ask_float(prompt: str, default: float, min_value: float, max_value: float) -> float:
    raw = input(f"{prompt} [{min_value}-{max_value}] (default: {default}): ").strip()
    if not raw:
        return default
    value = float(raw)
    return _clamp(value, min_value, max_value)


def _ask_config_interactive(default_seed: int | None = None) -> WorldConfig:
    if default_seed is None:
        default_seed = random.randint(0, 2_147_483_647)

    width = _ask_int("World width", 100, MIN_WORLD_SIZE, MAX_WORLD_SIZE)
    height = _ask_int("World height", 100, MIN_WORLD_SIZE, MAX_WORLD_SIZE)
    seed = _ask_int("Seed", default_seed, 0, 2_147_483_647)
    sea_level = _ask_float("Sea level", 0.52, 0.30, 0.75)
    mountain_strength = _ask_float("Mountain strength", 0.55, 0.0, 1.0)
    climate_bias = _ask_float("Climate bias (-cold / +warm)", 0.0, -1.0, 1.0)

    chunk_size = recommended_chunk_size(width, height)

    return WorldConfig(
        width=width,
        height=height,
        seed=seed,
        sea_level=sea_level,
        mountain_strength=mountain_strength,
        climate_bias=climate_bias,
        chunk_size=chunk_size,
    )


def _parse_args():
    parser = argparse.ArgumentParser(description="Generate a world map for GodGrid.")
    parser.add_argument("--width", type=int, default=100, help="World width (20-300)")
    parser.add_argument("--height", type=int, default=100, help="World height (20-300)")
    parser.add_argument("--seed", type=int, default=None, help="Seed (default: random)")
    parser.add_argument("--sea-level", type=float, default=0.52, help="Sea level ratio (0.30-0.75)")
    parser.add_argument("--mountain-strength", type=float, default=0.55, help="Mountain amount (0.0-1.0)")
    parser.add_argument("--climate-bias", type=float, default=0.0, help="Climate shift (-1.0 to 1.0)")
    parser.add_argument("--chunk-size", type=int, default=64, help="Chunk size (16-256)")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for world settings instead of using CLI flags",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.interactive:
        config = _ask_config_interactive(args.seed)
    else:
        seed = args.seed if args.seed is not None else random.randint(0, 2_147_483_647)
        config = WorldConfig(
            width=args.width,
            height=args.height,
            seed=seed,
            sea_level=args.sea_level,
            mountain_strength=args.mountain_strength,
            climate_bias=args.climate_bias,
            chunk_size=args.chunk_size,
        )

    mapa = generuj_mape(config)
    map_path = zapisz_mape(mapa)
    print(
        "Mapa wygenerowana:",
        f"{config.width}x{config.height}, seed={config.seed},",
        f"sea={config.sea_level:.2f}, mountain={config.mountain_strength:.2f}, climate={config.climate_bias:.2f}",
    )
    print(f"Zapisano: {map_path}")
