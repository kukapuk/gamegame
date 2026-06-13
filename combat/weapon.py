import pygame
import math
import random
from core.settings import Settings
from combat.bullet import Bullet
from items.weapon_item import WeaponItem, DIRTY_THRESHOLD, FILTHY_THRESHOLD
from items.ammo import AmmoItem

UNJAM_TIME = 0.5   # секунд на передёргивание затвора


class Weapon(pygame.sprite.Sprite):
    """
    Визуальный спрайт оружия, прикреплённый к владельцу.
    Управляет магазином, перезарядкой, загрязнением, клином, unjam.
    """

    def __init__(
        self,
        owner,
        settings: Settings,
        bullet_group: pygame.sprite.Group,
        all_sprites: pygame.sprite.Group,
        weapon_item: WeaponItem = None,
    ) -> None:
        super().__init__(all_sprites)

        self.owner        = owner
        self.settings     = settings
        self.bullet_group = bullet_group
        self.all_sprites  = all_sprites

        self._fire_cooldown: float = 0.0
        self._reload_timer: float  = 0.0
        self.reloading: bool       = False
        self.mag_current: int      = 0
        self.aim_dir = pygame.math.Vector2(1, 0)

        self._recoil_offset: float = 0.0

        # first shot
        self._first_shot: bool       = True
        self._silence_timer: float   = 0.0
        self._silence_threshold: float = 1.5  # сек без стрельбы → first_shot снова

        # unjam
        self.unjamming: bool        = False
        self._unjam_timer: float    = 0.0

        self._weapon_item: WeaponItem = None
        self._base_image = pygame.Surface((
            settings.weapon_width, settings.weapon_height
        ), pygame.SRCALPHA)
        self._base_image.fill(settings.weapon_color)
        self.image = self._base_image.copy()
        self.rect  = self.image.get_rect()

        if weapon_item:
            self.equip(weapon_item)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def has_weapon(self) -> bool:
        return self._weapon_item is not None

    @property
    def mag_size(self) -> int:
        return self._weapon_item.stats.mag_size if self._weapon_item else 0

    @property
    def jammed(self) -> bool:
        return self._weapon_item.jammed if self._weapon_item else False

    # ------------------------------------------------------------------ #
    # Equip
    # ------------------------------------------------------------------ #

    def equip(self, weapon_item) -> None:
        self._weapon_item   = weapon_item
        self._fire_cooldown = 0.0
        self.reloading      = False
        self._reload_timer  = 0.0
        self._recoil_offset = 0.0
        self.unjamming      = False
        self._unjam_timer   = 0.0
        self._first_shot    = True
        self._silence_timer = 0.0
        if weapon_item:
            s = weapon_item.stats
            self._build_visual(s.width, s.height, s.color)
            if weapon_item.mag_current < 0:
                weapon_item.mag_current = self._take_ammo(s.mag_size)
            self.mag_current = weapon_item.mag_current
        else:
            self.mag_current = 0

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def try_reload(self) -> None:
        if not self._weapon_item:
            return
        if self.reloading or self.unjamming:
            return
        if (not self._weapon_item.jammed
                and self.mag_current == self._weapon_item.stats.mag_size):
            return
        if self._find_ammo_count() == 0:
            return
        # перезарядка снимает клин автоматически
        self._weapon_item.jammed = False
        self.reloading           = True
        reload_time = self._weapon_item.stats.reload_time
        if getattr(self.owner, "arms_damaged", False):
            reload_time *= 1.5
        self._reload_timer = reload_time

    def try_unjam(self) -> None:
        """Q — передёрнуть затвор: снимает клин и выбрасывает патрон.
        Работает в любой момент — даже без клина, просто выбрасывает патрон."""
        if not self._weapon_item:
            return
        if self.unjamming or self.reloading:
            return
        if self.mag_current <= 0:
            return
        self.unjamming    = True
        self._unjam_timer = UNJAM_TIME

    def try_shoot(self) -> bool:
        if not self._weapon_item or self.reloading or self.unjamming:
            return False
        if self._weapon_item.jammed:
            return False
        if self._fire_cooldown > 0:
            return False
        if self.mag_current <= 0:
            self.try_reload()
            return False

        s = self._weapon_item.stats

        # проверка клина перед выстрелом
        jam_roll = random.random()
        if jam_roll < self._weapon_item.jam_chance():
            self._weapon_item.jammed = True
            return False

        self._fire_cooldown = s.fire_rate
        self.mag_current   -= 1
        self._weapon_item.mag_current = self.mag_current

        # загрязнение
        self._weapon_item.cleanliness = max(
            0.0, self._weapon_item.cleanliness - s.dirt_per_shot
        )

        # спавн пуль
        w      = self._base_image.get_width()
        offset = self.aim_dir * (self.settings.weapon_offset + w)
        spawn  = self.owner.pos + offset

        effective_spread = self._weapon_item.effective_spread()
        arms_mult = 2.0 if getattr(self.owner, "arms_damaged", False) else 1.0
        for _ in range(s.pellets):
            spread = effective_spread * arms_mult
            if self._first_shot:
                spread += s.first_shot_spread
            direction = self._apply_spread(self.aim_dir, spread)
            Bullet(
                pos=(spawn.x, spawn.y),
                direction=direction,
                speed=s.bullet_speed,
                lifetime=s.bullet_lifetime,
                damage=s.damage,
                size=s.bullet_size,
                color=s.bullet_color,
                stopping_effect=s.stopping_effect,
                groups=[self.bullet_group, self.all_sprites],
                can_ricochet=s.ricochet,
                ricochet_spread=s.ricochet_spread,
                ricochet_damage_mult=s.ricochet_damage_mult,
            )

        self._first_shot    = False
        self._silence_timer = 0.0
        self._recoil_offset = s.recoil_distance

        if self.mag_current == 0:
            self.try_reload()

        return True

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #

    def update(self, dt: float, camera_offset: pygame.math.Vector2, hud_open: bool = False) -> None:
        self._fire_cooldown = max(0.0, self._fire_cooldown - dt)
        self._update_reload(dt)
        self._update_unjam(dt)
        self._update_recoil(dt)
        self._update_first_shot(dt)
        self._update_aim(camera_offset, hud_open)
        self._update_transform()

    def _update_first_shot(self, dt: float) -> None:
        if self._first_shot:
            return
        self._silence_timer += dt
        if self._silence_timer >= self._silence_threshold:
            self._first_shot    = True
            self._silence_timer = 0.0

    def _update_unjam(self, dt: float) -> None:
        if not self.unjamming:
            return
        self._unjam_timer -= dt
        if self._unjam_timer <= 0:
            self.unjamming               = False
            self._weapon_item.jammed     = False
            self.mag_current            -= 1
            self._weapon_item.mag_current = self.mag_current

    def _update_recoil(self, dt: float) -> None:
        if self._recoil_offset <= 0:
            return
        recovery = (self._weapon_item.stats.recoil_recovery
                    if self._weapon_item else 12.0)
        self._recoil_offset -= self._recoil_offset * recovery * dt
        if self._recoil_offset < 0.2:
            self._recoil_offset = 0.0

    def _update_reload(self, dt: float) -> None:
        if not self.reloading:
            return
        self._reload_timer -= dt
        if self._reload_timer <= 0:
            self.reloading   = False
            needed           = self._weapon_item.stats.mag_size
            self.mag_current = self._take_ammo(needed)
            self._weapon_item.mag_current = self.mag_current

    # ------------------------------------------------------------------ #
    # Ammo helpers
    # ------------------------------------------------------------------ #

    def _find_ammo_count(self) -> int:
        if not self._weapon_item:
            return 0
        ammo_type = self._weapon_item.stats.ammo_type
        total = 0
        for slot in self.owner.pouch.all_slots():
            if slot.item and isinstance(slot.item, AmmoItem):
                if slot.item.ammo_type == ammo_type:
                    total += slot.item.stack_count
        for item in self.owner.backpack.all_items():
            if isinstance(item, AmmoItem) and item.ammo_type == ammo_type:
                total += item.stack_count
        return total

    def _take_ammo(self, needed: int) -> int:
        if not self._weapon_item:
            return 0
        if not hasattr(self.owner, 'pouch') or not hasattr(self.owner, 'backpack'):
            return 0
        ammo_type = self._weapon_item.stats.ammo_type
        taken = 0

        # pouch — старый Inventory, итерируем по слотам
        for slot in self.owner.pouch.all_slots():
            if needed <= 0:
                break
            if slot.item and isinstance(slot.item, AmmoItem):
                if slot.item.ammo_type == ammo_type:
                    take = min(slot.item.stack_count, needed)
                    slot.item.stack_count -= take
                    taken  += take
                    needed -= take
                    if slot.item.stack_count <= 0:
                        slot.item = None

        # backpack — GridInventory, итерируем по предметам
        for item in list(self.owner.backpack.all_items()):
            if needed <= 0:
                break
            if isinstance(item, AmmoItem) and item.ammo_type == ammo_type:
                take = min(item.stack_count, needed)
                item.stack_count -= take
                taken  += take
                needed -= take
                if item.stack_count <= 0:
                    self.owner.backpack.remove(item)

        return taken

    # Visual helpers

    def _build_visual(self, w: int, h: int, color: tuple) -> None:
        sprite = None
        if self._weapon_item:
            try:
                from combat.weapon_sprites import get_weapon_sprite
                sprite = get_weapon_sprite(self._weapon_item.name)
            except Exception:
                pass

        if sprite is not None:
            self._base_image = pygame.transform.scale(sprite, (w, h))
        else:
            self._base_image = pygame.Surface((w, h), pygame.SRCALPHA)
            self._base_image.fill(color)

    def _apply_spread(self, direction: pygame.math.Vector2, spread_deg: float) -> pygame.math.Vector2:
        if spread_deg == 0:
            return direction.copy()
        angle        = math.radians(random.uniform(-spread_deg / 2, spread_deg / 2))
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return pygame.math.Vector2(
            direction.x * cos_a - direction.y * sin_a,
            direction.x * sin_a + direction.y * cos_a,
        )

    def _update_aim(self, camera_offset: pygame.math.Vector2, hud_open: bool = False) -> None:
        mouse_screen  = pygame.math.Vector2(pygame.mouse.get_pos())
        player_screen = self.owner.pos - camera_offset

        should_clamp = (
            self._weapon_item is not None
            and self._weapon_item.stats.aim_radius > 0
            and not hud_open
        )
        if should_clamp:
            radius = self._weapon_item.stats.aim_radius
            delta  = mouse_screen - player_screen
            if delta.length() > radius:
                clamped      = player_screen + delta.normalize() * radius
                mouse_screen = clamped
                pygame.mouse.set_pos(round(clamped.x), round(clamped.y))

        delta = mouse_screen - player_screen
        if delta.length() > 0:
            self.aim_dir      = delta.normalize()
            self.owner.facing = self.aim_dir.copy()

    def _update_transform(self) -> None:
        angle      = -math.degrees(math.atan2(self.aim_dir.y, self.aim_dir.x))
        self.image = pygame.transform.rotate(self._base_image, angle)
        self.rect  = self.image.get_rect()
        offset     = self.aim_dir * (self.settings.weapon_offset - self._recoil_offset)
        self.rect.center = (
            round(self.owner.pos.x + offset.x),
            round(self.owner.pos.y + offset.y),
        )
