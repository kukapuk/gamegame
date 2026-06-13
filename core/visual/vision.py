"""
vision.py — 2D FOV через scanline (равномерные лучи).

Подход: вместо ray-cast по вершинам стен — N равномерных лучей по конусу.
  - Нет проблем с epsilon/floating-point на стыках рёбер
  - Длинные стены работают корректно
  - Blur скрывает «ступенчатость» от дискретных лучей

Pipeline:
  1. Для каждого луча находим расстояние до ближайшей стены (pygame.Rect.clipline)
  2. Строим полигон из точек попадания
  3. Рисуем полигон в PIL grayscale-маску (половина разрешения)
  4. Радиальный градиент через numpy внутри полигона
  5. GaussianBlur → pygame.transform.scale → blit как оверлей

Два слоя:
  - floor layer  (DARKNESS=218) — между полом и спрайтами
  - sprite layer (alpha=110)    — поверх спрайтов, силуэты видны
"""

from __future__ import annotations
import math
import pygame
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from dataclasses import dataclass, field


# ──────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────

@dataclass
class LightSource:
    pos:       pygame.math.Vector2
    radius:    float = 200.0
    color:     tuple = (255, 200, 120)
    intensity: float = 1.0
    flicker:   bool  = False
    _flicker_phase: float = field(default=0.0, repr=False)


# ──────────────────────────────────────────────
# Ray casting через pygame.Rect.clipline
# ──────────────────────────────────────────────

def _cast_ray(ox: float, oy: float, angle: float,
              max_r: float, wall_rects: list) -> tuple[float, float]:
    """
    Пускает луч из (ox,oy) под углом angle длиной max_r.
    Возвращает точку первого попадания в стену (или конец луча).
    Использует pygame.Rect.clipline — быстро и надёжно.
    """
    dx = math.cos(angle) * max_r
    dy = math.sin(angle) * max_r
    ex, ey = ox + dx, oy + dy

    best_dist2 = max_r * max_r
    bx, by = ex, ey

    for rect in wall_rects:
        clip = rect.clipline(ox, oy, ex, ey)
        if clip:
            # clipline возвращает ((x1,y1),(x2,y2)) — берём ближнюю точку
            p = clip[0]
            d2 = (p[0] - ox) ** 2 + (p[1] - oy) ** 2
            if d2 < best_dist2:
                best_dist2 = d2
                bx, by = p[0], p[1]

    return bx, by


def _build_poly(ox: float, oy: float, direction: float,
                cone_half: float, radius: float,
                wall_rects: list, ray_count: int) -> list[tuple[int, int]]:
    """Строит полигон конуса видимости через N равномерных лучей."""
    pts = [(ox, oy)]
    step = (2 * cone_half) / (ray_count - 1)
    for i in range(ray_count):
        angle = direction - cone_half + step * i
        x, y = _cast_ray(ox, oy, angle, radius, wall_rects)
        pts.append((x, y))
    return pts


def _build_circle_poly(ox: float, oy: float, radius: float,
                       wall_rects: list, ray_count: int) -> list[tuple[int, int]]:
    """Полный круг (для точечных источников)."""
    pts = [(ox, oy)]
    step = 2 * math.pi / ray_count
    for i in range(ray_count):
        angle = step * i
        x, y = _cast_ray(ox, oy, angle, radius, wall_rects)
        pts.append((x, y))
    pts.append(pts[1])  # замыкаем
    return pts


# ──────────────────────────────────────────────
# VisionSystem
# ──────────────────────────────────────────────

class VisionSystem:

    DARKNESS        = 215
    FLASHLIGHT_FOV  = 130.0   # градусы
    FLASHLIGHT_R    = 500.0
    AMBIENT_R       = 55.0
    RAY_COUNT       = 120     # лучей конуса (больше = точнее тени)
    CIRCLE_RAYS     = 80      # лучей для точечных источников
    BLUR_R          = 6
    SPRITE_ALPHA    = 105     # прозрачность оверлея поверх спрайтов

    def __init__(self, settings) -> None:
        sw, sh = settings.screen_width, settings.screen_height
        self._sw, self._sh   = sw, sh
        self._hsw, self._hsh = sw // 2, sh // 2

        self._pil  = Image.new('L', (self._hsw, self._hsh), self.DARKNESS)
        self._draw = ImageDraw.Draw(self._pil)

        self._small   = pygame.Surface((self._hsw, self._hsh), pygame.SRCALPHA)
        self._overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        # отдельный surface для цветового tint конуса и вспышки
        self._glow    = pygame.Surface((sw, sh), pygame.SRCALPHA)

        self._wall_rects: list[pygame.Rect] = []
        self._static: list[LightSource] = []

        self._player_pos = pygame.math.Vector2(0, 0)
        self._player_dir = 0.0

        # мuzzle flash
        self._muzzle_t     = 0.0
        self._muzzle_color = (255, 120, 30)   # оранжево-красный по умолчанию
        self._muzzle_r     = 55.0
        self._muzzle_dur   = 0.07

        # пульсация ambient
        self._pulse_t = 0.0

        # фонарик вкл/выкл
        self.flashlight_on = True

        self._last_pos    = (-9999.0, -9999.0)
        self._last_dir    = -9999.0
        self._last_offset = (-9999.0, -9999.0)
        self._dirty       = True

    # ── Setup ──────────────────────────────────

    def load_level(self, level) -> None:
        self._wall_rects = [w.rect for w in level.walls]
        self._static = [
            LightSource(
                pos       = pygame.math.Vector2(ld["x"], ld["y"]),
                radius    = float(ld.get("radius", 180)),
                color     = _parse_color(ld.get("color", "#ffcc88")),
                intensity = float(ld.get("intensity", 0.85)),
                flicker   = bool(ld.get("flicker", False)),
            )
            for ld in getattr(level, "lights", [])
        ]
        self._dirty = True

    def set_player_flashlight(self, pos, aim_dir) -> None:
        self._player_pos = pygame.math.Vector2(pos)
        self._player_dir = math.atan2(aim_dir.y, aim_dir.x)

    def toggle_flashlight(self) -> None:
        self.flashlight_on = not self.flashlight_on
        self._dirty = True

    def trigger_muzzle_flash(
        self,
        color:    tuple = (255, 120, 30),
        radius:   float = 80.0,
        duration: float = 0.07,
    ) -> None:
        self._muzzle_t     = duration
        self._muzzle_color = color
        self._muzzle_r     = radius
        self._muzzle_dur   = duration

    def update(self, dt: float) -> None:
        self._muzzle_t = max(0.0, self._muzzle_t - dt)
        self._pulse_t += dt
        for src in self._static:
            if src.flicker:
                src._flicker_phase += dt * 9.0
                src.intensity = max(0.4, 0.75 + 0.25 * math.sin(
                    src._flicker_phase + math.cos(src._flicker_phase * 1.7)))
                self._dirty = True

    # ── Render ─────────────────────────────────

    def render_floor_layer(self, screen, offset, debug=False) -> None:
        """После пола/гильз, ДО спрайтов."""
        if debug:
            return
        self._rebuild(offset)
        screen.blit(self._overlay, (0, 0))
        # цветовой tint поверх оверлея через ADD
        if self._glow_dirty:
            self._rebuild_glow(offset)
        screen.blit(self._glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def render_sprite_layer(self, screen, offset, debug=False) -> None:
        """После спрайтов — силуэты видны в темноте."""
        if debug:
            return
        self._overlay.set_alpha(self.SPRITE_ALPHA)
        screen.blit(self._overlay, (0, 0))
        self._overlay.set_alpha(255)

    # ── Build ──────────────────────────────────

    def _rebuild(self, offset: pygame.math.Vector2) -> None:
        ox, oy = offset.x, offset.y
        px, py = self._player_pos.x, self._player_pos.y
        pdir   = self._player_dir

        moved  = abs(px - self._last_pos[0]) > 1.5 or abs(py - self._last_pos[1]) > 1.5
        turned = abs(self._angle_diff(pdir, self._last_dir)) > 0.015
        scroll = abs(ox - self._last_offset[0]) > 1.5 or abs(oy - self._last_offset[1]) > 1.5
        flash  = self._muzzle_t > 0

        self._glow_dirty = moved or turned or scroll or flash or self._dirty

        if not (moved or turned or scroll or flash or self._dirty):
            return

        self._last_pos    = (px, py)
        self._last_dir    = pdir
        self._last_offset = (ox, oy)
        self._dirty       = False

        S    = 0.5
        hsw  = self._hsw
        hsh  = self._hsh
        DARK = self.DARKNESS
        rects = self._wall_rects

        # ── PIL: темнота ────────────────────────
        self._draw.rectangle([0, 0, hsw, hsh], fill=DARK)

        # ── Фонарик (только если включён) ───────
        if self.flashlight_on:
            cone_half = math.radians(self.FLASHLIGHT_FOV / 2)
            poly_w = _build_poly(px, py, pdir, cone_half,
                                 self.FLASHLIGHT_R, rects, self.RAY_COUNT)
            self._draw_poly_gradient(poly_w, px, py, self.FLASHLIGHT_R,
                                     DARK, ox, oy, S)

        # ── Ambient (с пульсацией) ───────────────
        pulse = math.sin(self._pulse_t * 2.5) * 5.0   # ±5px
        self._draw_soft_circle(px, py, self.AMBIENT_R + pulse, DARK, ox, oy, S)

        # ── Дульная вспышка (резкая) ─────────────
        if self._muzzle_t > 0:
            t  = self._muzzle_t / self._muzzle_dur
            fd = pygame.math.Vector2(math.cos(pdir), math.sin(pdir))
            fp = self._player_pos + fd * 28
            # резкий круг — один эллипс без градиента
            r  = max(1, int(self._muzzle_r * t * S))
            cx = round((fp.x - ox) * S)
            cy = round((fp.y - oy) * S)
            self._draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=0)

        # ── Статичные источники ──────────────────
        for src in self._static:
            poly_w = _build_circle_poly(src.pos.x, src.pos.y,
                                        src.radius, rects, self.CIRCLE_RAYS)
            fill = int(DARK * (1.0 - src.intensity))
            self._draw_poly_flat(poly_w, fill, ox, oy, S)

        # ── Blur ────────────────────────────────
        blurred = self._pil.filter(ImageFilter.GaussianBlur(radius=self.BLUR_R))
        arr = np.array(blurred, dtype=np.uint8)

        pa = pygame.surfarray.pixels_alpha(self._small)
        pa[:] = arr.T
        del pa
        rgb = pygame.surfarray.pixels3d(self._small)
        rgb[:] = 0
        del rgb

        pygame.transform.scale(self._small, (self._sw, self._sh), self._overlay)

    # ── Draw helpers ───────────────────────────

    def _rebuild_glow(self, offset: pygame.math.Vector2) -> None:
        """Цветовой glow — только вспышка выстрела конусом."""
        self._glow.fill((0, 0, 0, 0))
        if self._muzzle_t <= 0:
            return

        ox, oy = offset.x, offset.y
        px, py = self._player_pos.x, self._player_pos.y
        pdir   = self._player_dir
        t      = self._muzzle_t / self._muzzle_dur

        # конусная вспышка — узкий конус в направлении выстрела
        cone_half = math.radians(14.0)   # узкий конус ±14°
        flash_r   = self._muzzle_r * 1.8 * t
        poly_w = _build_poly(px, py, pdir, cone_half,
                             flash_r, self._wall_rects, 30)
        if len(poly_w) >= 3:
            pts = [(round(x - ox), round(y - oy)) for x, y in poly_w]
            alpha_cone = int(55 * t * t)   # t² — плавнее спадает
            pygame.draw.polygon(self._glow, (*self._muzzle_color, alpha_cone), pts)

        # маленький яркий круг у ствола
        fd = pygame.math.Vector2(math.cos(pdir), math.sin(pdir))
        fp = self._player_pos + fd * 22
        cx = round(fp.x - ox)
        cy = round(fp.y - oy)
        r  = max(1, int(14 * t))
        pygame.draw.circle(self._glow, (*self._muzzle_color, int(130 * t * t)), (cx, cy), r)

    def _draw_poly_gradient(self, poly_world, cx, cy, radius,
                            dark, ox, oy, S):
        """Полигон с радиальным градиентом: прозрачно в центре, темно на краях."""
        if len(poly_world) < 3:
            return

        pts = [(round((x - ox) * S), round((y - oy) * S))
               for x, y in poly_world]

        # 1. Рисуем полигон полностью прозрачным (fill=0)
        self._draw.polygon(pts, fill=0)

        # 2. Numpy радиальный градиент только внутри полигона
        hcx = round((cx - ox) * S)
        hcy = round((cy - oy) * S)
        hr  = max(1, int(radius * S))
        hsw, hsh = self._hsw, self._hsh

        # маска полигона
        mask_img = Image.new('L', (hsw, hsh), 0)
        ImageDraw.Draw(mask_img).polygon(pts, fill=255)
        mask = np.array(mask_img, dtype=np.float32) / 255.0

        # радиальный градиент
        ys, xs = np.ogrid[0:hsh, 0:hsw]
        dist = np.sqrt((xs - hcx) ** 2 + (ys - hcy) ** 2, dtype=np.float32)
        t = np.clip(dist / hr, 0.0, 1.0)
        # плавный эффект — тёмно на краях конуса
        grad = (t ** 1.4 * dark * 0.7).astype(np.uint8)

        cur = np.array(self._pil, dtype=np.uint8)
        inside = mask > 0.5
        cur[inside] = np.clip(
            cur[inside].astype(np.int16) + grad[inside], 0, dark
        ).astype(np.uint8)
        self._pil = Image.fromarray(cur, mode='L')
        self._draw = ImageDraw.Draw(self._pil)

    def _draw_poly_flat(self, poly_world, fill, ox, oy, S):
        """Полигон с плоским fill (для точечных источников)."""
        if len(poly_world) < 3:
            return
        pts = [(round((x - ox) * S), round((y - oy) * S))
               for x, y in poly_world]
        self._draw.polygon(pts, fill=fill)

    def _draw_soft_circle(self, wx, wy, radius, dark, ox, oy, S):
        """Мягкий градиентный круг (ambient, вспышка)."""
        steps = 6
        for i in range(steps, 0, -1):
            t    = i / steps
            r    = max(1, int(radius * t * S))
            fill = int(dark * 0.6 * (1.0 - t))
            cx   = round((wx - ox) * S)
            cy   = round((wy - oy) * S)
            self._draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fill)

    @staticmethod
    def _angle_diff(a: float, b: float) -> float:
        d = (a - b) % (2 * math.pi)
        return d - 2 * math.pi if d > math.pi else d


# ──────────────────────────────────────────────

def _parse_color(s: str) -> tuple:
    s = s.lstrip("#")
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    return (255, 200, 120)
