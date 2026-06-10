import pygame
from core.settings import Settings
from core.camera import Camera
from entities.player import Player
from entities.weapon import Weapon


class Game:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screen = pygame.display.set_mode(
            (settings.screen_width, settings.screen_height)
        )
        pygame.display.set_caption(settings.title)
        self.clock = pygame.time.Clock()
        self.running = True

        # -- Sprite groups --
        self.all_sprites = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()      # отдельная группа для коллизий

        # -- Entities --
        spawn = (settings.screen_width // 2, settings.screen_height // 2)
        self.player = Player(spawn, settings, self.all_sprites)

        self.weapon = Weapon(
            owner=self.player,
            settings=settings,
            bullet_group=self.bullets,
            all_sprites=self.all_sprites,
        )

        # -- Camera --
        self.camera = Camera(settings)

        # -- Debug --
        self.debug = False

    # ------------------------------------------------------------------

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.settings.fps) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()

    # ------------------------------------------------------------------

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_F1:
                    self.debug = not self.debug
                elif event.key == pygame.K_SPACE:
                    self.player.try_dash()

    def _update(self, dt: float) -> None:
        # Обычные спрайты — без доп. аргументов
        self.player.update(dt)
        self.bullets.update(dt)

        # Оружие требует camera_offset для пересчёта позиции мыши
        self.weapon.update(dt, self.camera.get_offset())

        # Стрельба — зажатая кнопка мыши (автоогонь)
        if pygame.mouse.get_pressed()[0]:
            self.weapon.try_shoot()

        self.camera.follow(self.player)

    def _draw(self) -> None:
        self.screen.fill(self.settings.bg_color)
        self._draw_grid()
        self._draw_sprites()
        if self.debug:
            self._draw_debug_info()
        pygame.display.flip()

    # ------------------------------------------------------------------

    def _draw_grid(self) -> None:
        gs = self.settings.grid_size
        offset = self.camera.get_offset()
        w, h = self.settings.screen_width, self.settings.screen_height

        start_x = int(offset.x // gs) * gs
        start_y = int(offset.y // gs) * gs

        x = start_x
        while x < offset.x + w + gs:
            sx = x - offset.x
            pygame.draw.line(self.screen, self.settings.grid_color,
                             (sx, 0), (sx, h))
            x += gs

        y = start_y
        while y < offset.y + h + gs:
            sy = y - offset.y
            pygame.draw.line(self.screen, self.settings.grid_color,
                             (0, sy), (w, sy))
            y += gs

    def _draw_sprites(self) -> None:
        # Рендерим в нужном порядке: сначала пули (под игроком), потом игрок, потом оружие
        for sprite in [*self.bullets.sprites(), self.player, self.weapon]:
            screen_rect = self.camera.apply(sprite.rect)
            self.screen.blit(sprite.image, screen_rect)

    def _draw_debug_info(self) -> None:
        font = pygame.font.SysFont("monospace", 16)
        p = self.player
        lines = [
            f"FPS: {self.clock.get_fps():.0f}",
            f"pos: ({p.pos.x:.0f}, {p.pos.y:.0f})",
            f"vel: ({p.velocity.x:.0f}, {p.velocity.y:.0f})",
            f"aim: ({self.weapon.aim_dir.x:.2f}, {self.weapon.aim_dir.y:.2f})",
            f"stamina: {p.stamina:.0f} / {p.stats.max_stamina:.0f}",
            f"dash cd: {p._dash_cooldown:.2f}s  dashing: {p._is_dashing}",
            f"bullets: {len(self.bullets)}",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (180, 220, 180))
            self.screen.blit(surf, (10, 10 + i * 20))
        p.draw_debug(self.screen, self.camera.get_offset())
