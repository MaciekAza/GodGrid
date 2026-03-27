import pygame
import menu

def main():
    pygame.init()

    # Zmienne
    info = pygame.display.Info()
    screen_size = (info.current_w, info.current_h)

    # Setup
    screen = pygame.display.set_mode(screen_size)
    pygame.display.set_caption("GodGrid")
    running = True

    # Główna pętla
    while running:
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

        # Aktualizacje ekranu
        screen.fill((255, 255, 255))
        menu.menu_draw(screen)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()