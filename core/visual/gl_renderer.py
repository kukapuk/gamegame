"""
gl_renderer.py — moderngl пост-процессинг поверх pygame.

Pipeline:
  Pass 1 (FOV + heat haze) : game_tex   → fov_fb
  Pass 2 (blur horizontal) : fov_fb     → blur_h_fb   (bloom)
  Pass 3 (blur vertical)   : blur_h_fb  → blur_v_fb   (bloom)
  Pass 4 (composite)       : fov_fb + blur_v_fb → экран
                             + chromatic aberration при ранении
                             + виньетка + зернистость
"""
from __future__ import annotations
import math
import numpy as np
import moderngl
import pygame

# ── Общий вершинный шейдер ────────────────────────────────────────────────────
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

# ── Pass 1: FOV + heat haze ───────────────────────────────────────────────────
_FRAG_FOV = """
#version 330 core

uniform sampler2D u_game;
uniform sampler2D u_walls;
uniform vec2  u_resolution;
uniform vec2  u_cam_offset;
uniform vec2  u_player_pos;
uniform float u_player_dir;
uniform int   u_wall_count;
uniform float u_flashlight_fov;
uniform float u_flashlight_r;
uniform float u_ambient_r;
uniform float u_darkness;
uniform float u_muzzle_t;
uniform float u_muzzle_dur;
uniform vec3  u_muzzle_color;
uniform float u_muzzle_r;
uniform float u_time;
uniform int   u_light_count;
uniform vec3  u_lights[16];

// heat haze
uniform float u_haze_strength;   // 0 = выкл, >0 = интенсивность

in  vec2 uv;
out vec4 fragColor;

float rand(vec2 co) {
    return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
}

float angleDiff(float a, float b) {
    float d = mod(a - b, 6.28318);
    return d > 3.14159 ? d - 6.28318 : d;
}

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

float castRay(vec2 origin, vec2 dir, float maxR) {
    float best = maxR;
    for (int i = 0; i < u_wall_count; i++) {
        float u  = (float(i) + 0.5) / float(max(u_wall_count, 1));
        vec4  wall = texture(u_walls, vec2(u, 0.5));
        float t  = rayAABB(origin, dir, wall);
        if (t > 0.0 && t < best) best = t;
    }
    return best;
}

float flashlightBrightness(vec2 worldPos) {
    vec2  delta = worldPos - u_player_pos;
    float dist  = length(delta);
    if (dist > u_flashlight_r) return 0.0;
    float angle   = atan(delta.y, delta.x);
    float diff    = abs(angleDiff(angle, u_player_dir));
    float halfFov = u_flashlight_fov * 0.5;
    if (diff > halfFov + 0.05) return 0.0;
    vec2  dir = normalize(delta);
    float hit = castRay(u_player_pos, dir, dist + 1.0);
    if (hit < dist - 2.0) return 0.0;
    float edgeFade = 1.0 - smoothstep(halfFov * 0.75, halfFov, diff);
    float distFade = 1.0 - pow(dist / u_flashlight_r, 1.4);
    return edgeFade * distFade;
}

void main() {
    // ── Heat haze ─────────────────────────────────────────────────────
    vec2 sampleUV = uv;
    if (u_haze_strength > 0.0) {
        float haze = sin(uv.y * 18.0 + u_time * 1.8) *
                     cos(uv.x * 12.0 + u_time * 1.3) * u_haze_strength;
        sampleUV += vec2(haze, haze * 0.6) / u_resolution;
    }

    vec4 color = texture(u_game, sampleUV);

    // ── World coords ──────────────────────────────────────────────────
    vec2 screenPos = vec2(uv.x, 1.0 - uv.y) * u_resolution;
    vec2 worldPos  = screenPos + u_cam_offset;

    // ── Освещённость ──────────────────────────────────────────────────
    float light = 0.0;

    float ambDist = length(worldPos - u_player_pos);
    float pulse   = sin(u_time * 2.5) * 4.0;
    light = max(light, 1.0 - smoothstep(0.0, u_ambient_r + pulse, ambDist));

    light = max(light, flashlightBrightness(worldPos));

    if (u_muzzle_t > 0.0) {
        float t   = u_muzzle_t / u_muzzle_dur;
        vec2  fd  = vec2(cos(u_player_dir), sin(u_player_dir));
        vec2  fp  = u_player_pos + fd * 22.0;
        float d   = length(worldPos - fp);
        float mr  = u_muzzle_r * t;
        light     = max(light, 1.0 - smoothstep(0.0, mr, d));
        float fl  = max(0.0, 1.0 - d / max(mr, 1.0)) * t * t;
        color.rgb += u_muzzle_color * fl * 0.4;
    }

    for (int i = 0; i < u_light_count; i++) {
        vec2  lpos = u_lights[i].xy;
        float lr   = u_lights[i].z;
        float ld   = length(worldPos - lpos);

        // мерцание: уникальная фаза для каждого источника
        float phase   = float(i) * 1.618;                      // золотое сечение → разные фазы
        float flicker = 1.0
            - 0.07 * sin(u_time * 7.3  + phase)
            - 0.05 * sin(u_time * 13.7 + phase * 2.1)
            - 0.04 * sin(u_time * 3.1  + phase * 0.7);
        float lr_f = lr * flicker;

        if (ld < lr_f) {
            light = max(light, (1.0 - pow(ld / lr_f, 1.6)) * 0.9 * flicker);
        }
    }

    // ── Тьма ──────────────────────────────────────────────────────────
    float alpha = (1.0 - u_darkness) * (1.0 - light);
    color.rgb   = mix(color.rgb, vec3(0.0), clamp(alpha, 0.0, 1.0));

    fragColor = color;
}
"""

# ── Pass 2: Gaussian blur horizontal ─────────────────────────────────────────
_FRAG_BLUR_H = """
#version 330 core
uniform sampler2D u_tex;
uniform vec2      u_resolution;
uniform float     u_bloom_threshold;

in  vec2 uv;
out vec4 fragColor;

void main() {
    vec4 color = texture(u_tex, uv);

    // отсекаем тёмные пиксели — bloom только от ярких
    float brightness = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));
    if (brightness < u_bloom_threshold) {
        fragColor = vec4(0.0);
        return;
    }

    float weights[5] = float[](0.227027, 0.194595, 0.121622, 0.054054, 0.016216);
    vec2  px = vec2(1.0 / u_resolution.x, 0.0);

    vec3 result = color.rgb * weights[0];
    for (int i = 1; i < 5; i++) {
        result += texture(u_tex, uv + px * float(i)).rgb * weights[i];
        result += texture(u_tex, uv - px * float(i)).rgb * weights[i];
    }
    fragColor = vec4(result, 1.0);
}
"""

# ── Pass 3: Gaussian blur vertical ───────────────────────────────────────────
_FRAG_BLUR_V = """
#version 330 core
uniform sampler2D u_tex;
uniform vec2      u_resolution;

in  vec2 uv;
out vec4 fragColor;

void main() {
    float weights[5] = float[](0.227027, 0.194595, 0.121622, 0.054054, 0.016216);
    vec2  px = vec2(0.0, 1.0 / u_resolution.y);

    vec3 result = texture(u_tex, uv).rgb * weights[0];
    for (int i = 1; i < 5; i++) {
        result += texture(u_tex, uv + px * float(i)).rgb * weights[i];
        result += texture(u_tex, uv - px * float(i)).rgb * weights[i];
    }
    fragColor = vec4(result, 1.0);
}
"""

# ── Pass 4: Composite ─────────────────────────────────────────────────────────
_FRAG_COMPOSITE = """
#version 330 core
uniform sampler2D u_fov;
uniform sampler2D u_bloom;

uniform float u_bloom_strength;
uniform float u_ca_strength;
uniform float u_hit_strength;   // 0..1 — интенсивность красной вспышки по краям
uniform float u_hp_ratio;       // 0..1 — текущий HP/maxHP (0 = при смерти)
uniform float u_time;
uniform vec2  u_resolution;

// цветовая коррекция
uniform vec3  u_shadow_color;     // тинт теней  (тёплый)
uniform vec3  u_light_color;      // тинт света   (холодный)
uniform float u_color_grading;    // интенсивность коррекции 0..1

in  vec2 uv;
out vec4 fragColor;

float rand(vec2 co) {
    return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
}

// перевод в HSL и обратно для насыщенности
vec3 rgb2hsl(vec3 c) {
    float mx = max(c.r, max(c.g, c.b));
    float mn = min(c.r, min(c.g, c.b));
    float l  = (mx + mn) * 0.5;
    if (mx == mn) return vec3(0.0, 0.0, l);
    float d = mx - mn;
    float s = l > 0.5 ? d / (2.0 - mx - mn) : d / (mx + mn);
    float h;
    if      (mx == c.r) h = (c.g - c.b) / d + (c.g < c.b ? 6.0 : 0.0);
    else if (mx == c.g) h = (c.b - c.r) / d + 2.0;
    else                h = (c.r - c.g) / d + 4.0;
    return vec3(h / 6.0, s, l);
}

float hue2rgb(float p, float q, float t) {
    if (t < 0.0) t += 1.0;
    if (t > 1.0) t -= 1.0;
    if (t < 1.0/6.0) return p + (q-p)*6.0*t;
    if (t < 1.0/2.0) return q;
    if (t < 2.0/3.0) return p + (q-p)*(2.0/3.0 - t)*6.0;
    return p;
}

vec3 hsl2rgb(vec3 c) {
    if (c.y == 0.0) return vec3(c.z);
    float q = c.z < 0.5 ? c.z*(1.0+c.y) : c.z+c.y - c.z*c.y;
    float p = 2.0*c.z - q;
    return vec3(hue2rgb(p,q,c.x+1.0/3.0),
                hue2rgb(p,q,c.x),
                hue2rgb(p,q,c.x-1.0/3.0));
}

void main() {
    // ── Chromatic aberration ───────────────────────────────────────────
    vec2  dir = uv - 0.5;
    float ca  = u_ca_strength * 0.012;

    float r = texture(u_fov, uv + dir * ca).r;
    float g = texture(u_fov, uv           ).g;
    float b = texture(u_fov, uv - dir * ca).b;
    vec4 color = vec4(r, g, b, 1.0);

    // ── Bloom ADD ─────────────────────────────────────────────────────
    color.rgb += texture(u_bloom, uv).rgb * u_bloom_strength;

    // ── Цветовая коррекция ────────────────────────────────────────────
    if (u_color_grading > 0.0) {
        // яркость пикселя — мера освещённости
        float lum = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));

        // shadow zone: lum 0..0.35  → тёплый тинт
        // light zone:  lum 0.55..1  → холодный тинт
        // midtones:    плавный переход
        float shadow_t = 1.0 - smoothstep(0.0, 0.45, lum);
        float light_t  = smoothstep(0.45, 0.85, lum);

        vec3 graded = color.rgb;
        graded = mix(graded, graded * u_shadow_color, shadow_t * u_color_grading);
        graded = mix(graded, graded * u_light_color,  light_t  * u_color_grading);

        // небольшое повышение насыщенности в освещённых зонах
        vec3 hsl = rgb2hsl(graded);
        hsl.y   *= 1.0 + light_t * 0.25;
        graded   = hsl2rgb(hsl);

        color.rgb = graded;
    }

    // ── Виньетка ──────────────────────────────────────────────────────
    float vig  = 1.0 - smoothstep(0.45, 0.85, length(uv - 0.5) * 1.4);
    color.rgb *= 0.85 + 0.15 * vig;

    // ── Hit flash — красный оверлей по краям экрана ───────────────────
    if (u_hit_strength > 0.0) {
        // расстояние от края: 0 в центре, 1 у угла
        vec2  d    = abs(uv - 0.5) * 2.0;           // [0..1] по каждой оси
        float edge = pow(max(d.x, d.y), 2.5);        // резче к углам
        float rim  = smoothstep(0.3, 1.0, edge);     // начинается с 30% от края
        vec3  red  = vec3(0.85, 0.04, 0.04);
        color.rgb  = mix(color.rgb, red, rim * u_hit_strength * 0.72);
    }

    // ── Low HP vignette — пульсирующая тёмно-красная виньетка ─────────
    if (u_hp_ratio < 0.4) {
        float danger    = 1.0 - u_hp_ratio / 0.4;           // 0→1 при HP 40%→0
        float pulse     = 0.5 + 0.5 * sin(u_time * (2.5 + danger * 3.0));
        float intensity = danger * (0.35 + 0.25 * pulse);
        float edge2     = pow(length((uv - 0.5) * 2.0), 2.2);
        float rim2      = smoothstep(0.4, 1.1, edge2);
        vec3  darkred   = vec3(0.55, 0.0, 0.0);
        color.rgb = mix(color.rgb, darkred, rim2 * intensity);
    }

    // ── Зернистость ───────────────────────────────────────────────────
    color.rgb += rand(uv + fract(u_time * 0.07)) * 0.03 - 0.015;

    fragColor = color;
}
"""

# ── Квад ─────────────────────────────────────────────────────────────────────
_QUAD = np.array([
    -1.0,  1.0,  0.0, 1.0,
    -1.0, -1.0,  0.0, 0.0,
     1.0, -1.0,  1.0, 0.0,
    -1.0,  1.0,  0.0, 1.0,
     1.0, -1.0,  1.0, 0.0,
     1.0,  1.0,  1.0, 1.0,
], dtype=np.float32)

_MAX_LIGHTS = 16


def _make_fb(ctx, w, h):
    """Создать framebuffer с RGBA текстурой."""
    tex = ctx.texture((w, h), 4)
    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    fb  = ctx.framebuffer(color_attachments=[tex])
    return fb, tex


class GLRenderer:

    FLASHLIGHT_FOV  = math.radians(130.0)
    FLASHLIGHT_R    = 500.0
    AMBIENT_R       = 55.0
    DARKNESS        = 0.88
    BLOOM_THRESHOLD = 0.55    # порог яркости для bloom
    BLOOM_STRENGTH  = 0.45    # интенсивность bloom
    HAZE_STRENGTH   = 0.0     # heat haze — включается через set_haze()

    # цветовая коррекция
    # тени — тёплые (чуть оранжево-коричневые)
    SHADOW_COLOR    = (1.12, 0.95, 0.80)
    # свет фонарика — холодный (чуть голубоватый)
    LIGHT_COLOR     = (0.88, 0.95, 1.10)
    # интенсивность эффекта
    COLOR_GRADING   = 0.55

    def __init__(self, settings) -> None:
        self.sw = settings.screen_width
        self.sh = settings.screen_height

        self.ctx = moderngl.create_context()
        self.ctx.viewport = (0, 0, self.sw, self.sh)

        # ── Шейдерные программы ───────────────────────────────────────
        self.prog_fov       = self.ctx.program(vertex_shader=_VERT,
                                               fragment_shader=_FRAG_FOV)
        self.prog_blur_h    = self.ctx.program(vertex_shader=_VERT,
                                               fragment_shader=_FRAG_BLUR_H)
        self.prog_blur_v    = self.ctx.program(vertex_shader=_VERT,
                                               fragment_shader=_FRAG_BLUR_V)
        self.prog_composite = self.ctx.program(vertex_shader=_VERT,
                                               fragment_shader=_FRAG_COMPOSITE)

        # ── VAO (один квад для всех проходов) ─────────────────────────
        self.vbo = self.ctx.buffer(data=_QUAD.tobytes())
        def make_vao(prog):
            return self.ctx.vertex_array(prog,
                                         [(self.vbo, '2f 2f', 'in_vert', 'in_uv')])
        self.vao_fov       = make_vao(self.prog_fov)
        self.vao_blur_h    = make_vao(self.prog_blur_h)
        self.vao_blur_v    = make_vao(self.prog_blur_v)
        self.vao_composite = make_vao(self.prog_composite)

        # ── Текстуры и framebuffers ────────────────────────────────────
        # исходный кадр pygame
        self.game_tex = self.ctx.texture((self.sw, self.sh), 4)
        self.game_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

        # стены
        self.wall_tex = self.ctx.texture((1, 1), 4, dtype='f4')
        self.wall_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self._wall_count = 0

        # framebuffers: fov → blur_h → blur_v
        self._bw, self._bh = self.sw, self.sh
        bw, bh = self._bw, self._bh

        self.fb_fov,    self.tex_fov    = _make_fb(self.ctx, self.sw, self.sh)
        self.fb_blur_h, self.tex_blur_h = _make_fb(self.ctx, bw, bh)
        self.fb_blur_v, self.tex_blur_v = _make_fb(self.ctx, bw, bh)

        # ── Состояние ─────────────────────────────────────────────────
        self._lights: list[tuple] = []
        self._cam_offset   = (0.0, 0.0)
        self._player_pos   = (0.0, 0.0)
        self._player_dir   = 0.0
        self._flashlight   = True
        self._muzzle_t     = 0.0
        self._muzzle_dur   = 0.07
        self._muzzle_color = (1.0, 0.47, 0.12)
        self._muzzle_r     = 55.0
        self._ca_strength  = 0.0   # chromatic aberration
        self._ca_decay     = 3.0   # скорость затухания CA
        self._hit_strength = 0.0   # красная вспышка по краям
        self._hit_decay    = 4.5   # быстро угасает
        self._haze         = self.HAZE_STRENGTH
        self._time         = 0.0

        # ── Инициализация uniforms ─────────────────────────────────────
        res = (float(self.sw), float(self.sh))
        bres = (float(self.sw), float(self.sh))

        p = self.prog_fov
        p['u_resolution'].value     = res
        p['u_flashlight_fov'].value = self.FLASHLIGHT_FOV
        p['u_flashlight_r'].value   = self.FLASHLIGHT_R
        p['u_ambient_r'].value      = self.AMBIENT_R
        p['u_darkness'].value       = self.DARKNESS
        p['u_muzzle_dur'].value     = self._muzzle_dur
        p['u_game'].value           = 0
        p['u_walls'].value          = 1

        self.prog_blur_h['u_resolution'].value      = bres
        self.prog_blur_h['u_bloom_threshold'].value = self.BLOOM_THRESHOLD
        self.prog_blur_h['u_tex'].value             = 0

        self.prog_blur_v['u_resolution'].value = bres
        self.prog_blur_v['u_tex'].value        = 0

        self.prog_composite['u_fov'].value            = 0
        self.prog_composite['u_bloom'].value          = 1
        self.prog_composite['u_bloom_strength'].value = self.BLOOM_STRENGTH
        self.prog_composite['u_shadow_color'].value   = self.SHADOW_COLOR
        self.prog_composite['u_light_color'].value    = self.LIGHT_COLOR
        self.prog_composite['u_color_grading'].value  = self.COLOR_GRADING

    # ── Данные уровня ─────────────────────────────────────────────────────────

    def load_walls(self, wall_rects: list) -> None:
        if not wall_rects:
            return
        n    = len(wall_rects)
        data = np.zeros((n, 4), dtype=np.float32)
        for i, r in enumerate(wall_rects):
            data[i] = (float(r.left), float(r.top),
                       float(r.right), float(r.bottom))
        self.wall_tex.release()
        self.wall_tex = self.ctx.texture((n, 1), 4,
                                         data=data.tobytes(), dtype='f4')
        self.wall_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self._wall_count = n
        self.prog_fov['u_wall_count'].value = n

    def load_lights(self, lights: list) -> None:
        self._lights = [(src.pos.x, src.pos.y, src.radius * 0.75)
                        for src in lights[:_MAX_LIGHTS]]
        count  = len(self._lights)
        padded = list(self._lights) + [(0.0, 0.0, 0.0)] * (_MAX_LIGHTS - count)
        self.prog_fov['u_light_count'].value = count
        if count > 0:
            self.prog_fov['u_lights'].value = padded

    # ── Состояние FOV ─────────────────────────────────────────────────────────

    def set_fov(self, player_pos, player_dir: float,
                cam_offset, flashlight_on: bool) -> None:
        self._player_pos = (float(player_pos[0]), float(player_pos[1]))
        self._player_dir = float(player_dir)
        self._cam_offset = (float(cam_offset[0]), float(cam_offset[1]))
        self._flashlight = flashlight_on

    def trigger_muzzle_flash(self, color=(1.0, 0.47, 0.12),
                             radius=55.0, duration=0.07) -> None:
        self._muzzle_t     = duration
        self._muzzle_dur   = duration
        self._muzzle_color = color
        self._muzzle_r     = radius
        self.prog_fov['u_muzzle_dur'].value = duration

    def trigger_hit(self, intensity: float = 1.0) -> None:
        """Вызвать при получении урона — запускает chromatic aberration + красную вспышку."""
        self._ca_strength  = min(1.0, self._ca_strength  + intensity)
        self._hit_strength = min(1.0, self._hit_strength + intensity * 0.85)

    def set_haze(self, strength: float) -> None:
        """Включить/выключить heat haze (0 = выкл)."""
        self._haze = strength

    def update(self, dt: float) -> None:
        self._muzzle_t    = max(0.0, self._muzzle_t - dt)
        self._ca_strength = max(0.0, self._ca_strength - self._ca_decay * dt)
        self._hit_strength = max(0.0, self._hit_strength - self._hit_decay * dt)

    # ── Рендер ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface, dt: float = 0.016, hp_ratio: float = 1.0) -> None:
        self._time += dt

        # pygame → GL текстура
        raw = pygame.image.tobytes(surface, 'RGBA', True)
        self.game_tex.write(raw)

        # ── Pass 1: FOV + heat haze ───────────────────────────────────
        self.fb_fov.use()
        self.ctx.viewport = (0, 0, self.sw, self.sh)
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        p = self.prog_fov
        p['u_time'].value         = self._time
        p['u_cam_offset'].value   = self._cam_offset
        p['u_player_pos'].value   = self._player_pos
        p['u_player_dir'].value   = self._player_dir
        p['u_flashlight_fov'].value = self.FLASHLIGHT_FOV if self._flashlight else 0.0
        p['u_muzzle_t'].value     = self._muzzle_t
        p['u_muzzle_color'].value = self._muzzle_color
        p['u_muzzle_r'].value     = self._muzzle_r
        p['u_haze_strength'].value= self._haze

        self.game_tex.use(0)
        self.wall_tex.use(1)
        self.vao_fov.render(moderngl.TRIANGLES)

        # ── Pass 2: Blur horizontal (half res) ────────────────────────
        self.fb_blur_h.use()
        self.ctx.viewport = (0, 0, self._bw, self._bh)
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self.tex_fov.use(0)
        self.vao_blur_h.render(moderngl.TRIANGLES)

        # ── Pass 3: Blur vertical (half res) ──────────────────────────
        self.fb_blur_v.use()
        self.ctx.viewport = (0, 0, self._bw, self._bh)
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self.tex_blur_h.use(0)
        self.vao_blur_v.render(moderngl.TRIANGLES)

        # ── Pass 4: Composite → экран ─────────────────────────────────
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, self.sw, self.sh)
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        self.prog_composite['u_time'].value         = self._time
        self.prog_composite['u_ca_strength'].value  = self._ca_strength
        self.prog_composite['u_hit_strength'].value = self._hit_strength
        self.prog_composite['u_hp_ratio'].value     = float(hp_ratio)

        self.tex_fov.use(0)
        self.tex_blur_v.use(1)
        self.vao_composite.render(moderngl.TRIANGLES)

        pygame.display.flip()

    def destroy(self) -> None:
        for obj in [self.game_tex, self.wall_tex,
                    self.tex_fov, self.fb_fov,
                    self.tex_blur_h, self.fb_blur_h,
                    self.tex_blur_v, self.fb_blur_v,
                    self.vbo,
                    self.vao_fov, self.vao_blur_h,
                    self.vao_blur_v, self.vao_composite,
                    self.prog_fov, self.prog_blur_h,
                    self.prog_blur_v, self.prog_composite]:
            obj.release()
