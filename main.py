import pygame
from core.settings import Settings
from core.game import Game


def main():
    pygame.init()
    settings = Settings()
    game = Game(settings)
    game.run()
    pygame.quit()


if __name__ == "__main__":
    main()
