import math
import random

import pygame

import menu
from map_gen import WorldConfig, generuj_mape, recommended_chunk_size, zapisz_mape
from map_io import TILE_COLORS, load_map, map_path_from_project_root, save_map
from mouse_state import MouseState
from painting import apply_brush, apply_brush_line, screen_to_tile
from tile_subtypes import build_color_map, build_subtype_map, refresh_colors_around, refresh_subtypes_around


def main():
    pygame.init()

    info = pygame.display.Info()
    screen_size = (info.current_w, info.current_h)
    screen_width, screen_height = screen_size
    viewport_top = menu.MENU_HEIGHT
    viewport_width = screen_width
    viewport_height = screen_height - viewport_top

    map_path = map_path_from_project_root(__file__)
    mapa = load_map(map_path)
    subtype_map = build_subtype_map(mapa)
    color_map = build_color_map(mapa, subtype_map, TILE_COLORS)

    map_width = len(mapa[0])
    map_height = len(mapa)
    menu.set_world_size(map_width, map_height)

    screen = pygame.display.set_mode(screen_size)
    pygame.display.set_caption("GodGrid")
    clock = pygame.time.Clock()
    progress_font = pygame.font.SysFont("segoeui", 28)
    progress_small_font = pygame.font.SysFont("segoeui", 22)
    running = True
    needs_redraw = True

    tile_draw_size = 1.0
    camera_x = 0.0
    camera_y = 0.0
    map_layer_surface = pygame.Surface((1, 1))
    map_layer_scale = 4
    flower_layer_surface = pygame.Surface((1, 1), pygame.SRCALPHA)
    flower_layer_scale = 2
    water_phase = 0.0
    anim_accum_ms = 0.0
    anim_step_ms = 50.0
    coastal_wave_tiles = []
    clouds = []
    cloud_time = 0.0
    scaled_map_cache = None
    scaled_flower_cache = None
    scaled_cache_width = 0
    scaled_cache_height = 0
    scaled_cache_dirty = True
    reduced_motion = False

    def clamp_channel(v: int):
        return max(0, min(255, int(v)))

    def darken(color, factor: float):
        r, g, b = color
        return (clamp_channel(r * factor), clamp_channel(g * factor), clamp_channel(b * factor))

    def blend(color_a, color_b, t: float):
        ar, ag, ab = color_a
        br, bg, bb = color_b
        return (
            clamp_channel(ar * (1.0 - t) + br * t),
            clamp_channel(ag * (1.0 - t) + bg * t),
            clamp_channel(ab * (1.0 - t) + bb * t),
        )

    def neighbors4(x: int, y: int):
        if x > 0:
            yield x - 1, y
        if x + 1 < map_width:
            yield x + 1, y
        if y > 0:
            yield x, y - 1
        if y + 1 < map_height:
            yield x, y + 1

    def styled_tile_color(x: int, y: int):
        subtype = subtype_map[y][x]
        base = color_map[y][x]
        is_water = subtype in ("water", "deep_ocean")

        has_other_neighbor = False
        near_water = False
        for nx, ny in neighbors4(x, y):
            nsub = subtype_map[ny][nx]
            if nsub != subtype:
                has_other_neighbor = True
            if nsub in ("water", "deep_ocean"):
                near_water = True

        if (not is_water) and near_water:
            sand = (198, 178, 122)
            coast_strength = 0.40 if subtype == "grass" else 0.30
            base = blend(base, sand, coast_strength)

        if has_other_neighbor:
            base = darken(base, 0.82)

        # Directional shadows: light from top-left, shadow cast to bottom-right.
        if x > 0 and y > 0:
            caster = subtype_map[y - 1][x - 1]
            if caster in ("forest", "highland", "mountain_high", "mountain_peak") and not is_water:
                base = darken(base, 0.88)

        # Palette quantization keeps the look crisp/cartoony (less noisy gradients).
        q = 18
        base = tuple((c // q) * q for c in base)

        return base

    def expand_tiles(changed_tiles, radius: int = 1):
        if not changed_tiles:
            return set()
        out = set()
        for x, y in changed_tiles:
            for ny in range(max(0, y - radius), min(map_height - 1, y + radius) + 1):
                for nx in range(max(0, x - radius), min(map_width - 1, x + radius) + 1):
                    out.add((nx, ny))
        return out

    def compute_fixed_view():
        nonlocal tile_draw_size, camera_x, camera_y
        tile_draw_size = viewport_height / max(1, map_height)
        map_pixel_w = map_width * tile_draw_size
        camera_x = (viewport_width - map_pixel_w) / 2
        camera_y = 0.0

    def rebuild_clouds():
        nonlocal clouds
        rng = random.Random(1337)
        cloud_count = max(6, min(14, (map_width * map_height) // 3000 + 6))
        clouds = []
        for _ in range(cloud_count):
            clouds.append(
                {
                    "x_pct": rng.random(),
                    "y_pct": rng.uniform(0.03, 0.55),
                    "amp_pct": rng.uniform(0.02, 0.08),
                    "speed": rng.uniform(0.12, 0.34),
                    "phase": rng.uniform(0.0, math.tau),
                    "scale": rng.uniform(0.8, 1.9),
                    "alpha": rng.randint(34, 76),
                }
            )

    def draw_clouds(target_surface, map_screen_x: int, map_screen_y: int, scaled_map_width: int):
        if not clouds:
            return

        layer = pygame.Surface((scaled_map_width, viewport_height), pygame.SRCALPHA)
        for cloud in clouds:
            base_x = cloud["x_pct"] * scaled_map_width
            amp = cloud["amp_pct"] * scaled_map_width
            cx = int(base_x + math.sin(cloud_time * cloud["speed"] + cloud["phase"]) * amp)
            cy = int(cloud["y_pct"] * viewport_height)

            radius = max(5, int(tile_draw_size * 1.45 * cloud["scale"]))
            color = (250, 252, 255, cloud["alpha"])
            shadow = (206, 216, 234, max(16, cloud["alpha"] - 20))
            puffs = (
                (-1.00, 0.05, 1.00, 0.72),
                (-0.30, -0.30, 1.10, 0.78),
                (0.45, -0.26, 1.02, 0.76),
                (1.08, 0.03, 0.92, 0.70),
                (0.12, 0.34, 0.86, 0.64),
            )
            for ox, oy, sx, sy in puffs:
                bw = max(6, int(radius * sx * 1.35))
                bh = max(4, int(radius * sy))
                px = int(cx + ox * radius * 1.05 - bw // 2)
                py = int(cy + oy * radius * 0.95 - bh // 2)
                rr = max(2, bh // 2)
                pygame.draw.rect(layer, color, (px, py, bw, bh), border_radius=rr)
                pygame.draw.rect(layer, shadow, (px, py + int(bh * 0.55), bw, max(1, int(bh * 0.42))), border_radius=rr)

        target_surface.blit(layer, (map_screen_x, map_screen_y))

    def rebuild_map_layer():
        nonlocal map_layer_surface, scaled_cache_dirty
        map_pixel_w = max(1, map_width * map_layer_scale)
        map_pixel_h = max(1, map_height * map_layer_scale)
        map_layer_surface = pygame.Surface((map_pixel_w, map_pixel_h), pygame.SRCALPHA)

        for y in range(map_height):
            for x in range(map_width):
                paint_map_tile(x, y, styled_tile_color(x, y))
        scaled_cache_dirty = True

    def paint_map_tile(x: int, y: int, color):
        base_x = x * map_layer_scale
        base_y = y * map_layer_scale
        cell_rect = pygame.Rect(base_x, base_y, map_layer_scale, map_layer_scale)
        pygame.draw.rect(map_layer_surface, darken(color, 0.96), cell_rect)

        h = ((x * 92837111) ^ (y * 689287499) ^ 0x517CC1B7) & 0xFFFFFFFF
        inset = 1 if (h % 4) == 0 else 0
        size = max(2, map_layer_scale - inset)
        rect = pygame.Rect(base_x + inset, base_y + inset, size, size)
        radius = max(1, int(size * 0.48))

        pygame.draw.rect(map_layer_surface, color, rect, border_radius=radius)
        highlight = blend(color, (255, 255, 255), 0.10)
        hx = rect.x + max(0, rect.w // 4)
        hy = rect.y + max(0, rect.h // 4)
        if hx < map_layer_surface.get_width() and hy < map_layer_surface.get_height():
            map_layer_surface.set_at((hx, hy), highlight)

    def flower_color_for_tile(x: int, y: int):
        if tile_draw_size < 5.0:
            return None
        if subtype_map[y][x] != "grass":
            return None

        h = ((x * 73856093) ^ (y * 19349663) ^ 0x9E3779B9) & 0xFFFFFFFF
        if (h % 100) >= 14:
            return None

        palette = (
            (255, 228, 110, 220),
            (255, 168, 196, 220),
            (236, 244, 255, 220),
            (208, 178, 255, 220),
        )
        return palette[(h >> 9) % len(palette)], h

    def rebuild_flower_layer():
        nonlocal flower_layer_surface, scaled_cache_dirty
        fw = max(1, map_width * flower_layer_scale)
        fh = max(1, map_height * flower_layer_scale)
        flower_layer_surface = pygame.Surface((fw, fh), pygame.SRCALPHA)

        for y in range(map_height):
            for x in range(map_width):
                paint_flower_tile(x, y)
        scaled_cache_dirty = True

    def paint_flower_tile(x: int, y: int):
        base_x = x * flower_layer_scale
        base_y = y * flower_layer_scale
        flower_layer_surface.fill((0, 0, 0, 0), (base_x, base_y, flower_layer_scale, flower_layer_scale))

        flower_data = flower_color_for_tile(x, y)
        if flower_data is None:
            return

        color, h = flower_data
        dx = 1 + ((h >> 13) & 1) - ((h >> 15) & 1)
        dy = 1 + ((h >> 17) & 1) - ((h >> 19) & 1)
        fx = max(base_x, min(base_x + flower_layer_scale - 1, base_x + dx))
        fy = max(base_y, min(base_y + flower_layer_scale - 1, base_y + dy))
        flower_layer_surface.set_at((fx, fy), color)

        if ((h >> 21) & 1) == 1:
            accent = (255, 255, 255, 180)
            ax = max(base_x, min(base_x + flower_layer_scale - 1, fx - 1))
            ay = max(base_y, min(base_y + flower_layer_scale - 1, fy))
            flower_layer_surface.set_at((ax, ay), accent)

    def update_map_layer_tiles(changed_tiles):
        if not changed_tiles:
            return
        nonlocal scaled_cache_dirty
        for x, y in changed_tiles:
            paint_map_tile(x, y, styled_tile_color(x, y))
            paint_flower_tile(x, y)
        scaled_cache_dirty = True

    def rebuild_water_wave_data():
        nonlocal coastal_wave_tiles
        coastal_wave_tiles = []
        for y in range(map_height):
            for x in range(map_width):
                subtype = subtype_map[y][x]
                if subtype not in ("water", "deep_ocean"):
                    continue
                coastal = False
                for nx, ny in neighbors4(x, y):
                    if subtype_map[ny][nx] not in ("water", "deep_ocean"):
                        coastal = True
                        break
                if not coastal:
                    continue
                h = ((x * 83492791) ^ (y * 27644437) ^ 0xA5A5A5A5) & 0xFFFFFFFF
                coastal_wave_tiles.append((x, y, subtype, h))

    def draw_water_wave_lines(target_surface, map_screen_x: int, map_screen_y: int):
        if tile_draw_size < 4.0:
            return
        if not coastal_wave_tiles:
            return

        scaled_map_width = max(1, int(round(map_width * tile_draw_size)))
        wave_layer = pygame.Surface((scaled_map_width, viewport_height), pygame.SRCALPHA)
        line_px = max(1, int(tile_draw_size * 0.10))
        segment_len = max(2, int(tile_draw_size * 0.34))

        for x, y, subtype, h in coastal_wave_tiles:
            if (h % 12) != 0:
                continue

            tile_left = int(x * tile_draw_size)
            tile_right = int((x + 1) * tile_draw_size) - 1
            tile_top = int(y * tile_draw_size)
            y_line = tile_top + int(tile_draw_size * (0.52 + 0.10 * math.sin((h % 19) * 0.4)))

            lane = tile_draw_size + segment_len + 3
            shift = (water_phase * 0.95 + (h % 97)) % lane
            seg_start = int(tile_left + shift - segment_len)
            seg_end = seg_start + segment_len
            x1 = max(tile_left, seg_start)
            x2 = min(tile_right, seg_end)
            if x2 <= x1:
                continue

            if subtype == "deep_ocean":
                color = (104, 160, 232, 96)
            else:
                color = (220, 246, 255, 112)
            pygame.draw.line(wave_layer, color, (x1, y_line), (x2, y_line), line_px)

        target_surface.blit(wave_layer, (map_screen_x, map_screen_y))

    def draw_generation_progress(progress, label):
        screen.fill((14, 16, 20))
        menu.menu_draw(screen)

        bar_w = min(560, screen_width - 80)
        bar_h = 34
        bar_x = (screen_width - bar_w) // 2
        bar_y = viewport_top + (viewport_height // 2) - (bar_h // 2)

        pygame.draw.rect(screen, (42, 48, 61), (bar_x, bar_y, bar_w, bar_h), border_radius=10)
        fill_w = int(bar_w * max(0.0, min(1.0, progress)))
        if fill_w > 0:
            pygame.draw.rect(screen, (100, 132, 214), (bar_x, bar_y, fill_w, bar_h), border_radius=10)
        pygame.draw.rect(screen, (70, 78, 96), (bar_x, bar_y, bar_w, bar_h), 2, border_radius=10)

        title = progress_font.render("Generowanie swiata...", True, (236, 240, 248))
        title_rect = title.get_rect(center=(screen_width // 2, bar_y - 44))
        screen.blit(title, title_rect)

        status = progress_small_font.render(label, True, (236, 240, 248))
        status_rect = status.get_rect(center=(screen_width // 2, bar_y + bar_h + 26))
        screen.blit(status, status_rect)

        percent = progress_small_font.render(f"{int(progress * 100)}%", True, (236, 240, 248))
        percent_rect = percent.get_rect(center=(screen_width // 2, bar_y + (bar_h // 2)))
        screen.blit(percent, percent_rect)

        pygame.display.flip()

    compute_fixed_view()
    rebuild_map_layer()
    rebuild_flower_layer()
    rebuild_water_wave_data()
    rebuild_clouds()

    mouse = MouseState()

    def regenerate_world(width, height):
        nonlocal mapa, subtype_map, color_map, map_width, map_height, needs_redraw

        seed = random.randint(0, 2_147_483_647)
        config = WorldConfig(
            width=width,
            height=height,
            seed=seed,
            chunk_size=recommended_chunk_size(width, height),
        )

        def on_progress(progress, label):
            pygame.event.pump()
            draw_generation_progress(progress, label)

        draw_generation_progress(0.0, "Start")
        generated = generuj_mape(config, progress_callback=on_progress)
        saved_generated_path = zapisz_mape(generated)

        mapa = load_map(saved_generated_path)
        subtype_map = build_subtype_map(mapa)
        color_map = build_color_map(mapa, subtype_map, TILE_COLORS)
        map_width = len(mapa[0])
        map_height = len(mapa)
        menu.set_world_size(map_width, map_height)

        compute_fixed_view()
        rebuild_map_layer()
        rebuild_flower_layer()
        rebuild_water_wave_data()
        rebuild_clouds()

        mouse.dragging = False
        mouse.painting = False
        mouse.last_paint_tile = None
        needs_redraw = True
        print(f"Wygenerowano nowy swiat: {map_width}x{map_height}, seed={seed}")

    def place_at_mouse(mouse_pos, interpolate=False):
        if menu.is_point_on_menu(mouse_pos):
            return False

        tile_pos = screen_to_tile(
            mouse_pos[0],
            mouse_pos[1] - viewport_top,
            camera_x,
            camera_y,
            tile_draw_size,
            map_width,
            map_height,
        )
        if tile_pos is None:
            return False

        tile_id = menu.get_current_tool()["item_id"]
        brush_size = menu.get_brush_size()

        if mouse.last_paint_tile is None or not interpolate:
            changed_tiles = apply_brush(mapa, tile_pos, tile_id, brush_size)
            refresh_subtypes_around(mapa, subtype_map, changed_tiles)
            refresh_colors_around(mapa, subtype_map, color_map, changed_tiles, TILE_COLORS)
            affected = expand_tiles(changed_tiles, radius=1)
            update_map_layer_tiles(affected)
            rebuild_water_wave_data()
            mouse.last_paint_tile = tile_pos
            return bool(changed_tiles)

        changed_tiles = apply_brush_line(mapa, mouse.last_paint_tile, tile_pos, tile_id, brush_size)
        refresh_subtypes_around(mapa, subtype_map, changed_tiles)
        refresh_colors_around(mapa, subtype_map, color_map, changed_tiles, TILE_COLORS)
        affected = expand_tiles(changed_tiles, radius=1)
        update_map_layer_tiles(affected)
        rebuild_water_wave_data()
        mouse.last_paint_tile = tile_pos
        return bool(changed_tiles)

    while running:
        dt_ms = clock.tick(120)
        if not reduced_motion:
            anim_accum_ms += dt_ms
            while anim_accum_ms >= anim_step_ms:
                anim_accum_ms -= anim_step_ms
                cloud_time = (cloud_time + anim_step_ms * 0.0012) % 1000000.0
                if coastal_wave_tiles and tile_draw_size >= 4.0:
                    water_phase = (water_phase + anim_step_ms * 0.008) % 1000000.0
                needs_redraw = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
                    saved_path = save_map(mapa, map_path)
                    print(f"Mapa zapisana: {saved_path}")
                elif event.key == pygame.K_m:
                    reduced_motion = not reduced_motion
                    print(f"Reduced motion: {'ON' if reduced_motion else 'OFF'}")
                    needs_redraw = True

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()

                if event.button == 1:
                    if menu.is_point_on_menu(mouse_pos):
                        action = menu.handle_mouse_down(mouse_pos)
                        needs_redraw = True
                        if action == "quit":
                            running = False
                        elif isinstance(action, dict) and action.get("action") == "generate_world":
                            regenerate_world(action["width"], action["height"])
                    else:
                        mouse.start_paint()
                        if place_at_mouse(mouse_pos):
                            needs_redraw = True

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                mouse.stop_paint()

            if event.type == pygame.MOUSEMOTION and mouse.painting:
                if place_at_mouse(event.pos, interpolate=True):
                    needs_redraw = True

        if needs_redraw:
            screen.fill((0, 0, 0))
            scaled_map_width = max(1, int(round(map_width * tile_draw_size)))
            if (
                scaled_cache_dirty
                or scaled_map_cache is None
                or scaled_flower_cache is None
                or scaled_cache_width != scaled_map_width
                or scaled_cache_height != viewport_height
            ):
                scaled_map_cache = pygame.transform.scale(map_layer_surface, (scaled_map_width, viewport_height))
                scaled_flower_cache = pygame.transform.scale(flower_layer_surface, (scaled_map_width, viewport_height))
                scaled_cache_width = scaled_map_width
                scaled_cache_height = viewport_height
                scaled_cache_dirty = False
            map_screen_x = int(camera_x)
            map_screen_y = int(viewport_top + camera_y)
            screen.blit(scaled_map_cache, (map_screen_x, map_screen_y))
            screen.blit(scaled_flower_cache, (map_screen_x, map_screen_y))
            if not reduced_motion:
                draw_water_wave_lines(screen, map_screen_x, map_screen_y)
                draw_clouds(screen, map_screen_x, map_screen_y, scaled_map_width)
            menu.menu_draw(screen)
            pygame.display.flip()
            needs_redraw = False

    saved_path = save_map(mapa, map_path)
    print(f"Mapa zapisana: {saved_path}")
    pygame.quit()


if __name__ == "__main__":
    main()
