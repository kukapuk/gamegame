"""
muzzle_smoke.py — дым/пыль после выстрела.

Небольшое облачко у ствола, рассеивается за 0.4–0.9с.
Частицы расширяются, замедляются и исчезают.

Использование:
    from core.visual.muzzle_smoke import muzzle_smoke

    # сразу после выстрела, pos = позиция ствола в мире:
    muzzle_smoke.spawn(muzzle_pos, aim_dir, suppressed=False)

    # в renderer (мировой буфер, поверх акторов):
    muzzle_smoke.draw(world_surface, camera_offset)

    # в game_scene._update:
    muzzle_smoke.update(dt)
"""
from __future__ import annotations
import random
import math
import pygame


class _SmokeParticle:
    __slots__ = (
        "x", "y", "vx", "vy",
        "radius", "grow_rate",
        "lifetime", "max_lifetime",
        "alpha_start",
        "r", "g", "b",
    )

    def __init__(
        self,
        x: float, y: float,
        vx: float, vy: float,
        radius: float,
        grow_rate: float,
        lifetime: float,
        alpha_start: int,
        color: tuple[int, int, int],
    ) -> None:
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.radius = radius
        self.grow_rate = grow_rate
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.alpha_start = alpha_start
        self.r, self.g, self.b = color


class MuzzleSmokeSystem:
    """Дым у ствола после выстрела."""

    def __init__(self) -> None:
        self._particles: list[_SmokeParticle] = []

    def spawn(
        self,
        muzzle_pos: pygame.math.Vector2,
        aim_dir: pygame.math.Vector2,
        suppressed: bool = False,
    ) -> None:
        """
        muzzle_pos  — позиция кончика ствола (мировые координаты)
        aim_dir     — нормализованный вектор прицеливания
        suppressed  — глушитель: меньше дыма
        """
        count = random.randint(2, 4) if suppressed else random.randint(5, 9)

        # с глушителем дым светлее и меньше
        if suppressed:
            colors = [(170, 170, 165), (150, 148, 142), (185, 183, 178)]
            alpha_base = 55
            speed_mult = 0.5
            radius_base = (3.0, 6.0)
            lifetime_range = (0.18, 0.35)
        else:
            colors = [(130, 128, 120), (110, 108, 100), (150, 148, 140), (90, 88, 82)]
            alpha_base = 90
            speed_mult = 1.0
            radius_base = (4.0, 9.0)
            lifetime_range = (0.35, 0.75)

        if aim_dir.length_squared() > 0:
            base_angle = math.degrees(math.atan2(aim_dir.y, aim_dir.x))
        else:
            base_angle = 0.0

        for _ in range(count):
            # конус вперёд, немного в стороны
            spread = random.uniform(-40, 40)
            angle_rad = math.radians(base_angle + spread)
            speed = random.uniform(15, 55) * speed_mult
            vx = math.cos(angle_rad) * speed
            vy = math.sin(angle_rad) * speed

            radius = random.uniform(*radius_base)
            grow   = random.uniform(8, 22) * speed_mult
            lt     = random.uniform(*lifetime_range)
            alpha  = random.randint(alpha_base - 20, alpha_base + 20)

            # небольшое рассеивание позиции
            ox = random.uniform(-3, 3)
            oy = random.uniform(-3, 3)

            self._particles.append(_SmokeParticle(
                x=muzzle_pos.x + ox,
                y=muzzle_pos.y + oy,
                vx=vx, vy=vy,
                radius=radius,
                grow_rate=grow,
                lifetime=lt,
                alpha_start=alpha,
                color=random.choice(colors),
            ))

    def update(self, dt: float) -> None:
        alive = []
        for p in self._particles:
            p.lifetime -= dt
            if p.lifetime <= 0:
                continue
            # замедление
            drag = 1.0 - min(0.95, 4.0 * dt)
            p.vx *= drag
            p.vy *= drag
            p.x  += p.vx * dt
            p.y  += p.vy * dt
            # расширение
            p.radius += p.grow_rate * dt
            alive.append(p)
        self._particles = alive

    def draw(
        self,
        surface: pygame.Surface,
        camera_offset: pygame.math.Vector2,
    ) -> None:
        for p in self._particles:
            t = p.lifetime / p.max_lifetime          # 1 → 0
            alpha = int(p.alpha_start * t * t)       # квадратичное затухание
            if alpha <= 2:
                continue
            r = int(p.radius)
            if r < 1:
                continue
            diam = r * 2
            surf = pygame.Surface((diam, diam), pygame.SRCALPHA)
            pygame.draw.circle(
                surf, (p.r, p.g, p.b, alpha),
                (r, r), r
            )
            sx = round(p.x - camera_offset.x) - r
            sy = round(p.y - camera_offset.y) - r
            surface.blit(surf, (sx, sy))


# глобальный синглтон
muzzle_smoke = MuzzleSmokeSystem()
