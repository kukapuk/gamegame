import pygame


class Wall(pygame.sprite.Sprite):
    """Стена. Блокирует движение акторов и уничтожает пули."""

    COLOR = (60, 65, 80)

    # Параметры стека (ШАГ 4)
    SS_NUM_LAYERS  = 6
    SS_LAYER_STEP  = 3.5

    def __init__(self, x: int, y: int, size: int, groups: list = ()) -> None:
        super().__init__(*groups)
        self.image = pygame.Surface((size, size))
        self.image.fill(self.COLOR)
        pygame.draw.rect(self.image, (70, 76, 92), (0, 0, size, size), 1)
        self.rect = self.image.get_rect(topleft=(x, y))

        # Sprite stack строится лениво в build_sprite_stack()
        # (или сразу после установки tile image в Level._load_walls)
        self.sprite_stack = None

    def build_sprite_stack(self) -> None:
        """Строит стек из текущего self.image."""
        from core.visual.sprite_stack import make_wall_stack
        self.sprite_stack = make_wall_stack(
            self.image,
            num_layers = self.SS_NUM_LAYERS,
            layer_step = self.SS_LAYER_STEP,
        )

    def draw_stacked(
        self,
        surface: pygame.Surface,
        cx: float,
        cy: float,
    ) -> None:
        """Рисует стену как экструдированный блок."""
        if self.sprite_stack is None:
            self.build_sprite_stack()
        self.sprite_stack.draw(surface, cx, cy, angle_deg=0)
