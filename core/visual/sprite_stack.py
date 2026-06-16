"""
sprite_stack.py — движок sprite stacking.

ШАГ 5 (полировка):
  - draw() принимает x_shear — горизонтальный сдвиг слоёв для иллюзии
    перспективного наклона (зависит от facing.x актора)
  - кэш округляет угол до 2° (вдвое меньше записей)
  - make_colored_stack добавляет outline на верхний слой
  - draw_shadow() рисует мягкую эллиптическую тень под объектом
"""

import math
import pygame


# ------------------------------------------------------------------ #
# SpriteStack
# ------------------------------------------------------------------ #

class SpriteStack:
    """Хранит слои и рисует их со смещением + опциональным X-shear."""

    def __init__(
        self,
        layers:     list[pygame.Surface],
        layer_step: float = 2.0,
    ) -> None:
        self.layers     = layers
        self.layer_step = layer_step
        self._cache: dict[int, list[pygame.Surface]] = {}

    # ---- построение -----------------------------------------------

    @classmethod
    def from_image(
        cls,
        image:      pygame.Surface,
        num_layers: int   = 8,
        layer_step: float = 2.0,
        layer_size: int | None = None,
    ) -> "SpriteStack":
        """
        Нарезать image на горизонтальные полосы.
        Формат MagicaVoxel: слои идут сверху вниз (верхушка → подошва).
        Мы читаем снизу вверх: i=0 = подошва (рисуется первой), i=n-1 = верхушка.
        """
        w, h    = image.get_size()
        slice_h = max(1, h // num_layers)
        layers  = []
        for i in range(num_layers):
            # MagicaVoxel: строка 0 в PNG = верхушка модели
            # нам нужно i=0 = подошва → берём с конца PNG
            row    = (num_layers - 1 - i)
            y_off  = row * slice_h
            # защита от выхода за границы
            if y_off + slice_h > h:
                continue
            strip  = image.subsurface(pygame.Rect(0, y_off, w, slice_h))
            sz     = layer_size or w
            scaled = pygame.transform.scale(strip, (sz, sz))
            layers.append(scaled)
        return cls(layers, layer_step)

    # ---- кэш -------------------------------------------------------

    def _get_rotated(self, angle_deg: int) -> list[pygame.Surface]:
        # округляем до 2° — вдвое меньше кэша, разница незаметна
        key = (angle_deg // 2) * 2
        if key not in self._cache:
            self._cache[key] = [
                pygame.transform.rotate(layer, key)
                for layer in self.layers
            ]
            if len(self._cache) > 180:
                del self._cache[next(iter(self._cache))]
        return self._cache[key]

    # ---- рисование -------------------------------------------------

    def draw(
        self,
        surface:   pygame.Surface,
        cx:        float,
        cy:        float,
        angle_deg: float,
        alpha:     int   = 255,
        x_shear:   float = 0.0,   # горизонтальный сдвиг на слой (пикселей)
    ) -> None:
        """
        Рисует стопку слоёв.
        x_shear — смещение по X на каждый слой (создаёт эффект наклона).
        Положительный = наклон вправо, отрицательный = влево.
        """
        angle_int = int(angle_deg) % 360
        rotated   = self._get_rotated(angle_int)
        n         = len(rotated)

        for i, layer in enumerate(rotated):
            y_off = -i * self.layer_step
            x_off =  i * x_shear
            r = layer.get_rect(center=(cx + x_off, cy + y_off))
            if alpha < 255:
                tmp = layer.copy()
                tmp.set_alpha(alpha)
                surface.blit(tmp, r)
            else:
                surface.blit(layer, r)


# ------------------------------------------------------------------ #
# Тень под объектом
# ------------------------------------------------------------------ #

def draw_shadow(
    surface:  pygame.Surface,
    cx:       float,
    cy:       float,
    radius_x: int   = 14,
    radius_y: int   = 6,
    alpha:    int   = 90,
) -> None:
    """
    Рисует мягкую эллиптическую тень под объектом.
    Вызывать ДО рисования стека — тень под всеми слоями.
    """
    w = radius_x * 2
    h = radius_y * 2
    shadow_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    # внешний эллипс прозрачнее, внутренний гуще
    for shrink, a in [(0, alpha // 3), (2, alpha // 2), (4, alpha)]:
        r = pygame.Rect(shrink, shrink // 2, w - shrink * 2, h - shrink)
        if r.width > 0 and r.height > 0:
            pygame.draw.ellipse(shadow_surf, (0, 0, 0, a), r)
    surface.blit(shadow_surf, (cx - radius_x, cy - radius_y // 2))


# ------------------------------------------------------------------ #
# Глобальный реестр
# ------------------------------------------------------------------ #

_registry: dict[str, SpriteStack] = {}


def get_stack(
    key:        str,
    image:      pygame.Surface,
    num_layers: int   = 8,
    layer_step: float = 2.0,
    layer_size: int | None = None,
) -> SpriteStack:
    if key not in _registry:
        _registry[key] = SpriteStack.from_image(
            image, num_layers=num_layers,
            layer_step=layer_step, layer_size=layer_size,
        )
    return _registry[key]


# ------------------------------------------------------------------ #
# Цветной стек для акторов
# ------------------------------------------------------------------ #

def make_colored_stack(
    color:      tuple,
    size:       int   = 28,
    num_layers: int   = 8,
    layer_step: float = 2.0,
) -> SpriteStack:
    """
    Строит стек из одного цвета.
    Нижние слои темнее, верхний — с тонкой тёмной обводкой (читаемость).
    """
    layers = []
    n      = num_layers
    for i in range(n):
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        t    = i / max(n - 1, 1)
        brightness = 0.50 + 0.50 * t

        r = min(255, int(color[0] * brightness))
        g = min(255, int(color[1] * brightness))
        b = min(255, int(color[2] * brightness))

        w_e = size - 2
        h_e = int(size * (0.85 - 0.15 * t))
        rect = pygame.Rect((size - w_e) // 2, (size - h_e) // 2, w_e, h_e)
        pygame.draw.ellipse(surf, (r, g, b), rect)

        # outline только на верхнем слое
        if i == n - 1:
            pygame.draw.ellipse(surf, (0, 0, 0, 160), rect, 2)

        layers.append(surf)

    return SpriteStack(layers, layer_step)


# ------------------------------------------------------------------ #
# Стек для стен
# ------------------------------------------------------------------ #

def make_wall_stack(
    tile_surf:  pygame.Surface,
    num_layers: int   = 6,
    layer_step: float = 3.5,
) -> SpriteStack:
    """
    Экструзия тайла стены вверх.
    Нижние слои темнее (боковые грани), верхний светлее (крыша).
    ШАГ 5: добавлена тонкая обводка верхнего слоя.
    """
    w, h   = tile_surf.get_size()
    layers = []
    n      = num_layers

    for i in range(n):
        t          = i / max(n - 1, 1)
        brightness = 0.45 + 0.55 * t

        layer = tile_surf.copy()

        if brightness < 1.0:
            dark  = pygame.Surface((w, h), pygame.SRCALPHA)
            alpha = int((1.0 - brightness) * 210)
            dark.fill((0, 0, 0, alpha))
            layer.blit(dark, (0, 0))

        # обводка верхнего слоя — помогает читать края стен
        if i == n - 1:
            pygame.draw.rect(layer, (0, 0, 0, 180), (0, 0, w, h), 2)

        layers.append(layer)

    return SpriteStack(layers, layer_step)
