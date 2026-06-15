"""
gl_renderer.py — moderngl пост-процессинг поверх pygame.

Pipeline каждого кадра:
  1. pygame рисует всё в offscreen Surface (как раньше)
  2. GLRenderer.render():
       a. Surface → GL текстура (u_game)
       b. Шейдер рисует полноэкранный квад:
            - Ray casting FOV  (конус фонарика + тени от стен)
            - Ambient вокруг игрока
            - Статичные источники света
            - Дульная вспышка
            - Виньетка + зернистость
       c. pygame.display.flip()

Стены передаются как 1D float-текстура: каждые 4 компоненты = (x1,y1,x2,y2).
Обновляется только при load_level.
"""
from __future__ import annotations
import math
import numpy as np
import moderngl
import pygame


# ── Вершинный шейдер — полноэкранный квад ────────────────────────────────────
_VERT = """
#version 330 core

in vec2 in_vert;
in vec2 in_uv;
out vec2 uv;

void main() {
    uv          = in_uv;
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

# ── Фрагментный шейдер ────────────────────────────────────────────────────────
_FRAG = """
#version 330 core

// ─── Входные данные ───────────────────────────────────────────────────────────
uniform sampler2D   u_game;          // кадр pygame
uniform sampler2D   u_walls;         // стены: каждый пиксель = (x1,y1,x2,y2) в мировых пикселях

uniform vec2  u_resolution;          // размер экрана в пикселях
uniform vec2  u_cam_offset;          // смещение камеры (camera.get_offset())
uniform vec2  u_player_pos;          // позиция игрока в мировых координатах
uniform float u_player_dir;          // направление взгляда (радианы)
uniform int   u_wall_count;          // количество стен

uniform float u_flashlight_fov;      // полный угол конуса (радианы)
uniform float u_flashlight_r;        // радиус фонарика
uniform float u_ambient_r;           // радиус ambient
uniform float u_darkness;            // 0..1  (0 = чёрный, 1 = видно полностью)

uniform float u_muzzle_t;            // 0 = нет вспышки, >0 = идёт
uniform float u_muzzle_dur;
uniform vec3  u_muzzle_color;
uniform float u_muzzle_r;

uniform float u_time;

// статичные источники (до 16)
uniform int   u_light_count;
uniform vec3  u_lights[16];          // (world_x, world_y, radius)

in  vec2 uv;
out vec4 fragColor;

// ─── Утилиты ──────────────────────────────────────────────────────────────────

float rand(vec2 co) {
    return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
}

float angleDiff(float a, float b) {
    float d = mod(a - b, 6.28318);
    return d > 3.14159 ? d - 6.28318 : d;
}

// пересечение луча (ox,oy)→dir с AABB (x1,y1,x2,y2)
// возвращает t параметр (расстояние), -1 если нет пересечения
float rayAABB(vec2 o, vec2 d, vec4 box) {
    vec2 inv = 1.0 / (d + vec2(1e-9));
    vec2 t1  = (box.xy - o) * inv;
    vec2 t2  = (box.zw - o) * inv;
    vec2 tmi = min(t1, t2);
    vec2 tma = max(t1, t2);
    float tmin = max(tmi.x, tmi.y);
    float tmax = min(tma.x, tma.y);
    if (tmax < 0.0 || tmin > tmax) return -1.0;
    return tmin > 0.0 ? tmin : tmax;
}

// пускаем луч из origin в направлении dir длиной maxR
// возвращает расстояние до ближайшей стены (или maxR)
float castRay(vec2 origin, vec2 dir, float maxR) {
    float best = maxR;
    for (int i = 0; i < u_wall_count; i++) {
        // читаем стену из текстуры: i-й пиксель, нормализованный UV
        float u = (float(i) + 0.5) / float(max(u_wall_count, 1));
        vec4  wall = texture(u_walls, vec2(u, 0.5));
        // стена в мировых координатах (денормализуем из [0,1])
        // хранится как есть в float32 — без нормализации
        float t = rayAABB(origin, dir, wall);
        if (t > 0.0 && t < best) best = t;
    }
    return best;
}

// яркость конуса фонарика в точке worldPos
float flashlightBrightness(vec2 worldPos) {
    vec2  delta = worldPos - u_player_pos;
    float dist  = length(delta);
    if (dist > u_flashlight_r) return 0.0;

    float angle = atan(delta.y, delta.x);
    float diff  = abs(angleDiff(angle, u_player_dir));
    float halfFov = u_flashlight_fov * 0.5;
    if (diff > halfFov + 0.05) return 0.0;

    // луч до этой точки — есть ли стена?
    vec2  dir = normalize(delta);
    float hit = castRay(u_player_pos, dir, dist + 1.0);
    if (hit < dist - 2.0) return 0.0;   // стена загородила

    // мягкий край конуса
    float edgeFade = 1.0 - smoothstep(halfFov * 0.75, halfFov, diff);
    // затухание по расстоянию
    float distFade = 1.0 - pow(dist / u_flashlight_r, 1.4);
    return edgeFade * distFade;
}

// ─── Главная функция ──────────────────────────────────────────────────────────
void main() {
    vec4 color = texture(u_game, uv);

    // мировые координаты текущего пикселя
    // GL UV: y=0 снизу, pygame: y=0 сверху — флипаем Y обратно
    vec2 screenPos = vec2(uv.x, 1.0 - uv.y) * u_resolution;
    vec2 worldPos  = screenPos + u_cam_offset;

    // ── Освещённость ──────────────────────────────────────────────────────
    float light = 0.0;

    // ambient вокруг игрока
    float ambDist = length(worldPos - u_player_pos);
    float pulse   = sin(u_time * 2.5) * 4.0;
    light = max(light,
        1.0 - smoothstep(0.0, u_ambient_r + pulse, ambDist));

    // фонарик
    light = max(light, flashlightBrightness(worldPos));

    // дульная вспышка
    if (u_muzzle_t > 0.0) {
        float t    = u_muzzle_t / u_muzzle_dur;
        vec2  fd   = vec2(cos(u_player_dir), sin(u_player_dir));
        vec2  fp   = u_player_pos + fd * 22.0;
        float dist = length(worldPos - fp);
        float mr   = u_muzzle_r * t;
        light = max(light, 1.0 - smoothstep(0.0, mr, dist));
        // цветной тint вспышки
        float fl = max(0.0, 1.0 - dist / mr) * t * t;
        color.rgb += u_muzzle_color * fl * 0.35;
    }

    // статичные источники света
    for (int i = 0; i < u_light_count; i++) {
        vec2  lpos = u_lights[i].xy;
        float lr   = u_lights[i].z;
        float ld   = length(worldPos - lpos);
        if (ld < lr) {
            float lbright = 1.0 - pow(ld / lr, 1.6);
            light = max(light, lbright * 0.9);
        }
    }

    // ── Тьма ──────────────────────────────────────────────────────────────
    float dark = 1.0 - u_darkness;   // базовый уровень темноты
    float alpha = dark * (1.0 - light);
    alpha = clamp(alpha, 0.0, 1.0);
    color.rgb = mix(color.rgb, vec3(0.0), alpha);

    // ── Виньетка ──────────────────────────────────────────────────────────
    vec2  vc  = uv - 0.5;
    float vig = 1.0 - smoothstep(0.45, 0.85, length(vc) * 1.4);
    color.rgb *= 0.85 + 0.15 * vig;

    // ── Зернистость ───────────────────────────────────────────────────────
    float noise = rand(uv + fract(u_time * 0.07)) * 0.03 - 0.015;
    color.rgb  += noise;

    fragColor = color;
}
"""

# ── Полноэкранный квад (NDC) ──────────────────────────────────────────────────
_QUAD = np.array([
    -1.0,  1.0,  0.0,  1.0,
    -1.0, -1.0,  0.0,  0.0,
     1.0, -1.0,  1.0,  0.0,
    -1.0,  1.0,  0.0,  1.0,
     1.0, -1.0,  1.0,  0.0,
     1.0,  1.0,  1.0,  1.0,
], dtype=np.float32)

_MAX_LIGHTS = 16


class GLRenderer:
    """
    Принимает pygame Surface (offscreen), применяет FOV + пост-эффекты, выводит на экран.
    Требует окно с pygame.OPENGL | pygame.DOUBLEBUF.
    """

    # ── Константы FOV (синхронизированы с VisionSystem) ──────────────────────
    FLASHLIGHT_FOV = math.radians(130.0)
    FLASHLIGHT_R   = 500.0
    AMBIENT_R      = 55.0
    DARKNESS       = 0.88        # 0..1

    def __init__(self, settings) -> None:
        self.sw = settings.screen_width
        self.sh = settings.screen_height

        self.ctx = moderngl.create_context()
        self.ctx.viewport = (0, 0, self.sw, self.sh)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        self.prog = self.ctx.program(
            vertex_shader=_VERT,
            fragment_shader=_FRAG,
        )

        self.vbo = self.ctx.buffer(data=_QUAD.tobytes())
        self.vao = self.ctx.vertex_array(
            self.prog,
            [(self.vbo, '2f 2f', 'in_vert', 'in_uv')],
        )

        # Текстура кадра pygame
        self.game_tex = self.ctx.texture((self.sw, self.sh), 4)
        self.game_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

        # Текстура стен (1D float32, RGBA32F = 4 floats per pixel)
        # Создаём заглушку на 1 пиксель — заменяем при load_walls
        self.wall_tex = self.ctx.texture((1, 1), 4, dtype='f4')
        self.wall_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self._wall_count = 0

        # Статичные источники
        self._lights: list[tuple] = []   # (world_x, world_y, radius)

        # Состояние FOV
        self._cam_offset  = (0.0, 0.0)
        self._player_pos  = (0.0, 0.0)
        self._player_dir  = 0.0
        self._flashlight  = True

        # Вспышка
        self._muzzle_t     = 0.0
        self._muzzle_dur   = 0.07
        self._muzzle_color = (1.0, 0.47, 0.12)
        self._muzzle_r     = 55.0

        self._time = 0.0

        # Инициализируем статичные uniforms
        self.prog['u_resolution'].value      = (float(self.sw), float(self.sh))
        self.prog['u_flashlight_fov'].value  = self.FLASHLIGHT_FOV
        self.prog['u_flashlight_r'].value    = self.FLASHLIGHT_R
        self.prog['u_ambient_r'].value       = self.AMBIENT_R
        self.prog['u_darkness'].value        = self.DARKNESS
        self.prog['u_muzzle_dur'].value      = self._muzzle_dur
        self.prog['u_game'].value            = 0
        self.prog['u_walls'].value           = 1

    # ── Данные уровня ─────────────────────────────────────────────────────────

    def load_walls(self, wall_rects: list) -> None:
        """Загружает список pygame.Rect стен в float-текстуру."""
        if not wall_rects:
            return

        n = len(wall_rects)
        # каждая стена = 4 float: x1, y1, x2, y2
        data = np.zeros((n, 4), dtype=np.float32)
        for i, r in enumerate(wall_rects):
            data[i] = (float(r.left), float(r.top),
                       float(r.right), float(r.bottom))

        # создаём 1D текстуру (n пикселей, 4 канала float32)
        self.wall_tex.release()
        self.wall_tex = self.ctx.texture((n, 1), 4, data=data.tobytes(), dtype='f4')
        self.wall_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self._wall_count = n
        self.prog['u_wall_count'].value = n

    def load_lights(self, lights: list) -> None:
        """Загружает статичные источники света. lights = list[LightSource]."""
        self._lights = []
        for src in lights[:_MAX_LIGHTS]:
            self._lights.append((src.pos.x, src.pos.y, src.radius * 0.75))

        count = len(self._lights)
        self.prog['u_light_count'].value = count
        # moderngl array uniform ожидает список кортежей [(x,y,r), ...]
        padded = list(self._lights) + [(0.0, 0.0, 0.0)] * (_MAX_LIGHTS - count)
        self.prog['u_lights'].value = padded

    # ── FOV состояние ─────────────────────────────────────────────────────────

    def set_fov(self, player_pos, player_dir: float,
                cam_offset, flashlight_on: bool) -> None:
        self._player_pos = (float(player_pos[0]), float(player_pos[1]))
        # pygame Y вниз → GLSL atan Y вниз тоже (worldPos флипнут) — dir без изменений
        self._player_dir = float(player_dir)
        self._cam_offset = (float(cam_offset[0]), float(cam_offset[1]))
        self._flashlight = flashlight_on

    def trigger_muzzle_flash(self, color=(1.0, 0.47, 0.12),
                              radius=55.0, duration=0.07) -> None:
        self._muzzle_t     = duration
        self._muzzle_dur   = duration
        self._muzzle_color = color
        self._muzzle_r     = radius
        self.prog['u_muzzle_dur'].value = duration

    def update(self, dt: float) -> None:
        self._muzzle_t = max(0.0, self._muzzle_t - dt)

    # ── Главный рендер ────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface, dt: float = 0.016) -> None:
        self._time += dt

        # pygame Surface → GL текстура
        raw = pygame.image.tobytes(surface, 'RGBA', True)   # True = flip Y
        self.game_tex.write(raw)

        # обновляем uniforms
        self.prog['u_time'].value       = self._time
        self.prog['u_cam_offset'].value = self._cam_offset
        self.prog['u_player_pos'].value = self._player_pos
        self.prog['u_player_dir'].value = self._player_dir

        # фонарик — если выключен, ставим очень маленький радиус
        fov = self.FLASHLIGHT_FOV if self._flashlight else 0.0
        self.prog['u_flashlight_fov'].value = fov

        self.prog['u_muzzle_t'].value       = self._muzzle_t
        self.prog['u_muzzle_color'].value   = self._muzzle_color
        self.prog['u_muzzle_r'].value       = self._muzzle_r

        # рисуем
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self.game_tex.use(0)
        self.wall_tex.use(1)
        self.vao.render(moderngl.TRIANGLES)

        pygame.display.flip()

    def destroy(self) -> None:
        self.game_tex.release()
        self.wall_tex.release()
        self.vbo.release()
        self.vao.release()
        self.prog.release()
