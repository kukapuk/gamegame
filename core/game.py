import pygame
from core.settings import Settings
from core.camera import Camera
from core.hud import HUD
from core.level import Level
from actors.player import Player
from combat.weapon import Weapon
from actors.enemy import Enemy
from items.world_item import WorldItem
from items.consumable import make_medkit
from items.weapon_item import WeaponItem, make_carbine, make_shotgun, make_sniper
from items.ammo import make_ammo, AmmoType
from combat.calculator import resolve_hit
from actors.enemy import make_grunt, make_shooter


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
        self.enemy_bullets = pygame.sprite.Group()

        self.level = Level("levels/level_1.txt", settings.grid_size)

        spawn = self.level.player_spawn
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
        if item is self.weapon._weapon_item:
            return
        self.weapon.equip(item if item else None)

    def _spawn_enemies(self) -> None:
        grunts = [
            ((800, 400), 0),
            ((1000, 200), 1),
        ]
        shooters = [
            ((500, 800), 2),
        ]

        for pos, armor in grunts:
            make_grunt(
                pos=pos, target=self.player, armor_class=armor,
                groups=[self.all_sprites, self.enemies],
            )

        for pos, armor in shooters:
            make_shooter(
                pos=pos, target=self.player, armor_class=armor,
                groups=[self.all_sprites, self.enemies],
                bullet_group=self.enemy_bullets,
                all_sprites=self.all_sprites,
            )
    
    def _check_enemy_bullet_hits(self) -> None:
        for bullet in self.enemy_bullets:
            if self.player.rect.colliderect(bullet.rect):
                self.player.take_damage(bullet.damage)
                bullet.kill()

    def _give_test_items(self) -> None:
        test_items = [
            make_ammo(AmmoType.CARBINE, 90),
            make_ammo(AmmoType.SHOTGUN, 48),
            make_ammo(AmmoType.SNIPER,  20),
            make_medkit(30),
            make_medkit(30),
        ]
        for i, item in enumerate(test_items):
            slot = self.player.backpack.get_slot(i)
            if slot:
                slot.put(item)

    def _spawn_world_items(self) -> None:
        from items.ammo import make_ammo, AmmoType
        from items.armor import make_light_armor, make_medium_armor, make_heavy_armor
        cx, cy = self.settings.screen_width // 2, self.settings.screen_height // 2
        items = [
            (make_carbine(),                  (cx + 120, cy + 60)),
            (make_shotgun(),                  (cx - 140, cy + 80)),
            (make_sniper(),                   (cx + 60,  cy - 120)),
            (make_ammo(AmmoType.CARBINE, 30), (cx + 180, cy - 40)),
            (make_ammo(AmmoType.SHOTGUN, 16), (cx - 60,  cy - 100)),
            (make_ammo(AmmoType.SNIPER,  5),  (cx - 180, cy + 40)),
            (make_light_armor(),              (cx + 240, cy + 120)),
            (make_medium_armor(),             (cx - 240, cy - 60)),
            (make_heavy_armor(),              (cx,       cy + 160)),
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
                elif event.key == pygame.K_r:
                    self.weapon.try_reload()
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
                    grabbed = self.hud.handle_world_mouse_down(
                        event.pos, self.world_items, self.camera.get_offset()
                    )
                    if not grabbed:
                        self.hud.handle_mouse_down(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    result = self.hud.handle_mouse_up(event.pos)
                    if result["kill_world_item"]:
                        result["kill_world_item"].kill()
                    if result["drop_item"]:
                        drop_pos = (
                            self.player.pos.x + self.player.facing.x * 48,
                            self.player.pos.y + self.player.facing.y * 48,
                        )
                        WorldItem(item=result["drop_item"], pos=drop_pos, groups=[self.world_items])
                    self._sync_weapon()

            elif event.type == pygame.MOUSEMOTION:
                self.hud.handle_mouse_motion(event.pos)
                self.hud.update_world_hover(event.pos, self.world_items, self.camera.get_offset())

    def _try_drop(self) -> None:
        from items.item import ItemType
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
        item   = self._nearby_world_item.item
        picked = False

        if isinstance(item, WeaponItem):
            from items.item import ItemType
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
        elif item.stackable:
            remainder = self._pickup_stackable(item)
            if remainder < item.stack_count:
                picked = True
                if remainder > 0:
                    item.stack_count = remainder
                    picked = False
        else:
            picked = self.player.backpack.add(item) or self.player.pouch.add(item)

        if picked:
            self._nearby_world_item.kill()
            self._nearby_world_item = None
            self._sync_weapon()

    def _pickup_stackable(self, item) -> int:
        remaining = item.stack_count
        for inv in [self.player.backpack, self.player.pouch]:
            for slot in inv.all_slots():
                if remaining <= 0:
                    break
                if (slot.item and type(slot.item) == type(item)
                        and hasattr(slot.item, 'ammo_type')
                        and slot.item.ammo_type == item.ammo_type
                        and slot.item.stack_count < slot.item.max_stack):
                    space = slot.item.max_stack - slot.item.stack_count
                    take  = min(space, remaining)
                    slot.item.stack_count += take
                    remaining -= take
            if remaining <= 0:
                break
        if remaining > 0:
            from items.ammo import AmmoItem
            temp = AmmoItem(item.ammo_type, remaining)
            for inv in [self.player.backpack, self.player.pouch]:
                if inv.add(temp):
                    remaining = 0
                    break
        return remaining

    def _update(self, dt: float) -> None:
        self.player.update(dt, self.level.walls)
        self.enemies.update(dt, self.level.walls)
        self.bullets.update(dt)
        self.enemy_bullets.update(dt)
        self.world_items.update(dt)
        self.weapon.update(dt, self.camera.get_offset())

        if pygame.mouse.get_pressed()[0] and not self.hud.is_open():
            self.weapon.try_shoot()

        self._check_bullet_hits()
        self._check_bullet_wall_hits()
        self._check_contact_damage()
        self._check_enemy_bullet_hits()
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
        active    = self.player.get_active_weapon()
        armor_pen = active.stats.armor_pen if active else 0
        hits = pygame.sprite.groupcollide(self.enemies, self.bullets, False, True)
        for enemy, bullet_list in hits.items():
            for bullet in bullet_list:
                damage, se = resolve_hit(
                    base_damage=bullet.damage,
                    base_se=bullet.stopping_effect,
                    armor_pen=armor_pen,
                    armor_class=enemy.armor_class,
                    settings=self.settings,
                )
                enemy.take_damage(damage)
                if se > 0 and bullet.velocity.length() > 0:
                    enemy.apply_stopping_effect(bullet.velocity, se)

    def _check_bullet_wall_hits(self) -> None:
        pygame.sprite.groupcollide(self.bullets, self.level.walls, True, False)

    def _check_contact_damage(self) -> None:
        s           = self.settings
        armor_class = self.player.get_armor_class()
        for enemy in self.enemies:
            damage, _ = resolve_hit(
                base_damage=s.enemy_contact_damage,
                base_se=0.0,
                armor_pen=0,
                armor_class=armor_class,
                settings=s,
            )
            enemy.try_deal_contact_damage(self.player, damage, s.enemy_contact_cooldown)

    def _draw(self) -> None:
        self.screen.fill(self.settings.bg_color)
        self._draw_grid()
        self._draw_sprites()
        self._draw_enemy_hp_bars()
        self.hud.draw_world_hover(self.screen, self.camera.get_offset())
        self._draw_pickup_hint()
        self.hud.draw(self.screen, i_hold_progress=self._i_held_time / self.settings.backpack_hold_time, weapon=self.weapon)
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
        for sprite in self.level.walls:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))
        for sprite in self.world_items:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))
        for sprite in [*self.bullets.sprites(), *self.enemies.sprites(), self.player]:
            self.screen.blit(sprite.image, self.camera.apply(sprite.rect))
        for sprite in [*self.enemy_bullets.sprites(), *self.bullets.sprites(), *self.enemies.sprites(), self.player]:
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
            f"enemy_bullets: {len(self.enemy_bullets)}",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (180, 220, 180))
            self.screen.blit(surf, (10, 10 + i * 20))
        p.draw_debug(self.screen, self.camera.get_offset())
