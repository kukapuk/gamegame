import numpy as np
import pygame


class AudioManager:
    """
    Управляет звуками игры. Звуки генерируются процедурно через numpy.

    Два типа debug-кругов:
      amber  — выстрел
      blue   — шаги игрока
    """

    def __init__(self, settings) -> None:
        self.s = settings
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._load_all()

        self._debug_events: list[dict] = []
        self._debug_lifetime: float    = 0.5

    def _load_all(self) -> None:
        self._sounds["gunshot"] = self._generate_gunshot()
        self._sounds["step"]    = self._generate_footstep()

    def play(self, name: str) -> None:
        if name in self._sounds:
            self._sounds[name].play()

    def play_at(
        self,
        name: str,
        world_pos: pygame.math.Vector2,
        radius: float,
        color: tuple = (255, 220, 80),
    ) -> None:
        self.play(name)
        self._add_debug_event(world_pos, radius, color)

    def emit_silent(
        self,
        world_pos: pygame.math.Vector2,
        radius: float,
        color: tuple = (255, 220, 80),
    ) -> None:
        """Добавляет звуковое событие без воспроизведения звука (для шагов без звука)."""
        self._add_debug_event(world_pos, radius, color)

    def _add_debug_event(
        self,
        world_pos: pygame.math.Vector2,
        radius: float,
        color: tuple,
    ) -> None:
        self._debug_events.append({
            "pos":      pygame.math.Vector2(world_pos),
            "radius":   radius,
            "lifetime": self._debug_lifetime,
            "max_life": self._debug_lifetime,
            "color":    color,
        })

    def get_sound_events(self) -> list[dict]:
        return self._debug_events

    def update(self, dt: float) -> None:
        for ev in self._debug_events[:]:
            ev["lifetime"] -= dt
            if ev["lifetime"] <= 0:
                self._debug_events.remove(ev)

    def draw_debug(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        for ev in self._debug_events:
            progress = ev["lifetime"] / ev["max_life"]
            alpha    = int(180 * progress)
            r        = int(ev["radius"])
            color    = ev.get("color", (255, 220, 80))
            cx = round(ev["pos"].x - camera_offset.x)
            cy = round(ev["pos"].y - camera_offset.y)

            circle_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surf, (*color, alpha // 4), (r, r), r)
            pygame.draw.circle(circle_surf, (*color, alpha),      (r, r), r, 1)
            surface.blit(circle_surf, (cx - r, cy - r))

    def _generate_gunshot(self) -> pygame.mixer.Sound:
        sample_rate = 44100
        duration    = 0.18
        samples     = int(sample_rate * duration)
        t           = np.linspace(0, duration, samples, endpoint=False)

        noise    = np.random.uniform(-1.0, 1.0, samples)
        envelope = np.exp(-t * 28.0)
        tone     = np.sin(2 * np.pi * 180 * t) * 0.3

        wave = (noise * 0.7 + tone) * envelope
        wave = np.clip(wave * 0.6, -1.0, 1.0)

        pcm    = (wave * 32767).astype(np.int16)
        stereo = np.column_stack([pcm, pcm])
        sound  = pygame.sndarray.make_sound(stereo)
        sound.set_volume(0.4)
        return sound

    def _generate_footstep(self) -> pygame.mixer.Sound:
        sample_rate = 44100
        duration    = 0.12
        samples     = int(sample_rate * duration)
        t           = np.linspace(0, duration, samples, endpoint=False)

        thump    = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 35.0)
        rustle   = np.random.uniform(-1.0, 1.0, samples) * np.exp(-t * 80.0) * 0.15
        mid      = np.sin(2 * np.pi * 120 * t) * np.exp(-t * 50.0) * 0.2

        wave = thump * 0.65 + rustle + mid
        wave = np.clip(wave * 0.5, -1.0, 1.0)

        pcm    = (wave * 32767).astype(np.int16)
        stereo = np.column_stack([pcm, pcm])
        sound  = pygame.sndarray.make_sound(stereo)
        sound.set_volume(0.18)
        return sound
