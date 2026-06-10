import pygame


class Wall(pygame.sprite.Sprite):
    """Стена. Блокирует движение акторов и уничтожает пули."""

    COLOR = (60, 65, 80)

    def __init__(self, x: int, y: int, size: int, groups: list = ()) -> None:
        super().__init__(*groups)
        self.image = pygame.Surface((size, size))
        self.image.fill(self.COLOR)
        pygame.draw.rect(self.image, (70, 76, 92), (0, 0, size, size), 1)
        self.rect = self.image.get_rect(topleft=(x, y))
