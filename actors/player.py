import pygame
from actors.actor import Actor
from items.stats import Stats
from items.inventory import Inventory, GridInventory
from items.item import ItemType
from core.settings import Settings
from core.managers.faction_manager import Faction

LEGS_SPEED_MULT = 0.6


class StepEvent:
    def __init__(self, pos: pygame.math.Vector2, radius: float) -> None:
        self.pos    = pygame.math.Vector2(pos)
        self.radius = radius


class Player(Actor):
    """
    Human-controlled actor.
    WASD — движение, Shift — спринт, Space — dash, Ctrl — крадёмся.

    Debuff конечностей:
      arms_damaged — spread x2, reload_time x1.5
      legs_damaged — скорость x0.6, dash недоступен
    Снимается heal_limbs() (surgical_kit).
    """

    def __init__(self, pos: tuple[float, float], settings: Settings, groups: list = ()) -> None:
        super().__init__(
            pos=pos,
            size=settings.player_size,
            color=settings.player_color,
            groups=groups,
        )
        self.settings = settings
        self.surface_map: dict = {}
        self.faction  = Faction.PLAYER

        # загружаем спрайт-шит и нарезаем кадры (4 кадра по 32x32)
        # кадр 0 — покой, 1 и 2 — движение, 3 — рывок
        import os
        _path = os.path.join(os.path.dirname(__file__),
                             '..', 'assets', 'actors', 'player.png')
        sz = settings.player_size
        if os.path.exists(_path):
            raw = pygame.image.load(_path).convert_alpha()
            frame_w = raw.get_width() // 4  # 32px при sheet 128x32
            frame_h = raw.get_height()      # 32px
            # нарезаем и масштабируем все 4 кадра до player_size
            self._anim_frames: list[pygame.Surface] = [
                pygame.transform.smoothscale(
                    raw.subsurface(pygame.Rect(i * frame_w, 0, frame_w, frame_h)),
                    (sz, sz)
                )
                for i in range(4)
            ]
        else:
            # запасной вариант: одноцветные квадраты
            self._anim_frames = []
            for _ in range(4):
                surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
                surf.fill(settings.player_color)
                self._anim_frames.append(surf)

        self._anim_frame_idx: int   = 0   # текущий кадр внутри цикла
        self._anim_timer: float     = 0.0
        self._anim_walk_speed: float = 0.15  # секунд на кадр при ходьбе
        self._anim_run_speed: float  = 0.10  # секунд на кадр при беге

        self.image = self._anim_frames[0]
        self.rect  = self.image.get_rect(center=pos)

        self.stats    = Stats()
        self.speed    = self.stats.speed

        self.facing    = pygame.math.Vector2(0, 1)
        self._move_dir = pygame.math.Vector2(0, 0)

        self.stamina: float        = self.stats.max_stamina
        self._dash_cooldown: float = 0.0
        self._dash_timer: float    = 0.0
        self._dash_velocity        = pygame.math.Vector2(0, 0)
        self._is_dashing: bool     = False
        self.is_sprinting: bool    = False
        self.is_crouching: bool    = False

        # шлейф дэша: список (image_copy, pos_copy, age)
        self.dash_ghosts: list[tuple[pygame.Surface, pygame.math.Vector2, float]] = []
        self._ghost_timer: float = 0.0
        self._GHOST_INTERVAL: float = 0.018   # каждые N секунд новый ghost
        self._GHOST_LIFETIME: float = 0.18    # сколько живёт каждый ghost

        self._step_timer: float   = 0.0
        self._pending_steps: list = []

        self.arms_damaged: bool = False
        self.legs_damaged: bool = False

        self._using_item             = None  # TimedConsumable | None
        self._using_slot             = None  # слот откуда берём
        self.use_timer: float        = 0.0
        self.use_time_total: float   = 0.0

        self.pouch = Inventory(
            capacity=4,
            typed_slots=[ItemType.WEAPON, ItemType.WEAPON, ItemType.HELMET, ItemType.ARMOR],
            owner=self,
        )
        self.backpack = GridInventory(cols=8, rows=6)
        self.active_weapon_slot: int = 0

    def start_timed_use(self, item, slot) -> bool:
        """Начать применение TimedConsumable. False если уже применяем."""
        if self._using_item is not None:
            return False
        self._using_item    = item
        self._using_slot    = slot
        self.use_timer      = 0.0
        self.use_time_total = item.use_time
        return True

    def cancel_use(self) -> None:
        self._using_item  = None
        self._using_slot  = None
        self.use_timer    = 0.0

    @property
    def is_using_item(self) -> bool:
        return self._using_item is not None

    def _update_timed_use(self, dt: float) -> None:
        if self._using_item is None:
            return
        self.use_timer += dt
        if self.use_timer >= self.use_time_total:
            self._using_item.apply(self)
            if self._using_slot is not None:
                self._using_slot.take()
            self._using_item = None
            self._using_slot = None
            self.use_timer   = 0.0

    def apply_arms_debuff(self) -> None:
        self.arms_damaged = True

    def apply_legs_debuff(self) -> None:
        self.legs_damaged = True

    def heal_limbs(self) -> None:
        self.arms_damaged = False
        self.legs_damaged = False

    def get_active_weapon(self):
        weapon_slots = [s for s in self.pouch.typed_slots if s.allowed_type == ItemType.WEAPON]
        if self.active_weapon_slot >= len(weapon_slots):
            return None
        slot = weapon_slots[self.active_weapon_slot]
        return slot.item if not slot.empty else None

    def get_armor_class(self) -> int:
        from items.armor import Armor
        armor_slots = [s for s in self.pouch.typed_slots if s.allowed_type == ItemType.ARMOR]
        if armor_slots and not armor_slots[0].empty:
            item = armor_slots[0].item
            if isinstance(item, Armor):
                return item.tier
        return 0

    def get_helmet_class(self) -> int:
        from items.armor import Helmet
        helmet_slots = [s for s in self.pouch.typed_slots if s.allowed_type == ItemType.HELMET]
        if helmet_slots and not helmet_slots[0].empty:
            item = helmet_slots[0].item
            if isinstance(item, Helmet):
                return item.tier
        return 0

    def switch_weapon(self, slot_index: int) -> bool:
        weapon_slots = [s for s in self.pouch.typed_slots if s.allowed_type == ItemType.WEAPON]
        if slot_index >= len(weapon_slots):
            return False
        self.active_weapon_slot = slot_index
        return True

    def try_dash(self) -> None:
        if self.legs_damaged:
            return
        if self._is_dashing or self._dash_cooldown > 0:
            return
        if self.stamina < self.stats.dash_stamina_cost:
            return
        direction = self._move_dir if self._move_dir.length() > 0 else self.facing
        self.stamina        -= self.stats.dash_stamina_cost
        self._is_dashing     = True
        self._dash_timer     = self.stats.dash_duration
        self._dash_cooldown  = self.stats.dash_cooldown
        dash_speed           = self.stats.dash_distance / self.stats.dash_duration
        self._dash_velocity  = direction.normalize() * dash_speed
        self._emit_step(self.settings.step_radius_dash)

    def pop_step_events(self) -> list:
        events = self._pending_steps[:]
        self._pending_steps.clear()
        return events

    def _emit_step(self, radius: float) -> None:
        self._pending_steps.append(StepEvent(self.pos, radius))

    def _handle_input(self) -> None:
        keys = pygame.key.get_pressed()

        direction = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:    direction.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  direction.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  direction.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: direction.x += 1
        if direction.length() > 0:
            direction = direction.normalize()

        self._move_dir = direction

        ctrl_held  = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        self.is_crouching = ctrl_held and not self._is_dashing
        self.is_sprinting = (
            shift_held
            and direction.length() > 0
            and not self._is_dashing
            and not self.is_crouching
            and self.stamina > 0
        )

        if not self._is_dashing:
            speed = self.speed * (LEGS_SPEED_MULT if self.legs_damaged else 1.0)
            if self.is_crouching:
                self.velocity = direction * speed * self.settings.crouch_speed_mult
            elif self.is_sprinting:
                self.velocity = direction * speed * self.stats.sprint_multiplier
            else:
                self.velocity = direction * speed

    def _update_dash(self, dt: float) -> None:
        self._dash_cooldown = max(0.0, self._dash_cooldown - dt)

        # обновляем возраст ghostов
        self.dash_ghosts = [
            (img, pos, age + dt)
            for img, pos, age in self.dash_ghosts
            if age + dt < self._GHOST_LIFETIME
        ]

        if self._is_dashing:
            self._dash_timer -= dt
            self.velocity = self._dash_velocity

            # спавним новый ghost с интервалом
            self._ghost_timer -= dt
            if self._ghost_timer <= 0:
                self._ghost_timer = self._GHOST_INTERVAL
                self.dash_ghosts.append((
                    self.image.copy(),
                    pygame.math.Vector2(self.pos),
                    0.0,
                ))

            if self._dash_timer <= 0:
                self._is_dashing  = False
                self._ghost_timer = 0.0
                self.velocity     = self._move_dir * self.speed

    def _update_stamina(self, dt: float) -> None:
        if self._is_dashing:
            return
        if self.is_sprinting:
            self.stamina = max(0.0, self.stamina - self.stats.sprint_stamina_drain * dt)
        else:
            self.stamina = min(
                self.stats.max_stamina,
                self.stamina + self.stats.stamina_regen * dt,
            )

    def _get_surface_mult(self) -> float:
        """Множитель радиуса шага по типу поверхности под игроком."""
        ts  = self.settings.grid_size
        tx  = int(self.pos.x) // ts
        ty  = int(self.pos.y) // ts
        surface = self.surface_map.get((tx, ty), "default")
        return {
            "grass":    0.5,    # трава — тише обычного
            "concrete": 1.0,    # бетон — норма
            "asphalt":  1.3,    # асфальт — громче
            "metal":    2.2,    # металл — очень громко
            "default":  1.0,
        }.get(surface, 1.0)

    def _get_step_radius_mult(self) -> float:
        from items.armor import Armor
        armor_slots = [s for s in self.pouch.typed_slots if s.allowed_type == ItemType.ARMOR]
        if armor_slots and not armor_slots[0].empty:
            item = armor_slots[0].item
            if isinstance(item, Armor):
                return item.step_radius_mult
        return 1.0

    def _update_footsteps(self, dt: float) -> None:
        moving = self._move_dir.length() > 0 and not self._is_dashing
        if not moving:
            self._step_timer = 0.0
            return
        s    = self.settings
        mult = self._get_step_radius_mult() * self._get_surface_mult()
        if self.is_crouching:
            interval = s.step_interval_crouch
            radius   = s.step_radius_crouch * mult
        elif self.is_sprinting:
            interval = s.step_interval_sprint
            radius   = s.step_radius_sprint * mult
        else:
            interval = s.step_interval_walk
            radius   = s.step_radius_walk * mult
        self._step_timer += dt
        if self._step_timer >= interval:
            self._step_timer = 0.0
            self._emit_step(radius)

    def _update_animation(self, dt: float) -> None:
        """
        Обновляет кадр спрайта в зависимости от состояния игрока.

        Логика:
          - рывок (_is_dashing)        → кадр 3 (статично, без смены)
          - стоит (движение == 0)      → кадр 0 (покой, статично)
          - движется (ходьба / бег)    → цикл кадров 1 → 2 → 1 → 2 …
        """
        if not self._anim_frames:
            return

        is_moving = self._move_dir.length() > 0

        if self._is_dashing:
            # рывок: фиксированный 4-й кадр (индекс 3)
            self._anim_frame_idx = 3
            self._anim_timer     = 0.0
        elif not is_moving:
            # покой: 1-й кадр (индекс 0)
            self._anim_frame_idx = 0
            self._anim_timer     = 0.0
        else:
            # движение: чередуем кадры 1 и 2
            speed = self._anim_run_speed if self.is_sprinting else self._anim_walk_speed
            self._anim_timer += dt
            if self._anim_timer >= speed:
                self._anim_timer -= speed
                # переключаем между индексами 1 и 2
                self._anim_frame_idx = 1 if self._anim_frame_idx != 1 else 2

        old_center = self.rect.center
        frame = self._anim_frames[self._anim_frame_idx]
        # флип по горизонтали когда смотрим влево
        facing_left = self.facing.x < 0
        if facing_left:
            frame = pygame.transform.flip(frame, True, False)
        self.image = frame
        self.rect  = self.image.get_rect(center=old_center)

    def update(self, dt: float, walls: pygame.sprite.Group = None) -> None:
        self._handle_input()
        self._update_dash(dt)
        self._update_stamina(dt)
        self._update_footsteps(dt)
        self._update_timed_use(dt)
        self._update_animation(dt)
        super().update(dt, walls)
