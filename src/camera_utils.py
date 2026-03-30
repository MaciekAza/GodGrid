def clamp_camera(camera_x, camera_y, zoom, map_width, map_height, tile_size, screen_width, screen_height):
    map_pixel_width = map_width * tile_size * zoom
    map_pixel_height = map_height * tile_size * zoom

    bound_x_a = screen_width - map_pixel_width
    bound_x_b = 0
    min_x = min(bound_x_a, bound_x_b)
    max_x = max(bound_x_a, bound_x_b)

    bound_y_a = screen_height - map_pixel_height
    bound_y_b = 0
    min_y = min(bound_y_a, bound_y_b)
    max_y = max(bound_y_a, bound_y_b)

    camera_x = max(min_x, min(max_x, camera_x))
    camera_y = max(min_y, min(max_y, camera_y))
    return camera_x, camera_y


def zoom_at_cursor(
    mouse_x,
    mouse_y,
    delta,
    camera_x,
    camera_y,
    zoom,
    min_zoom,
    max_zoom,
    map_width,
    map_height,
    tile_size,
    screen_width,
    screen_height,
):
    world_x = (mouse_x - camera_x) / zoom
    world_y = (mouse_y - camera_y) / zoom

    if delta > 0:
        zoom *= 1.1
    elif delta < 0:
        zoom /= 1.1

    zoom = max(min_zoom, min(max_zoom, zoom))

    camera_x = mouse_x - world_x * zoom
    camera_y = mouse_y - world_y * zoom
    return clamp_camera(
        camera_x,
        camera_y,
        zoom,
        map_width,
        map_height,
        tile_size,
        screen_width,
        screen_height,
    ) + (zoom,)
