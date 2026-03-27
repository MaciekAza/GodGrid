import pygame

# Kolory
WHITE = (255, 255, 255)
BACKGROUND = (200, 200, 200)
BUTTON = (150, 150, 150)

# Pasek menu
MENU_HEIGHT = 50

# Przyciski
buttons = [
    {"rect": pygame.Rect(0, 0, 100, 30), "text": "X"}
]
font = None

def menu_draw(screen):
    global font
    if font is None:
        font = pygame.font.SysFont(None, 24)

    # Rysowanie paska tła
    pygame.draw.rect(screen, BACKGROUND, (0, 0, screen.get_width(), MENU_HEIGHT))

    # Guzik wyjscie
    button_width = 100
    buttons[0]["rect"] = pygame.Rect(screen.get_width() - button_width, 0, button_width, MENU_HEIGHT)
    pygame.draw.rect(screen, BUTTON, buttons[0]["rect"])
    text_surface = font.render(buttons[0]["text"], True, WHITE)
    text_rect = text_surface.get_rect(center=buttons[0]["rect"].center)
    screen.blit(text_surface, text_rect)