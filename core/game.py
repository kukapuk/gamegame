import pygame
from core.settings import Settings
from core.camera import Camera
from entities.player import Player
from entities.weapon import Weapon
from entities.enemy import Enemy


class Game:
    """Central game loop, renderer, and scene owner."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screen = pygame.display.set_mode(
            (settings.screen_width, settings.screen_height)
        )
        pygame.display.set_caption(settings.title)
        self.clock = pygame.time.Clock()
        self.running = True

        self.all_sprites = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()

        spawn = (settings.screen_width // 2, settings.screen_height // 2)
        self.player = Player(spawn, settings, groups=[self.all_sprites])

        self.weapon = Weapon(
            owner=self.player,
            settings=settings,
            bullet_group=self.bullets,
            all_sprites=self.all_sprites,
        )

        self._spawn_enemies()

        self.camera = Camera(settings)
        self.debug = False

    def _spawn_enemies(self) -> None:
        positions = [
            (800, 400), (300, 600), (1000, 200),
            (500, 800), (1200, 500),
        ]
        for pos in positions:
            Enemy(pos=pos, target=self.player, groups=[self.all_sprites, self.enemies])

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.settings.fps) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()

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
        self.player.update(dt)
        self.enemies.update(dt)
        self.bullets.update(dt)
        self.weapon.update(dt, self.camera.get_offset())

        if pygame.mouse.get_pressed()[0]:
            self.weapon.try_shoot()

        self._check_bullet_hits()
        self._check_contact_damage()
        self.camera.follow(self.player)

    def _check_bullet_hits(self) -> None:
        hits = pygame.sprite.groupcollide(self.enemies, self.bullets, False, True)
        for enemy, bullet_list in hits.items():
            for bullet in bullet_list:
                enemy.take_damage(bullet.damage)

    def _check_contact_damage(self) -> None:
        s = self.settings
        for enemy in self.enemies:
            enemy.try_deal_contact_damage(
                self.player,
                s.enemy_contact_damage,
                s.enemy_contact_cooldown,
            )

    def _draw(self) -> None:
        self.screen.fill(self.settings.bg_color)
        self._draw_grid()
        self._draw_sprites()
        self._draw_hp_bars()
        self._draw_player_hud()
        if self.debug:
            self._draw_debug_info()
        pygame.display.flip()

    def _draw_grid(self) -> None:
        gs = self.settings.grid_size
        offset = self.camera.get_offset()
        w, h = self.settings.screen_width, self.settings.screen_height

        start_x = int(offset.x // gs) * gs
        start_y = int(offset.y // gs) * gs

        x = start_x
        while x < offset.x + w + gs:
            pygame.draw.line(self.screen, self.settings.grid_color,
                             (x - offset.x, 0), (x - offset.x, h))
            x += gs

        y = start_y
        while y < offset.y + h + gs:
            pygame.draw.line(self.screen, self.settings.grid_color,
                             (0, y - offset.y), (w, y - offset.y))
            y += gs

    def _draw_sprites(self) -> None:
        for sprite in [*self.bullets.sprites(), *self.enemies.sprites(), self.player, self.weapon]:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))

    def _draw_hp_bars(self) -> None:
        s = self.settings
        for enemy in self.enemies:
            bar_rect = self.camera.apply(enemy.rect)
            bx = bar_rect.centerx - s.enemy_hp_bar_width // 2
            by = bar_rect.top - 8

            pygame.draw.rect(self.screen, s.enemy_hp_bar_bg,
                             (bx, by, s.enemy_hp_bar_width, s.enemy_hp_bar_height))

            fill = int(s.enemy_hp_bar_width * enemy.hp / enemy.max_hp)
            if fill > 0:
                pygame.draw.rect(self.screen, s.enemy_hp_bar_color,
                                 (bx, by, fill, s.enemy_hp_bar_height))

    def _draw_player_hud(self) -> None:
        s = self.settings
        font = pygame.font.SysFont("monospace", 13)

        bw = s.player_hp_bar_width
        bh = s.player_hp_bar_height
        margin = s.player_hp_bar_margin

        bx = margin
        by = s.screen_height - margin - bh

        pygame.draw.rect(self.screen, s.player_hp_bar_bg, (bx, by, bw, bh))

        fill = int(bw * self.player.hp / self.player.max_hp)
        if fill > 0:
            pygame.draw.rect(self.screen, s.player_hp_bar_color, (bx, by, fill, bh))

        pygame.draw.rect(self.screen, (80, 80, 80), (bx, by, bw, bh), 1)

        label = font.render(f"HP  {self.player.hp} / {self.player.max_hp}", True, (200, 200, 200))
        self.screen.blit(label, (bx, by - 18))

    def _draw_debug_info(self) -> None:
        font = pygame.font.SysFont("monospace", 16)
        p = self.player
        lines = [
            f"FPS: {self.clock.get_fps():.0f}",
            f"pos: ({p.pos.x:.0f}, {p.pos.y:.0f})",
            f"vel: ({p.velocity.x:.0f}, {p.velocity.y:.0f})",
            f"stamina: {p.stamina:.0f} / {p.stats.max_stamina:.0f}",
            f"dash cd: {p._dash_cooldown:.2f}s",
            f"bullets: {len(self.bullets)}  enemies: {len(self.enemies)}",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (180, 220, 180))
            self.screen.blit(surf, (10, 10 + i * 20))
        p.draw_debug(self.screen, self.camera.get_offset())
