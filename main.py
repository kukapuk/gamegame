import pygame
from core.settings import Settings
from core.app import App


def main():
    pygame.init()
    App(Settings()).run()
    pygame.quit()


if __name__ == "__main__":
    main()
