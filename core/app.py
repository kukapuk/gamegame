import pygame
from core.settings import Settings
from core.scenes.menu_scene import MenuScene
from core.scenes.game_scene import GameScene
from core.scenes.pause_scene import PauseScene


class App:
    """
    Pygame-уровень: создаёт окно, держит clock, управляет сценами.
    Сцены общаются через строковые команды:
        "running"    — продолжаем текущую сцену
        "start_game" — запустить игру
        "pause"      — открыть паузу
        "resume"     — вернуться в игру
        "menu"       — вернуться в главное меню
        "quit"       — выйти
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screen   = pygame.display.set_mode(
            (settings.screen_width, settings.screen_height)
        )
        pygame.display.set_caption(settings.title)
        self.clock = pygame.time.Clock()

        self._menu:  MenuScene  = MenuScene(settings, self.screen)
        self._game:  GameScene  = None
        self._pause: PauseScene = None

        self._state: str = "menu"

    def run(self) -> None:
        while True:
            dt = self.clock.tick(self.settings.fps) / 1000.0
            cmd = self._tick(dt)
            if cmd == "quit":
                break

    def _tick(self, dt: float) -> str:
        if self._state == "menu":
            cmd = self._menu.update(dt)
            if cmd == "start_game":
                self._game  = GameScene(self.settings, self.screen, self.clock)
                self._state = "game"
            elif cmd == "quit":
                return "quit"

        elif self._state == "game":
            cmd = self._game.update(dt)
            if cmd == "pause":
                frozen = self.screen.copy()
                self._pause = PauseScene(self.settings, self.screen, frozen)
                self._state = "pause"
            elif cmd == "quit":
                return "quit"

        elif self._state == "pause":
            cmd = self._pause.update(dt)
            if cmd == "resume":
                self._pause = None
                self._state = "game"
            elif cmd == "menu":
                self._pause = None
                self._game  = None
                self._state = "menu"
            elif cmd == "quit":
                return "quit"

        return "running"
