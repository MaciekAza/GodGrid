import pygame

import menu
from camera_utils import clamp_camera, zoom_at_cursor
from map_io import TILE_COLORS, load_map, map_path_from_project_root, save_map
from mouse_state import MouseState
from painting import apply_brush, apply_brush_line, screen_to_tile


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

    tile_size = 10
    zoom = 1.0
    min_zoom = 0.5
    max_zoom = 4.0

    map_width = len(mapa[0])
    map_height = len(mapa)

    screen = pygame.display.set_mode(screen_size)
    pygame.display.set_caption("GodGrid")
    clock = pygame.time.Clock()
    running = True

    camera_x = (viewport_width - map_width * tile_size * zoom) // 2
    camera_y = (viewport_height - map_height * tile_size * zoom) // 2
    camera_x, camera_y = clamp_camera(
        camera_x,
        camera_y,
        zoom,
        map_width,
        map_height,
        tile_size,
        viewport_width,
        viewport_height,
    )

    mouse = MouseState()

    def place_at_mouse(mouse_pos, interpolate=False):
        if menu.is_point_on_menu(mouse_pos):
            return

        tile_draw_size = tile_size * zoom
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
            return

        tile_id = menu.get_current_tool()["item_id"]
        brush_size = menu.get_brush_size()

        if mouse.last_paint_tile is None or not interpolate:
            apply_brush(mapa, tile_pos, tile_id, brush_size)
            mouse.last_paint_tile = tile_pos
            return

        apply_brush_line(mapa, mouse.last_paint_tile, tile_pos, tile_id, brush_size)
        mouse.last_paint_tile = tile_pos

    while running:
        dt = clock.tick_busy_loop(0) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
                saved_path = save_map(mapa, map_path)
                print(f"Mapa zapisana: {saved_path}")

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()

                if event.button == 1:
                    if menu.is_point_on_menu(mouse_pos):
                        action = menu.handle_mouse_down(mouse_pos)
                        if action == "quit":
                            running = False
                    else:
                        mouse.start_paint()
                        place_at_mouse(mouse_pos)

                if event.button == 3 and not menu.is_point_on_menu(mouse_pos):
                    mouse.start_drag()

                if event.button == 4:
                    if not menu.is_point_on_menu(mouse_pos):
                        camera_x, camera_y, zoom = zoom_at_cursor(
                            mouse_pos[0],
                            mouse_pos[1] - viewport_top,
                            1,
                            camera_x,
                            camera_y,
                            zoom,
                            min_zoom,
                            max_zoom,
                            map_width,
                            map_height,
                            tile_size,
                            viewport_width,
                            viewport_height,
                        )

                if event.button == 5:
                    if not menu.is_point_on_menu(mouse_pos):
                        camera_x, camera_y, zoom = zoom_at_cursor(
                            mouse_pos[0],
                            mouse_pos[1] - viewport_top,
                            -1,
                            camera_x,
                            camera_y,
                            zoom,
                            min_zoom,
                            max_zoom,
                            map_width,
                            map_height,
                            tile_size,
                            viewport_width,
                            viewport_height,
                        )

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    mouse.stop_paint()
                if event.button == 3:
                    mouse.stop_drag()

            if event.type == pygame.MOUSEMOTION:
                if mouse.dragging:
                    dx, dy = event.rel
                    camera_x += dx
                    camera_y += dy
                    camera_x, camera_y = clamp_camera(
                        camera_x,
                        camera_y,
                        zoom,
                        map_width,
                        map_height,
                        tile_size,
                        viewport_width,
                        viewport_height,
                    )

                if mouse.painting:
                    place_at_mouse(event.pos, interpolate=True)

            if event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                if not menu.is_point_on_menu((mouse_x, mouse_y)):
                    camera_x, camera_y, zoom = zoom_at_cursor(
                        mouse_x,
                        mouse_y - viewport_top,
                        event.y,
                        camera_x,
                        camera_y,
                        zoom,
                        min_zoom,
                        max_zoom,
                        map_width,
                        map_height,
                        tile_size,
                        viewport_width,
                        viewport_height,
                    )

        keys = pygame.key.get_pressed()
        move_speed = 500 * zoom

        if keys[pygame.K_a]:
            camera_x += move_speed * dt
        if keys[pygame.K_d]:
            camera_x -= move_speed * dt
        if keys[pygame.K_w]:
            camera_y += move_speed * dt
        if keys[pygame.K_s]:
            camera_y -= move_speed * dt

        camera_x, camera_y = clamp_camera(
            camera_x,
            camera_y,
            zoom,
            map_width,
            map_height,
            tile_size,
            viewport_width,
            viewport_height,
        )

        if mouse.painting:
            place_at_mouse(pygame.mouse.get_pos(), interpolate=True)

        screen.fill((0, 0, 0))

        tile_draw_size = tile_size * zoom
        start_x = max(0, int((-camera_x) / tile_draw_size) - 2)
        start_y = max(0, int((-camera_y) / tile_draw_size) - 2)
        end_x = min(map_width, int((viewport_width - camera_x) / tile_draw_size) + 2)
        end_y = min(map_height, int((viewport_height - camera_y) / tile_draw_size) + 2)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                tile = mapa[y][x]
                color = TILE_COLORS.get(tile, (255, 0, 255))

                draw_x = int(camera_x + x * tile_draw_size)
                draw_y = int(viewport_top + camera_y + y * tile_draw_size)
                rect = pygame.Rect(draw_x, draw_y, int(tile_draw_size) + 1, int(tile_draw_size) + 1)
                pygame.draw.rect(screen, color, rect)

        menu.menu_draw(screen)
        pygame.display.flip()

    saved_path = save_map(mapa, map_path)
    print(f"Mapa zapisana: {saved_path}")
    pygame.quit()


if __name__ == "__main__":
    main()
