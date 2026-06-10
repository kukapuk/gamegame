import pygame
from core.settings import Settings
from core.camera import Camera
from core.hud import HUD
from entities.actors.player import Player
from entities.combat.weapon import Weapon
from entities.actors.enemy import Enemy
from entities.items.world_item import WorldItem
from entities.items.consumable import make_medkit
from entities.items.weapon_item import WeaponItem, make_carbine, make_shotgun, make_sniper


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
        self.bullets     = pygame.sprite.Group()
        self.enemies     = pygame.sprite.Group()
        self.world_items = pygame.sprite.Group()

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
        self._spawn_world_items()
        self._sync_weapon()

        self.camera = Camera(settings)
        self.hud    = HUD(settings, self.player)
        self.debug  = False

        self._i_held_time: float     = 0.0
        self._i_triggered: bool      = False
        self._nearby_world_item: WorldItem = None
        self._font_pickup = pygame.font.SysFont("monospace", 14)

    def _sync_weapon(self) -> None:
        item = self.player.get_active_weapon()
        self.weapon.equip(item if item else None)

    def _spawn_enemies(self) -> None:
        for pos in [(800, 400), (300, 600), (1000, 200), (500, 800), (1200, 500)]:
            Enemy(pos=pos, target=self.player, groups=[self.all_sprites, self.enemies])

    def _give_test_items(self) -> None:
        for i in range(2):
            slot = self.player.backpack.get_slot(i)
            if slot:
                slot.put(make_medkit(30))

    def _spawn_world_items(self) -> None:
        cx, cy = self.settings.screen_width // 2, self.settings.screen_height // 2
        items = [
            (make_carbine(), (cx + 120, cy + 60)),
            (make_shotgun(), (cx - 140, cy + 80)),
            (make_sniper(),  (cx + 60,  cy - 120)),
        ]
        for item, pos in items:
            WorldItem(item=item, pos=pos, groups=[self.world_items])

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.settings.fps) / 1000.0
            self._handle_i_hold(dt)
            self._handle_events()
            self._update(dt)
            self._draw()

    def _handle_i_hold(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_i]:
            self._i_held_time += dt
            if self._i_held_time >= self.settings.backpack_hold_time and not self._i_triggered:
                self._i_triggered = True
                if self.hud.is_open():
                    self.hud.close_backpack()
                else:
                    self.hud.open_backpack()
        else:
            self._i_held_time = 0.0
            self._i_triggered = False

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_1:
                    self.player.switch_weapon(0)
                    self._sync_weapon()
                elif event.key == pygame.K_2:
                    self.player.switch_weapon(1)
                    self._sync_weapon()
                elif event.key == pygame.K_TAB:
                    self.hud.toggle_pouch()
                elif event.key == pygame.K_F1:
                    self.debug = not self.debug
                elif event.key == pygame.K_SPACE:
                    self.player.try_dash()
                elif event.key == pygame.K_e:
                    self._try_pickup()
                elif event.key == pygame.K_g:
                    self._try_drop()
                else:
                    if not self.hud.is_open():
                        typed_count = len(self.player.pouch.typed_slots)
                        for i, key in enumerate(self.settings.pouch_hotkeys):
                            if event.key == key:
                                self.player.pouch.use_slot(typed_count + i, self.player)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.hud.handle_mouse_down(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.hud.handle_mouse_up(event.pos)
                    self._sync_weapon()

            elif event.type == pygame.MOUSEMOTION:
                self.hud.handle_mouse_motion(event.pos)

    def _try_drop(self) -> None:
        from entities.items.item import ItemType
        weapon_slots = [s for s in self.player.pouch.typed_slots if s.allowed_type == ItemType.WEAPON]
        slot = weapon_slots[self.player.active_weapon_slot]
        if slot.empty:
            return
        item = slot.take()
        drop_pos = (
            self.player.pos.x + self.player.facing.x * 48,
            self.player.pos.y + self.player.facing.y * 48,
        )
        WorldItem(item=item, pos=drop_pos, groups=[self.world_items])
        self._sync_weapon()

    def _try_pickup(self) -> None:
        if not self._nearby_world_item:
            return
        item     = self._nearby_world_item.item
        picked   = False

        if isinstance(item, WeaponItem):
            from entities.items.item import ItemType
            weapon_slots = [s for s in self.player.pouch.typed_slots if s.allowed_type == ItemType.WEAPON]
            for slot in weapon_slots:
                if slot.empty:
                    slot.item = item
                    picked = True
                    break
            if not picked:
                old = weapon_slots[self.player.active_weapon_slot].item
                weapon_slots[self.player.active_weapon_slot].item = item
                if old:
                    WorldItem(item=old, pos=self._nearby_world_item.world_pos,
                              groups=[self.world_items])
                picked = True
        else:
            picked = self.player.backpack.add(item) or self.player.pouch.add(item)

        if picked:
            self._nearby_world_item.kill()
            self._nearby_world_item = None
            self._sync_weapon()

    def _update(self, dt: float) -> None:
        self.player.update(dt)
        self.enemies.update(dt)
        self.bullets.update(dt)
        self.world_items.update(dt)
        self.weapon.update(dt, self.camera.get_offset())

        if pygame.mouse.get_pressed()[0] and not self.hud.is_open():
            self.weapon.try_shoot()

        self._check_bullet_hits()
        self._check_contact_damage()
        self._update_nearby_item()
        self.camera.follow(self.player)

    def _update_nearby_item(self) -> None:
        self._nearby_world_item = None
        closest_dist = float("inf")
        for wi in self.world_items:
            dist = (wi.world_pos - self.player.pos).length()
            if wi.is_in_pickup_range(self.player.pos) and dist < closest_dist:
                closest_dist = dist
                self._nearby_world_item = wi

    def _check_bullet_hits(self) -> None:
        hits = pygame.sprite.groupcollide(self.enemies, self.bullets, False, True)
        for enemy, bullet_list in hits.items():
            for bullet in bullet_list:
                enemy.take_damage(bullet.damage)
                if bullet.stopping_effect > 0 and bullet.velocity.length() > 0:
                    enemy.apply_stopping_effect(bullet.velocity, bullet.stopping_effect)

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
        self._draw_pickup_hint()
        self.hud.draw(self.screen, i_hold_progress=self._i_held_time / self.settings.backpack_hold_time)
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
        for sprite in self.world_items:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))
        for sprite in [*self.bullets.sprites(), *self.enemies.sprites(), self.player]:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))
        if self.weapon.has_weapon:
            self.screen.blit(self.weapon.image, self.camera.apply(self.weapon.rect))

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

    def _draw_pickup_hint(self) -> None:
        if not self._nearby_world_item:
            return
        item       = self._nearby_world_item.item
        screen_pos = self.camera.apply(self._nearby_world_item.rect)
        text       = f"[E]  {item.name}"
        surf       = self._font_pickup.render(text, True, (240, 220, 140))
        pad        = 5
        bg         = pygame.Surface((surf.get_width() + pad * 2, surf.get_height() + pad * 2), pygame.SRCALPHA)
        bg.fill((10, 10, 20, 180))
        bx = screen_pos.centerx - bg.get_width() // 2
        by = screen_pos.top - bg.get_height() - 6
        self.screen.blit(bg, (bx, by))
        self.screen.blit(surf, (bx + pad, by + pad))

    def _draw_debug_info(self) -> None:
        font = pygame.font.SysFont("monospace", 16)
        p = self.player
        lines = [
            f"FPS: {self.clock.get_fps():.0f}",
            f"pos: ({p.pos.x:.0f}, {p.pos.y:.0f})",
            f"stamina: {p.stamina:.0f} / {p.stats.max_stamina:.0f}",
            f"dash cd: {p._dash_cooldown:.2f}s",
            f"bullets: {len(self.bullets)}  enemies: {len(self.enemies)}",
            f"world_items: {len(self.world_items)}",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (180, 220, 180))
            self.screen.blit(surf, (10, 10 + i * 20))
        p.draw_debug(self.screen, self.camera.get_offset())
