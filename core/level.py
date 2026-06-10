import pygame
from core.wall import Wall


class Level:
    """
    Загружает уровень из .txt файла.
    Символы: w=стена, d=дверь, p=спавн игрока, пробел=пустота.
    """

    def __init__(self, path: str, tile_size: int) -> None:
        self.tile_size   = tile_size
        self.walls       = pygame.sprite.Group()
        self.all_sprites = pygame.sprite.Group()
        self.player_spawn: tuple[int, int] = (0, 0)
        self._load(path)

    def _load(self, path: str) -> None:
        with open(path, "r") as f:
            lines = f.readlines()

        ts = self.tile_size
        for row, line in enumerate(lines):
            for col, char in enumerate(line):
                x = col * ts
                y = row * ts
                if char == "w":
                    wall = Wall(x, y, ts, groups=[self.walls, self.all_sprites])
                elif char == "p":
                    self.player_spawn = (x + ts // 2, y + ts // 2)
