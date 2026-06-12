import pygame
from core.settings import Settings
from core.game_scene import GameScene


class App:
    """
    Pygame-уровень: создаёт окно, держит clock, запускает цикл.
    Не знает ни об одном игровом объекте — только передаёт dt в сцену.

    Использование:
        App(Settings()).run()
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screen   = pygame.display.set_mode(
            (settings.screen_width, settings.screen_height)
        )
        pygame.display.set_caption(settings.title)
        self.clock = pygame.time.Clock()
        self.scene = GameScene(settings, self.screen, self.clock)

    def run(self) -> None:
        while True:
            dt = self.clock.tick(self.settings.fps) / 1000.0
            if not self.scene.update(dt):
                break
