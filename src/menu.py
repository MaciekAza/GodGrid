import pygame

MENU_HEIGHT = 82

TOPBAR_BG = (24, 27, 34)
TOPBAR_BG_2 = (31, 35, 44)
TOPBAR_BORDER = (70, 78, 96)
ITEM_ACTIVE = (100, 132, 214)
ITEM_IDLE = (56, 64, 80)
PANEL_BG = (34, 39, 49)
CLOSE_IDLE = (120, 54, 61)
CLOSE_HOVER = (164, 66, 77)
DOT_COLOR = (236, 240, 248)

TOOL_LIBRARY = {
    "blocks": [
        {"id": "grass", "color": (50, 200, 50)},
        {"id": "water", "color": (50, 50, 200)},
        {"id": "forest", "color": (20, 120, 20)},
        {"id": "mountain", "color": (100, 100, 100)},
    ]
}

font = None
ui_rects = {
    "close": pygame.Rect(0, 0, 0, 0),
    "items": [],
    "brush_toggle": pygame.Rect(0, 0, 0, 0),
    "brush_options": [],
    "brush_panel": pygame.Rect(0, 0, 0, 0),
}

selected_item_id = TOOL_LIBRARY["blocks"][0]["id"]
brush_size = 1
brush_menu_open = False
BRUSH_SIZES = [1, 3, 6, 10]
BRUSH_DOT_RADIUS = {1: 4, 3: 8, 6: 12, 10: 16}


def _ensure_fonts():
    global font
    if font is None:
        font = pygame.font.SysFont("segoeui", 22)


def _get_item_color(item_id):
    for item in TOOL_LIBRARY["blocks"]:
        if item["id"] == item_id:
            return item["color"]
    return (255, 0, 255)


def is_point_on_menu(pos):
    if pos[1] <= MENU_HEIGHT:
        return True

    if brush_menu_open and ui_rects["brush_panel"].collidepoint(pos):
        return True

    return False


def get_current_tool():
    return {
        "category": "blocks",
        "item_id": selected_item_id,
        "color": _get_item_color(selected_item_id),
    }


def get_brush_size():
    return brush_size


def hide_brush_menu():
    global brush_menu_open
    brush_menu_open = False


def handle_mouse_down(pos):
    global selected_item_id, brush_size, brush_menu_open

    if ui_rects["close"].collidepoint(pos):
        return "quit"

    if ui_rects["brush_toggle"].collidepoint(pos):
        brush_menu_open = not brush_menu_open
        return "handled"

    if brush_menu_open:
        for brush in ui_rects["brush_options"]:
            if brush["rect"].collidepoint(pos):
                brush_size = brush["size"]
                brush_menu_open = False
                return "handled"

    for item in ui_rects["items"]:
        if item["rect"].collidepoint(pos):
            selected_item_id = item["id"]
            return "handled"

    if brush_menu_open and not ui_rects["brush_panel"].collidepoint(pos):
        brush_menu_open = False

    return "handled"


def menu_draw(screen):
    _ensure_fonts()
    width = screen.get_width()

    pygame.draw.rect(screen, TOPBAR_BG, (0, 0, width, MENU_HEIGHT))
    pygame.draw.rect(screen, TOPBAR_BG_2, (0, MENU_HEIGHT // 2, width, MENU_HEIGHT // 2))
    pygame.draw.line(screen, TOPBAR_BORDER, (0, MENU_HEIGHT - 1), (width, MENU_HEIGHT - 1), 2)

    close_rect = pygame.Rect(width - 72, 12, 56, 56)
    mouse_pos = pygame.mouse.get_pos()
    close_color = CLOSE_HOVER if close_rect.collidepoint(mouse_pos) else CLOSE_IDLE
    pygame.draw.rect(screen, close_color, close_rect, border_radius=10)
    pygame.draw.rect(screen, TOPBAR_BORDER, close_rect, width=1, border_radius=10)
    close_label = font.render("X", True, DOT_COLOR)
    screen.blit(close_label, close_label.get_rect(center=close_rect.center))

    brush_toggle_rect = pygame.Rect(close_rect.x - 60, 16, 48, 48)
    toggle_color = ITEM_ACTIVE if brush_menu_open else ITEM_IDLE
    pygame.draw.rect(screen, toggle_color, brush_toggle_rect, border_radius=10)
    pygame.draw.rect(screen, TOPBAR_BORDER, brush_toggle_rect, width=1, border_radius=10)

    current_radius = BRUSH_DOT_RADIUS.get(brush_size, 6)
    pygame.draw.circle(screen, DOT_COLOR, brush_toggle_rect.center, current_radius)

    items = []
    item_size = 34
    item_x = 20
    item_y = 24
    gap = 10

    for tool in TOOL_LIBRARY["blocks"]:
        rect = pygame.Rect(item_x, item_y, item_size, item_size)
        active = tool["id"] == selected_item_id
        shell_color = ITEM_ACTIVE if active else ITEM_IDLE
        pygame.draw.rect(screen, shell_color, rect, border_radius=8)
        pygame.draw.rect(screen, TOPBAR_BORDER, rect, width=1, border_radius=8)

        swatch_rect = rect.inflate(-8, -8)
        pygame.draw.rect(screen, tool["color"], swatch_rect, border_radius=4)
        pygame.draw.rect(screen, TOPBAR_BORDER, swatch_rect, width=1, border_radius=4)

        items.append({"id": tool["id"], "rect": rect})
        item_x += item_size + gap

    brush_options = []
    panel_rect = pygame.Rect(0, 0, 0, 0)

    if brush_menu_open:
        option_w = 56
        option_h = 48
        option_gap = 6
        panel_w = option_w + 12
        panel_h = 8 + len(BRUSH_SIZES) * option_h + (len(BRUSH_SIZES) - 1) * option_gap + 8
        panel_rect = pygame.Rect(brush_toggle_rect.x - 6, brush_toggle_rect.bottom + 6, panel_w, panel_h)

        pygame.draw.rect(screen, PANEL_BG, panel_rect, border_radius=10)
        pygame.draw.rect(screen, TOPBAR_BORDER, panel_rect, width=1, border_radius=10)

        oy = panel_rect.y + 8
        for size in BRUSH_SIZES:
            rect = pygame.Rect(panel_rect.x + 6, oy, option_w, option_h)
            active = size == brush_size
            color = ITEM_ACTIVE if active else ITEM_IDLE
            pygame.draw.rect(screen, color, rect, border_radius=8)
            pygame.draw.rect(screen, TOPBAR_BORDER, rect, width=1, border_radius=8)

            dot_radius = BRUSH_DOT_RADIUS.get(size, 6)
            pygame.draw.circle(screen, DOT_COLOR, rect.center, dot_radius)

            brush_options.append({"size": size, "rect": rect})
            oy += option_h + option_gap

    ui_rects["items"] = items
    ui_rects["brush_toggle"] = brush_toggle_rect
    ui_rects["brush_options"] = brush_options
    ui_rects["brush_panel"] = panel_rect
    ui_rects["close"] = close_rect
