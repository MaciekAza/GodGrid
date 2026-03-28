import pygame
import menu
import os

char_to_tile = {
    "G": "grass",
    "W": "water",
    "F": "forest",
    "M": "mountain"
}

tile_colors = {
    "grass": (50, 200, 50),
    "water": (50, 50, 200),
    "forest": (20, 120, 20),
    "mountain": (100, 100, 100)
}

# wczytywanie mapy
def wczytaj_mape():
    mapa = []
    base_path = os.path.dirname(os.path.dirname(__file__))
    map_path = os.path.join(base_path, "data", "map.txt")
    with open(map_path, "r") as f:
        for linia in f:
            row = [char_to_tile[znak] for znak in linia.strip()]
            mapa.append(row)
    return mapa


def main():
    pygame.init()

    # Zmienne
    info = pygame.display.Info()
    screen_size = (info.current_w, info.current_h)

    mapa = wczytaj_mape()
    tile_size = 10
    zoom = 1.0
    min_zoom = 0.5
    max_zoom = 4.0

    map_width = len(mapa[0])
    map_height = len(mapa)

    # Setup
    screen = pygame.display.set_mode(screen_size)
    pygame.display.set_caption("GodGrid")
    clock = pygame.time.Clock()
    running = True

    screen_width, screen_height = screen_size

    # Kamera
    camera_x = (screen_width - map_width * tile_size * zoom) // 2
    camera_y = (screen_height - map_height * tile_size * zoom) // 2

    # Przesuwanie myszką
    dragging = False

    # Główna pętla
    while running:
        dt = clock.tick(60) / 1000.0

        # Obsługa zdarzeń
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()

                for btn in menu.buttons:
                    if btn["rect"].collidepoint(mouse_pos):
                        if btn["text"] == "X":
                            running = False
                        break
                else:
                    if event.button == 1:
                        dragging = True

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging = False

            if event.type == pygame.MOUSEMOTION:
                if dragging:
                    dx, dy = event.rel
                    camera_x += dx
                    camera_y += dy

            if event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()

                # Punkt pod myszką przed zoomem
                world_x = (mouse_x - camera_x) / zoom
                world_y = (mouse_y - camera_y) / zoom

                if event.y > 0:
                    zoom *= 1.1
                elif event.y < 0:
                    zoom /= 1.1

                zoom = max(min_zoom, min(max_zoom, zoom))

                # Ustawienie kamery tak, żeby zoom był pod myszką
                camera_x = mouse_x - world_x * zoom
                camera_y = mouse_y - world_y * zoom

            # Fallback dla starszych wersji pygame
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    world_x = (mouse_x - camera_x) / zoom
                    world_y = (mouse_y - camera_y) / zoom
                    zoom *= 1.1
                    zoom = max(min_zoom, min(max_zoom, zoom))
                    camera_x = mouse_x - world_x * zoom
                    camera_y = mouse_y - world_y * zoom

                if event.button == 5:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    world_x = (mouse_x - camera_x) / zoom
                    world_y = (mouse_y - camera_y) / zoom
                    zoom /= 1.1
                    zoom = max(min_zoom, min(max_zoom, zoom))
                    camera_x = mouse_x - world_x * zoom
                    camera_y = mouse_y - world_y * zoom

        # Ruch WASD
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

        # Rysowanie mapy
        screen.fill((0, 0, 0))

        tile_draw_size = tile_size * zoom

        # Widoczne fragmenty mapy
        start_x = max(0, int((-camera_x) / tile_draw_size) - 2)
        start_y = max(0, int((-camera_y) / tile_draw_size) - 2)
        end_x = min(map_width, int((screen_width - camera_x) / tile_draw_size) + 2)
        end_y = min(map_height, int((screen_height - camera_y) / tile_draw_size) + 2)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                tile = mapa[y][x]
                color = tile_colors.get(tile, (255, 0, 255))

                draw_x = int(camera_x + x * tile_draw_size)
                draw_y = int(camera_y + y * tile_draw_size)
                rect = pygame.Rect(draw_x, draw_y, int(tile_draw_size) + 1, int(tile_draw_size) + 1)

                pygame.draw.rect(screen, color, rect)

        # UI
        menu.menu_draw(screen)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()