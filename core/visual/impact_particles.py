"""
impact_particles.py — частицы при попадании пуль.

Три вида:
    spawn_wall_hit(pos, bullet_vel)   — кирпичная пыль (серо-коричневые)
    spawn_armor_hit(pos, bullet_vel)  — броня не пробита (серые металлические)
    spawn_flesh_hit(pos, bullet_vel)  — пробитие / кровь (красные)

Все частицы живут < 0.4s, не привязаны к камере — хранят мировые координаты.
Рендерятся в мировом буфере перед HUD.

Использование:
    from core.visual.impact_particles import impact_particles

    # в combat_manager:
    impact_particles.spawn_wall_hit(bullet.pos, bullet.velocity)
    impact_particles.spawn_armor_hit(pos, bullet.velocity)
    impact_particles.spawn_flesh_hit(pos, bullet.velocity)

    # в renderer (мировой буфер):
    impact_particles.draw(world_surface, camera_offset)

    # в game_scene._update:
    impact_particles.update(dt)
"""
from __future__ import annotations
import random
import math
import pygame


class _Particle:
    __slots__ = (
        "x", "y", "vx", "vy",
        "lifetime", "max_lifetime",
        "size", "r", "g", "b",
    )

    def __init__(
        self,
        x: float, y: float,
        vx: float, vy: float,
        lifetime: float,
        size: int,
        color: tuple[int, int, int],
    ) -> None:
        self.x  = x;  self.y  = y
        self.vx = vx; self.vy = vy
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.size = size
        self.r, self.g, self.b = color


class ImpactParticleSystem:
    """Singleton-like менеджер. Импортируй готовый объект `impact_particles`."""

    GRAVITY = 180.0   # px/s² — слабая гравитация

    def __init__(self) -> None:
        self._particles: list[_Particle] = []

    # ------------------------------------------------------------------ #
    # Public spawn API
    # ------------------------------------------------------------------ #

    def spawn_wall_hit(
        self,
        pos: pygame.math.Vector2,
        bullet_vel: pygame.math.Vector2,
        count: int = 8,
    ) -> None:
        """Серо-коричневая пыль стены/кирпича."""
        self._spawn(
            pos, bullet_vel, count,
            colors=[(170, 155, 130), (140, 128, 110), (100, 90, 75), (200, 185, 165)],
            speed_min=40, speed_max=130,
            lifetime_min=0.15, lifetime_max=0.35,
            size_range=(2, 4),
            spread=150,
        )

    def spawn_armor_hit(
        self,
        pos: pygame.math.Vector2,
        bullet_vel: pygame.math.Vector2,
        count: int = 7,
    ) -> None:
        """Серые металлические искры — броня не пробита."""
        self._spawn(
            pos, bullet_vel, count,
            colors=[(180, 180, 185), (210, 210, 215), (130, 130, 135), (255, 240, 180)],
            speed_min=60, speed_max=160,
            lifetime_min=0.10, lifetime_max=0.28,
            size_range=(1, 3),
            spread=140,
        )

    def spawn_flesh_hit(
        self,
        pos: pygame.math.Vector2,
        bullet_vel: pygame.math.Vector2,
        count: int = 9,
    ) -> None:
        """Красные брызги — пробитие брони / попадание по плоти."""
        self._spawn(
            pos, bullet_vel, count,
            colors=[(180, 20, 20), (210, 40, 30), (140, 10, 10), (220, 80, 60)],
            speed_min=50, speed_max=140,
            lifetime_min=0.18, lifetime_max=0.38,
            size_range=(2, 4),
            spread=160,
        )

    # ------------------------------------------------------------------ #
    # Update / Draw
    # ------------------------------------------------------------------ #

    def update(self, dt: float) -> None:
        alive = []
        for p in self._particles:
            p.lifetime -= dt
            if p.lifetime <= 0:
                continue
            p.x  += p.vx * dt
            p.y  += p.vy * dt
            p.vy += self.GRAVITY * dt
            alive.append(p)
        self._particles = alive

    def draw(
        self,
        surface: pygame.Surface,
        camera_offset: pygame.math.Vector2,
    ) -> None:
        for p in self._particles:
            alpha = max(0, int(255 * p.lifetime / p.max_lifetime))
            sx = round(p.x - camera_offset.x)
            sy = round(p.y - camera_offset.y)
            sz = p.size
            # быстро рисуем маленький квадрат с альфой
            surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
            surf.fill((p.r, p.g, p.b, alpha))
            surface.blit(surf, (sx - sz // 2, sy - sz // 2))

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _spawn(
        self,
        pos: pygame.math.Vector2,
        bullet_vel: pygame.math.Vector2,
        count: int,
        colors: list[tuple[int, int, int]],
        speed_min: float,
        speed_max: float,
        lifetime_min: float,
        lifetime_max: float,
        size_range: tuple[int, int],
        spread: float,          # половина конуса разлёта в градусах
    ) -> None:
        # базовый угол — ПРОТИВ направления пули (от точки удара наружу)
        if bullet_vel.length_squared() > 0:
            base_angle = math.degrees(math.atan2(-bullet_vel.y, -bullet_vel.x))
        else:
            base_angle = random.uniform(0, 360)

        for _ in range(count):
            angle_deg = base_angle + random.uniform(-spread / 2, spread / 2)
            angle_rad = math.radians(angle_deg)
            speed     = random.uniform(speed_min, speed_max)
            vx = math.cos(angle_rad) * speed
            vy = math.sin(angle_rad) * speed
            # небольшое рассеивание позиции
            ox = random.uniform(-3, 3)
            oy = random.uniform(-3, 3)
            self._particles.append(_Particle(
                x=pos.x + ox, y=pos.y + oy,
                vx=vx, vy=vy,
                lifetime=random.uniform(lifetime_min, lifetime_max),
                size=random.randint(size_range[0], size_range[1]),
                color=random.choice(colors),
            ))


# Глобальный синглтон — импортировать отовсюду
impact_particles = ImpactParticleSystem()
