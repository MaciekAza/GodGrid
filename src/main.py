import pygame

def main():
    pygame.init()

    # variables
    info = pygame.display.Info()
    screen_size = (info.current_w, info.current_h)

    # setup
    screen = pygame.display.set_mode(screen_size)
    pygame.display.set_caption("GodGrid")
    running = True
    # main loop
    while running:
        # event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        screen.fill((255, 255, 255))
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()