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
    pos:        pygame.math.Vector2
    radius:     float = 200.0
    color:      tuple = (255, 200, 120)
    intensity:  float = 1.0
    flicker:    bool  = False
    light_type: str   = "point"   # "flat" | "point" | "spot"
    angle:      float = 0.0       # направление для spot (градусы)
    cone_deg:   float = 60.0      # угол конуса для spot
    _flicker_phase: float = field(default=0.0, repr=False)
    _buf_world:     object = field(default=None, repr=False)  # np.ndarray кеш


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
    BLUR_R          = 4
    SPRITE_ALPHA    = 105     # прозрачность оверлея поверх спрайтов

    def __init__(self, settings) -> None:
        sw, sh = settings.screen_width, settings.screen_height
        self._sw, self._sh   = sw, sh
        # 1/3 разрешения для маски — blur скрывает пикселизацию, но в 9x быстрее
        self._hsw = sw // 3
        self._hsh = sh // 3
        self._S   = 1.0 / 3.0

        self._pil  = Image.new('L', (self._hsw, self._hsh), self.DARKNESS)
        self._draw = ImageDraw.Draw(self._pil)

        self._small   = pygame.Surface((self._hsw, self._hsh), pygame.SRCALPHA)
        self._overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)

        # предвычисленная сетка координат (переиспользуется каждый кадр)
        ys, xs = np.mgrid[0:self._hsh, 0:self._hsw]
        self._xs = xs.astype(np.float32)
        self._ys = ys.astype(np.float32)
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
        cols = getattr(level, 'cols', 40)
        rows = getattr(level, 'rows', 30)
        ts   = getattr(level, 'tile_size', 64)
        # размер уровня в half-res пикселях
        self._level_w = round(cols * ts * 0.5)
        self._level_h = round(rows * ts * 0.5)
        self._static = [
            LightSource(
                pos        = pygame.math.Vector2(ld["x"], ld["y"]),
                radius     = float(ld.get("radius", 180)),
                color      = _parse_color(ld.get("color", "#ffcc88")),
                intensity  = float(ld.get("intensity", 0.85)),
                flicker    = bool(ld.get("flicker", False)),
                light_type = str(ld.get("light_type", "point")),
                angle      = float(ld.get("angle", 0.0)),
                cone_deg   = float(ld.get("cone_deg", 60.0)),
            )
            for ld in getattr(level, "lights", [])
        ]
        self._bake_static()
        self._dirty = True

    def _bake_static(self) -> None:
        """Предвычисляем буфер каждого источника в размере всего уровня (half-res).
        При рендере вырезаем нужный кусок по offset."""
        DARK  = self.DARKNESS
        rects = self._wall_rects
        S     = 0.5
        # размер буфера = весь уровень в half-res
        lw = self._level_w
        lh = self._level_h

        for src in self._static:
            self._bake_one_into(src, lw, lh, rects, DARK, S)

    def _bake_one_into(self, src, lw, lh, rects, DARK, S) -> None:
        if src.light_type == "spot":
            poly_w = _build_poly(src.pos.x, src.pos.y,
                                 math.radians(src.angle),
                                 math.radians(src.cone_deg / 2),
                                 src.radius, rects, self.CIRCLE_RAYS)
        else:
            poly_w = _build_circle_poly(src.pos.x, src.pos.y,
                                        src.radius, rects, self.CIRCLE_RAYS)
        if len(poly_w) < 3:
            src._buf_world = None
            return

        pts = [(round(x * S), round(y * S)) for x, y in poly_w]
        hcx = round(src.pos.x * S)
        hcy = round(src.pos.y * S)
        hr  = max(1, int(src.radius * S))

        if src.light_type == "flat":
            fill = int(DARK * (1.0 - src.intensity))
            src._buf_world = self._flat_light(pts, fill, lw, lh, DARK)
        else:
            src._buf_world = self._radial_light(
                pts, hcx, hcy, hr, lw, lh, DARK,
                power=1.6, center_val=int(DARK*(1-src.intensity)*0.05))



    def set_player_flashlight(self, pos, aim_dir) -> None:
        self._player_pos = pygame.math.Vector2(pos)
        self._player_dir = math.atan2(aim_dir.y, aim_dir.x)

    def is_visible(self, world_pos) -> bool:
        """
        True если точка видна игроку — попадает в конус фонарика,
        в ambient-радиус или в радиус любого статичного источника света.
        Стены не учитываются (дорого) — используем только угол и дистанцию.
        """
        wp = pygame.math.Vector2(world_pos)

        # ambient вокруг игрока — всегда видно рядом
        dist = (wp - self._player_pos).length()
        if dist <= self.AMBIENT_R + 8:
            return True

        # конус фонарика
        if self.flashlight_on and dist <= self.FLASHLIGHT_R:
            delta = wp - self._player_pos
            if delta.length() > 0:
                angle_to = math.atan2(delta.y, delta.x)
                diff = self._angle_diff(angle_to, self._player_dir)
                if abs(diff) <= math.radians(self.FLASHLIGHT_FOV / 2) + 0.05:
                    return True

        # статичные источники света
        for src in self._static:
            if (wp - src.pos).length() <= src.radius * 0.75:
                return True

        return False

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
                old_i = src.intensity
                src.intensity = max(0.4, 0.75 + 0.25 * math.sin(
                    src._flicker_phase + math.cos(src._flicker_phase * 1.7)))
                # перепекаем только если интенсивность изменилась заметно
                if abs(src.intensity - old_i) > 0.02:
                    self._bake_one(src)
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

    def _rebuild_glow(self, offset: pygame.math.Vector2) -> None:
        """Цветовой glow — только вспышка выстрела."""
        self._glow.fill((0, 0, 0, 0))
        ox, oy = offset.x, offset.y

        if self._muzzle_t <= 0:
            return

        px, py = self._player_pos.x, self._player_pos.y
        pdir   = self._player_dir
        t      = self._muzzle_t / self._muzzle_dur

        # конусная вспышка
        cone_half = math.radians(14.0)
        flash_r   = self._muzzle_r * 1.8 * t
        poly_w = _build_poly(px, py, pdir, cone_half,
                             flash_r, self._wall_rects, 30)
        if len(poly_w) >= 3:
            pts = [(round(x - ox), round(y - oy)) for x, y in poly_w]
            pygame.draw.polygon(self._glow, (*self._muzzle_color, int(55 * t * t)), pts)

        # маленький яркий круг у ствола
        fd = pygame.math.Vector2(math.cos(pdir), math.sin(pdir))
        fp = self._player_pos + fd * 22
        cx = round(fp.x - ox)
        cy = round(fp.y - oy)
        r  = max(1, int(14 * t))
        pygame.draw.circle(self._glow, (*self._muzzle_color, int(130 * t * t)), (cx, cy), r)


    # ── numpy light helpers ─────────────────────

    def _poly_mask(self, pts, w, h) -> np.ndarray:
        img = Image.new('L', (w, h), 0)
        ImageDraw.Draw(img).polygon(pts, fill=255)
        return np.array(img, dtype=np.uint8) > 127

    def _radial_light(self, pts, hcx, hcy, hr, w, h, dark,
                      power=1.4, center_val=0) -> np.ndarray:
        """Полигон с радиальным градиентом. np.minimum решает наложение."""
        mask = self._poly_mask(pts, w, h)
        ys, xs = np.ogrid[0:h, 0:w]
        dist = np.sqrt((xs - hcx)**2 + (ys - hcy)**2, dtype=np.float32)
        t    = np.clip(dist / hr, 0.0, 1.0)
        grad = (center_val + t**power * (dark - center_val)).astype(np.uint8)
        out  = np.full((h, w), dark, dtype=np.uint8)
        out[mask] = grad[mask]
        return out

    def _flat_light(self, pts, fill, w, h, dark) -> np.ndarray:
        mask = self._poly_mask(pts, w, h)
        out  = np.full((h, w), dark, dtype=np.uint8)
        out[mask] = fill
        return out

    def _radial_circle(self, cx, cy, r, w, h, dark, power=1.2) -> np.ndarray:
        ys, xs = np.ogrid[0:h, 0:w]
        dist = np.sqrt((xs - cx)**2 + (ys - cy)**2, dtype=np.float32)
        t    = np.clip(dist / max(r, 1), 0.0, 1.0)
        return (t**power * dark).astype(np.uint8)

    def _bake_one(self, src) -> None:
        """Перепекаем один источник (для flicker)."""
        self._bake_one_into(src, self._level_w, self._level_h,
                            self._wall_rects, self.DARKNESS, 0.5)

    def _rebuild(self, offset: pygame.math.Vector2) -> None:
        ox, oy = offset.x, offset.y
        px, py = self._player_pos.x, self._player_pos.y
        pdir   = self._player_dir

        moved  = abs(px - self._last_pos[0]) > 1.5 or abs(py - self._last_pos[1]) > 1.5
        turned = abs(self._angle_diff(pdir, self._last_dir)) > 0.015
        scroll = abs(ox - self._last_offset[0]) > 1.5 or abs(oy - self._last_offset[1]) > 1.5
        flash  = self._muzzle_t > 0

        self._glow_dirty = moved or turned or scroll or flash or self._dirty or bool(self._static)

        if not (moved or turned or scroll or flash or self._dirty):
            return

        self._last_pos    = (px, py)
        self._last_dir    = pdir
        self._last_offset = (ox, oy)
        self._dirty       = False

        S     = self._S
        hsw   = self._hsw
        hsh   = self._hsh
        DARK  = self.DARKNESS
        rects = self._wall_rects

        # Единый numpy буфер — тёмный фон
        buf = np.full((hsh, hsw), DARK, dtype=np.uint8)

        # ── Фонарик ─────────────────────────────
        if self.flashlight_on:
            cone_half = math.radians(self.FLASHLIGHT_FOV / 2)
            poly_w = _build_poly(px, py, pdir, cone_half,
                                 self.FLASHLIGHT_R, rects, self.RAY_COUNT)
            if len(poly_w) >= 3:
                pts = [(round((x-ox)*S), round((y-oy)*S)) for x,y in poly_w]
                hcx = round((px-ox)*S); hcy = round((py-oy)*S)
                hr  = max(1, int(self.FLASHLIGHT_R * S))
                buf = np.minimum(buf,
                    self._radial_light(pts, hcx, hcy, hr, hsw, hsh, DARK, power=1.4))

        # ── Ambient ──────────────────────────────
        pulse = math.sin(self._pulse_t * 2.5) * 5.0
        acx   = round((px-ox)*S); acy = round((py-oy)*S)
        amb_r = max(1, int((self.AMBIENT_R + pulse) * S))
        buf   = np.minimum(buf,
            self._radial_circle(acx, acy, amb_r, hsw, hsh, DARK, power=1.2))

        # ── Дульная вспышка ──────────────────────
        if self._muzzle_t > 0:
            t   = self._muzzle_t / self._muzzle_dur
            fd  = pygame.math.Vector2(math.cos(pdir), math.sin(pdir))
            fp  = self._player_pos + fd * 28
            fr  = max(1, int(self._muzzle_r * t * S))
            fcx = round((fp.x-ox)*S); fcy = round((fp.y-oy)*S)
            buf = np.minimum(buf,
                self._radial_circle(fcx, fcy, fr, hsw, hsh, DARK, power=0.5))

        # ── Статичные источники (из кеша) ────────
        sx0 = round(ox * S)
        sy0 = round(oy * S)
        sx1 = sx0 + hsw
        sy1 = sy0 + hsh
        for src in self._static:
            if src._buf_world is None:
                continue
            lh, lw = src._buf_world.shape
            # вырезаем видимый кусок уровня
            bx0 = max(0, sx0); bx1 = min(lw, sx1)
            by0 = max(0, sy0); by1 = min(lh, sy1)
            if bx0 >= bx1 or by0 >= by1:
                continue
            # куда в buf вставлять
            dx0 = bx0 - sx0; dy0 = by0 - sy0
            dx1 = dx0 + (bx1 - bx0); dy1 = dy0 + (by1 - by0)
            buf[dy0:dy1, dx0:dx1] = np.minimum(
                buf[dy0:dy1, dx0:dx1],
                src._buf_world[by0:by1, bx0:bx1]
            )

        # ── Blur + → overlay ─────────────────────
        pil  = Image.fromarray(buf, mode='L')
        blur = pil.filter(ImageFilter.GaussianBlur(radius=self.BLUR_R))
        arr  = np.array(blur, dtype=np.uint8)

        pa = pygame.surfarray.pixels_alpha(self._small)
        pa[:] = arr.T
        del pa
        rgb = pygame.surfarray.pixels3d(self._small)
        rgb[:] = 0
        del rgb

        pygame.transform.scale(self._small, (self._sw, self._sh), self._overlay)

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
