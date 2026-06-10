import pygame
from core.settings import Settings
from core.camera import Camera
from core.hud import HUD
from entities.actors.player import Player
from entities.combat.weapon import Weapon
from entities.actors.enemy import Enemy
from entities.items.consumable import make_medkit


class Game:
    """Central game loop, renderer, and scene owner."""

    POUCH_HOTKEYS = [pygame.K_z, pygame.K_x, pygame.K_c, pygame.K_v]

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screen = pygame.display.set_mode(
            (settings.screen_width, settings.screen_height)
        )
        pygame.display.set_caption(settings.title)
        self.clock = pygame.time.Clock()
        self.running = True

        self.all_sprites = pygame.sprite.Group()
        self.bullets     = pygame.sprite.Group()
        self.enemies     = pygame.sprite.Group()

        spawn = (settings.screen_width // 2, settings.screen_height // 2)
        self.player = Player(spawn, settings, groups=[self.all_sprites])

        self.weapon = Weapon(
            owner=self.player,
            settings=settings,
            bullet_group=self.bullets,
            all_sprites=self.all_sprites,
        )

        self._spawn_enemies()
        self._give_test_items()

        self.camera = Camera(settings)
        self.hud    = HUD(settings, self.player)
        self.debug  = False

        self.backpack_open   = False
        self._backpack_timer = 0.0
        self._backpack_delay = 1.5

    def _spawn_enemies(self) -> None:
        for pos in [(800, 400), (300, 600), (1000, 200), (500, 800), (1200, 500)]:
            Enemy(pos=pos, target=self.player, groups=[self.all_sprites, self.enemies])

    def _give_test_items(self) -> None:
        typed_count = len(self.player.pouch.typed_slots)
        for i in range(3):
            slot_index = typed_count + i
            slot = self.player.pouch.get_slot(slot_index)
            if slot:
                slot.put(make_medkit(30))

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.settings.fps) / 1000.0
            self._handle_events(dt)
            self._update(dt)
            self._draw()

    def _handle_events(self, dt: float) -> None:
        keys_held = pygame.key.get_pressed()

        if keys_held[pygame.K_i]:
            self._backpack_timer += dt
            if self._backpack_timer >= self._backpack_delay:
                self.backpack_open = True
        else:
            self._backpack_timer = 0.0
            if not keys_held[pygame.K_i]:
                pass

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.backpack_open:
                        self.backpack_open = False
                    else:
                        self.running = False

                elif event.key == pygame.K_TAB:
                    pass

                elif event.key == pygame.K_F1:
                    self.debug = not self.debug

                elif event.key == pygame.K_SPACE:
                    self.player.try_dash()

                else:
                    typed_count = len(self.player.pouch.typed_slots)
                    for i, key in enumerate(self.POUCH_HOTKEYS):
                        if event.key == key:
                            self.player.pouch.use_slot(typed_count + i, self.player)

            elif event.type == pygame.MOUSEMOTION:
                self.hud.handle_mouse_motion(event.pos)

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_i and not self.backpack_open:
                    self._backpack_timer = 0.0

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
                self.player, s.enemy_contact_damage, s.enemy_contact_cooldown
            )

    def _draw(self) -> None:
        self.screen.fill(self.settings.bg_color)
        self._draw_grid()
        self._draw_sprites()
        self._draw_enemy_hp_bars()
        self.hud.draw(self.screen)
        if self.backpack_open:
            self._draw_backpack()
        self.hud.draw_tooltip(self.screen, pygame.mouse.get_pos())
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

    def _draw_enemy_hp_bars(self) -> None:
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

    def _draw_backpack(self) -> None:
        ss = HUD.SLOT_SIZE
        pad = HUD.SLOT_PAD
        cols = 4
        slots = self.player.backpack.all_slots()

        rows = (len(slots) + cols - 1) // cols
        panel_w = cols * ss + (cols - 1) * pad + 24
        panel_h = rows * ss + (rows - 1) * pad + 50

        cx = self.settings.screen_width // 2
        cy = self.settings.screen_height // 2
        panel_rect = pygame.Rect(cx - panel_w // 2, cy - panel_h // 2, panel_w, panel_h)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((20, 22, 32, 230))
        self.screen.blit(panel, panel_rect.topleft)
        pygame.draw.rect(self.screen, (60, 65, 90), panel_rect, 1)

        font = self.hud.font_md
        title = font.render("Backpack", True, (180, 180, 200))
        self.screen.blit(title, (panel_rect.x + 12, panel_rect.y + 10))

        ox = panel_rect.x + 12
        oy = panel_rect.y + 36

        for i, slot in enumerate(slots):
            col = i % cols
            row = i // cols
            x = ox + col * (ss + pad)
            y = oy + row * (ss + pad)
            rect = pygame.Rect(x, y, ss, ss)
            pygame.draw.rect(self.screen, HUD.SLOT_BG, rect)
            pygame.draw.rect(self.screen, HUD.SLOT_BORDER, rect, 1)
            if not slot.empty:
                icon = slot.item.icon
                self.screen.blit(icon, icon.get_rect(center=rect.center))

    def _draw_debug_info(self) -> None:
        font = pygame.font.SysFont("monospace", 16)
        p = self.player
        lines = [
            f"FPS: {self.clock.get_fps():.0f}",
            f"pos: ({p.pos.x:.0f}, {p.pos.y:.0f})",
            f"stamina: {p.stamina:.0f} / {p.stats.max_stamina:.0f}",
            f"dash cd: {p._dash_cooldown:.2f}s",
            f"bullets: {len(self.bullets)}  enemies: {len(self.enemies)}",
            f"backpack: {'open' if self.backpack_open else 'closed'}  (hold I {self._backpack_timer:.1f}s)",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (180, 220, 180))
            self.screen.blit(surf, (10, 10 + i * 20))
        p.draw_debug(self.screen, self.camera.get_offset())
