import pygame
from actors.actor import Actor


class NPC(Actor):
    """
    Неигровой персонаж. Стоит на месте, имеет имя над головой.
    Взаимодействие через E при приближении — вызывает диалог.
    """

    INTERACT_RADIUS = 80.0
    NAME_COLOR      = (140, 180, 255)
    NAME_BG         = (10, 12, 20, 160)

    def __init__(
        self,
        pos: tuple[float, float],
        name: str,
        dialog_file: str = "",
        groups: list = (),
    ) -> None:
        super().__init__(
            pos=pos,
            size=28,
            color=(60, 100, 220),
            groups=groups,
        )
        self.name          = name
        self.dialog_file   = dialog_file
        self.velocity.update(0, 0)
        self._font         = pygame.font.SysFont("monospace", 12)
        self._name_surf    = self._font.render(name, True, self.NAME_COLOR)

    def is_in_interact_range(self, target_pos: pygame.math.Vector2) -> bool:
        return (self.pos - target_pos).length() <= self.INTERACT_RADIUS

    def update(self, dt: float, walls=None) -> None:
        pass

    def draw_name(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        screen_rect = self.rect.move(-camera_offset.x, -camera_offset.y)
        ns          = self._name_surf
        pad         = 4
        bx          = screen_rect.centerx - ns.get_width() // 2 - pad
        by          = screen_rect.top - ns.get_height() - 8

        bg = pygame.Surface((ns.get_width() + pad * 2, ns.get_height() + pad * 2), pygame.SRCALPHA)
        bg.fill(self.NAME_BG)
        surface.blit(bg, (bx, by))
        surface.blit(ns, (bx + pad, by + pad))
