"""
cover_system.py — система укрытий для военных и элиты.

Точки укрытий генерируются автоматически из стен уровня:
у каждой стены берём 4 точки — по одной с каждой стороны, чуть отступив.
Точка валидна как укрытие если:
  1. Между ней и игроком есть стена (стена загораживает)
  2. Точка не внутри другой стены

Враг запрашивает лучшую точку через find_cover(enemy_pos, player_pos, walls).
"""
from __future__ import annotations
import pygame


_SIDE_OFFSET = 52    # пикселей от края стены — где встать
_MIN_DIST    = 80    # минимум от врага (не брать точки вплотную к себе)
_MAX_DIST    = 420   # максимум от врага


class CoverSystem:
    def __init__(self) -> None:
        self._points: list[pygame.math.Vector2] = []

    # ── Public ────────────────────────────────────────────────────────

    def build(self, walls: pygame.sprite.Group) -> None:
        """Генерировать точки укрытий из стен. Вызывать после загрузки уровня."""
        self._points.clear()
        for wall in walls:
            r = wall.rect
            cx, cy = r.centerx, r.centery
            candidates = [
                pygame.math.Vector2(r.left  - _SIDE_OFFSET, cy),
                pygame.math.Vector2(r.right + _SIDE_OFFSET, cy),
                pygame.math.Vector2(cx, r.top    - _SIDE_OFFSET),
                pygame.math.Vector2(cx, r.bottom + _SIDE_OFFSET),
            ]
            for pt in candidates:
                # не внутри стены
                if not any(w.rect.collidepoint(pt.x, pt.y) for w in walls):
                    self._points.append(pt)

    def find_cover(
        self,
        enemy_pos:  pygame.math.Vector2,
        player_pos: pygame.math.Vector2,
        walls:      pygame.sprite.Group,
    ) -> pygame.math.Vector2 | None:
        """
        Найти лучшую точку укрытия для врага:
        - стена между точкой и игроком
        - в диапазоне дистанций от врага
        - ближайшая из валидных
        """
        best     = None
        best_d   = float("inf")

        for pt in self._points:
            d = (pt - enemy_pos).length()
            if d < _MIN_DIST or d > _MAX_DIST:
                continue
            if not self._wall_between(pt, player_pos, walls):
                continue
            if d < best_d:
                best_d = d
                best   = pt

        return best

    # ── Private ───────────────────────────────────────────────────────

    @staticmethod
    def _wall_between(
        a: pygame.math.Vector2,
        b: pygame.math.Vector2,
        walls: pygame.sprite.Group,
    ) -> bool:
        """True если хоть одна стена пересекает отрезок a→b."""
        from actors.geometry import segment_intersects_rect
        for wall in walls:
            if segment_intersects_rect(a, b, wall.rect):
                return True
        return False

    # ── Debug ─────────────────────────────────────────────────────────

    def draw_debug(
        self,
        surface: pygame.Surface,
        camera_offset: pygame.math.Vector2,
        player_pos: pygame.math.Vector2 = None,
        walls: pygame.sprite.Group = None,
    ) -> None:
        for pt in self._points:
            sx = round(pt.x - camera_offset.x)
            sy = round(pt.y - camera_offset.y)
            valid = (player_pos and walls and
                     self._wall_between(pt, player_pos, walls))
            color = (80, 200, 80) if valid else (100, 100, 100)
            pygame.draw.circle(surface, color, (sx, sy), 3)


# Глобальный экземпляр
cover_system = CoverSystem()
