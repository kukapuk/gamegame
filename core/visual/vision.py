"""
vision.py — тонкая обёртка над GLRenderer для FOV.

Вся тяжёлая работа теперь в gl_renderer.py (GLSL шейдер).
Этот модуль:
  - хранит состояние фонарика / вспышки
  - предоставляет is_visible() для culling спрайтов
  - пробрасывает данные в GLRenderer
"""
from __future__ import annotations
import math
import pygame
from dataclasses import dataclass, field


@dataclass
class LightSource:
    pos:        pygame.math.Vector2
    radius:     float = 200.0
    color:      tuple = (255, 200, 120)
    intensity:  float = 1.0
    flicker:    bool  = False
    light_type: str   = "point"
    angle:      float = 0.0
    cone_deg:   float = 60.0
    _flicker_phase: float = field(default=0.0, repr=False)


class VisionSystem:

    FLASHLIGHT_FOV = 130.0    # градусы
    FLASHLIGHT_R   = 500.0
    AMBIENT_R      = 55.0

    def __init__(self, settings, gl_renderer=None) -> None:
        self._gl            = gl_renderer   # GLRenderer | None
        self._player_pos    = pygame.math.Vector2(0, 0)
        self._player_dir    = 0.0
        self.flashlight_on  = True
        self._static: list[LightSource] = []

        self._muzzle_t     = 0.0
        self._muzzle_dur   = 0.07
        self._muzzle_color = (255, 120, 30)
        self._muzzle_r     = 55.0

        self._pulse_t = 0.0

    def set_gl(self, gl_renderer) -> None:
        """Подключить GLRenderer (вызывается из app после создания)."""
        self._gl = gl_renderer

    # ── Setup ──────────────────────────────────────────────────────────

    def load_level(self, level) -> None:
        self._static = [
            LightSource(
                pos        = pygame.math.Vector2(ld["x"], ld["y"]),
                radius     = float(ld.get("radius", 180)),
                color      = _parse_color(ld.get("color", "#ffcc88")),
                intensity  = float(ld.get("intensity", 0.85)),
                flicker    = bool(ld.get("flicker", False)),
                light_type = str(ld.get("light_type", "point")),
            )
            for ld in getattr(level, "lights", [])
        ]
        if self._gl:
            self._gl.load_walls([w.rect for w in level.walls])
            self._gl.load_lights(self._static)

    # ── FOV state ──────────────────────────────────────────────────────

    def set_player_flashlight(self, pos, aim_dir) -> None:
        self._player_pos = pygame.math.Vector2(pos)
        self._player_dir = math.atan2(aim_dir.y, aim_dir.x)

    def toggle_flashlight(self) -> None:
        self.flashlight_on = not self.flashlight_on

    def trigger_muzzle_flash(self, color=(255, 120, 30),
                             radius=80.0, duration=0.07) -> None:
        self._muzzle_t     = duration
        self._muzzle_dur   = duration
        self._muzzle_color = color
        self._muzzle_r     = radius
        if self._gl:
            self._gl.trigger_muzzle_flash(
                color    = (color[0]/255, color[1]/255, color[2]/255),
                radius   = radius,
                duration = duration,
            )

    def update(self, dt: float, cam_offset=None) -> None:
        self._muzzle_t = max(0.0, self._muzzle_t - dt)
        self._pulse_t += dt

        # flicker
        for src in self._static:
            if src.flicker:
                src._flicker_phase += dt * 9.0
                src.intensity = max(0.4, 0.75 + 0.25 * math.sin(
                    src._flicker_phase + math.cos(src._flicker_phase * 1.7)))

        # пробрасываем состояние в GLRenderer
        if self._gl and cam_offset is not None:
            self._gl.set_fov(
                player_pos   = self._player_pos,
                player_dir   = self._player_dir,
                cam_offset   = cam_offset,
                flashlight_on= self.flashlight_on,
            )
            self._gl.update(dt)

    # ── Visibility culling (для renderer.py) ───────────────────────────

    def is_visible(self, world_pos) -> bool:
        """
        Быстрая проверка — попадает ли точка в зону видимости.
        Используется renderer.py чтобы не рисовать скрытые спрайты.
        """
        wp   = pygame.math.Vector2(world_pos)
        dist = (wp - self._player_pos).length()

        # ambient
        if dist <= self.AMBIENT_R + 8:
            return True

        # конус фонарика
        if self.flashlight_on and dist <= self.FLASHLIGHT_R:
            delta = wp - self._player_pos
            if delta.length() > 0:
                angle_to = math.atan2(delta.y, delta.x)
                diff = abs(_angle_diff(angle_to, self._player_dir))
                if diff <= math.radians(self.FLASHLIGHT_FOV / 2) + 0.05:
                    return True

        # статичные источники
        for src in self._static:
            if (wp - src.pos).length() <= src.radius * 0.75:
                return True

        return False

    # ── Совместимость с renderer.py (теперь ничего не рисуем здесь) ───

    def render_floor_layer(self, screen, offset, debug=False) -> None:
        pass   # FOV рисует шейдер

    def render_sprite_layer(self, screen, offset, debug=False) -> None:
        pass   # FOV рисует шейдер


# ── Helpers ────────────────────────────────────────────────────────────────────

def _angle_diff(a: float, b: float) -> float:
    d = (a - b) % (2 * math.pi)
    return d - 2 * math.pi if d > math.pi else d


def _parse_color(s: str) -> tuple:
    s = s.lstrip("#")
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    return (255, 200, 120)
