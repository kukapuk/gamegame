"""
bullet_decals.py — следы пуль на стенах.

Маленькие тёмные кратеры/царапины в мировых координатах.
Живут долго (30–60с), плавно исчезают в последние 3с.

Использование:
    from core.visual.bullet_decals import bullet_decals

    # при ударе пули в стену:
    bullet_decals.spawn(pos, bullet_vel)

    # в renderer (мировой буфер, ПОСЛЕ floor, ДО стен/акторов):
    bullet_decals.draw(world_surface, camera_offset)

    # в game_scene._update:
    bullet_decals.update(dt)
"""
from __future__ import annotations
import random
import math
import pygame


_FADE_TIME = 3.0      # секунды плавного исчезновения в конце жизни


class _Decal:
    __slots__ = ("x", "y", "surf", "half", "lifetime", "max_lifetime")

    def __init__(
        self,
        x: float, y: float,
        surf: pygame.Surface,
        lifetime: float,
    ) -> None:
        self.x = x
        self.y = y
        self.surf = surf
        self.half = surf.get_width() // 2
        self.lifetime = lifetime
        self.max_lifetime = lifetime


class BulletDecalSystem:
    """Следы пуль на стенах."""

    MAX_DECALS = 300   # старые удаляются при переполнении

    # Варианты форм декалей (рисуются на Surface один раз при спавне)
    _SIZE_RANGE   = (3, 7)
    _LIFETIME_RANGE = (30.0, 55.0)

    def __init__(self) -> None:
        self._decals: list[_Decal] = []

    def spawn(
        self,
        pos: pygame.math.Vector2,
        bullet_vel: pygame.math.Vector2,
        count: int = 1,
    ) -> None:
        """Создаёт 1–2 декали вблизи точки удара."""
        for _ in range(count):
            ox = random.uniform(-2, 2)
            oy = random.uniform(-2, 2)
            size = random.randint(*self._SIZE_RANGE)
            surf = self._make_decal_surf(size, bullet_vel)
            lifetime = random.uniform(*self._LIFETIME_RANGE)
            self._decals.append(_Decal(pos.x + ox, pos.y + oy, surf, lifetime))

        # обрезаем старые если переполнение
        if len(self._decals) > self.MAX_DECALS:
            self._decals = self._decals[-self.MAX_DECALS:]

    def clear(self) -> None:
        """Очистить при смене уровня."""
        self._decals.clear()

    def update(self, dt: float) -> None:
        alive = []
        for d in self._decals:
            d.lifetime -= dt
            if d.lifetime > 0:
                alive.append(d)
        self._decals = alive

    def draw(
        self,
        surface: pygame.Surface,
        camera_offset: pygame.math.Vector2,
    ) -> None:
        for d in self._decals:
            # плавное исчезновение в последние _FADE_TIME секунд
            if d.lifetime < _FADE_TIME:
                alpha = int(255 * d.lifetime / _FADE_TIME)
                # клонируем surf с нужной альфой
                tmp = d.surf.copy()
                tmp.set_alpha(alpha)
                sx = round(d.x - camera_offset.x) - d.half
                sy = round(d.y - camera_offset.y) - d.half
                surface.blit(tmp, (sx, sy))
            else:
                sx = round(d.x - camera_offset.x) - d.half
                sy = round(d.y - camera_offset.y) - d.half
                surface.blit(d.surf, (sx, sy))

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_decal_surf(
        size: int,
        bullet_vel: pygame.math.Vector2,
    ) -> pygame.Surface:
        """
        Рисует кратер/царапину.
        Форма зависит от угла пули: под углом — вытянутая царапина,
        прямо в стену — круглый кратер.
        """
        # угол удара (от нормали): 0° = перпендикулярно, 90° = скользящий
        if bullet_vel.length_squared() > 0:
            angle_deg = math.degrees(
                math.atan2(abs(bullet_vel.y), abs(bullet_vel.x))
            )
        else:
            angle_deg = 45.0

        # скользящий удар → вытянутая форма
        stretch = 1.0 + (angle_deg / 90.0) * 1.4
        w = max(3, round(size * stretch))
        h = size

        surf = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)

        # кратер: тёмное пятно с чуть более светлым центром
        cx, cy = (w + 2) // 2, (h + 2) // 2

        # внешний обод — почти чёрный
        pygame.draw.ellipse(surf, (20, 18, 15, 210), (1, 1, w, h))
        # внутренний — тёмно-серый (выбитый материал)
        iw, ih = max(1, w - 2), max(1, h - 2)
        pygame.draw.ellipse(surf, (45, 40, 35, 180),
                            (cx - iw // 2, cy - ih // 2, iw, ih))
        # центральная точка — самая тёмная
        if w > 3:
            pygame.draw.ellipse(surf, (10, 8, 6, 230),
                                (cx - 1, cy - 1, 2, 2))

        # случайные «трещины» расходятся от кратера
        num_cracks = random.randint(1, 3)
        for _ in range(num_cracks):
            crack_angle = random.uniform(0, math.pi * 2)
            crack_len   = random.uniform(2, size * 0.8)
            ex = cx + math.cos(crack_angle) * crack_len
            ey = cy + math.sin(crack_angle) * crack_len
            pygame.draw.line(surf, (30, 26, 22, 160),
                             (cx, cy), (round(ex), round(ey)), 1)

        # поворачиваем в направлении удара
        if bullet_vel.length_squared() > 0:
            rot_angle = -math.degrees(math.atan2(bullet_vel.y, bullet_vel.x))
            surf = pygame.transform.rotate(surf, rot_angle)

        return surf


# глобальный синглтон
bullet_decals = BulletDecalSystem()
