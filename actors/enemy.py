"""
enemy.py — Enemy класс со state machine и AI.
"""
import pygame
import math
from actors.actor import Actor
from actors.geometry import segment_intersects_rect, ray_rect_hit_point
from items.stats import Stats
from core.managers.faction_manager import Faction


class EnemyState:
    IDLE    = "idle"
    CHASE   = "chase"
    SEARCH  = "search"
    ALERT   = "alert"
    RETREAT = "retreat"
    COVER    = "cover"    # движется к укрытию
    PEEK     = "peek"     # выглядывает из укрытия и стреляет
    SUPPRESS = "suppress" # подавляющий огонь без прямой видимости
    FLANK    = "flank"    # обходной манёвр с фланга


DEBUG_COLORS = {
    EnemyState.IDLE:    (80,  200, 80,  40),
    EnemyState.CHASE:   (220, 80,  80,  40),
    EnemyState.SEARCH:  (220, 180, 60,  40),
    EnemyState.ALERT:   (180, 120, 220, 40),
    EnemyState.RETREAT: (80,  160, 220, 40),
    EnemyState.COVER:   (60,  180, 220, 40),
    EnemyState.PEEK:     (220, 140, 60,  40),
    EnemyState.SUPPRESS: (220, 80,  180, 40),
    EnemyState.FLANK:    (80,  220, 180, 40),
}


class Enemy(Actor):
    """
    Стейт-машина: IDLE → CHASE → SEARCH → ALERT → IDLE.
    SEARCH: идёт к последней известной позиции, крутится.
    ALERT:  стоит на месте, насторожён, через timeout → IDLE.
    """

    KNOCKBACK_FRICTION = 8.0
    VISION_ANGLE       = 125.0
    VISION_RANGE       = 280.0   # базовый — переопределяется в фабриках
    SEARCH_ROTATE_TIME = 2.5
    ALERT_TIMEOUT      = 10.0
    ALERT_REACT_DELAY  = 0.4   # базовый — переопределяется в фабриках
    ROTATE_SPEED       = 90.0

    def __init__(
        self,
        pos:         tuple[float, float],
        target:      Actor,
        armor_class: int = 0,
        groups:      list = (),
    ) -> None:
        super().__init__(pos=pos, size=28, color=(220, 60, 60), groups=groups)

        self.target       = target
        self.armor_class  = armor_class
        self.helmet_class = 0
        self.walls        = None
        self.faction      = Faction.BANDIT   # переопределяется в фабриках

        self.stats  = Stats(max_hp=60, speed=120.0, dash_cooldown=999, dash_stamina_cost=999)
        self.hp     = self.stats.max_hp
        self.max_hp = self.stats.max_hp
        self.speed  = self.stats.speed

        self._contact_cooldown: float = 0.0
        self._stun_timer:       float = 0.0
        self._knockback_vel           = pygame.math.Vector2(0, 0)

        self.state:    str = EnemyState.IDLE
        self._ai_update    = self._ai_grunt

        self._last_known_pos:      pygame.math.Vector2 = pygame.math.Vector2(pos)
        self._search_rotate_timer: float = 0.0
        self._alert_timer:         float = 0.0
        self._alert_react_timer:   float = 0.0
        self.reaction_delay:       float = self.ALERT_REACT_DELAY  # задержка реакции
        self._facing_angle:        float = 0.0

        self._path:          list  = []
        self._path_timer:    float = 0.0
        self._path_interval: float = 0.4
        self.pathfinder            = None

        self.patrol_group          = None   # PatrolGroup | None
        self._retreat_point            = None   # Vector2 — точка отхода
        self._cover_point              = None   # Vector2 — точка укрытия
        self._peek_timer:      float   = 0.0    # сколько выглядывает
        self._cover_cooldown:  float   = 0.0    # пауза перед следующим поиском укрытия
        self._suppress_timer:  float   = 0.0    # сколько ещё подавляем
        self._flank_point              = None   # Vector2 — цель обхода
        self._strafe_dir:      float   = 1.0    # +1 или -1, меняется редко
        self._strafe_timer:    float   = 0.0
        self._flank_phase:     int     = 0       # 0=идём к точке, 1=атакуем
        self.use_cover:        bool    = False   # включить cover AI (военные/элита)
        self._broken:                  bool  = False  # отступил — больше не атакует
        self.enemies_group         = None
        self._popup_group          = None
        self._separation_radius:   float = 40.0
        self._separation_force:    float = 180.0

        self.can_shoot:          bool  = False
        self._shoot_cooldown:    float = 0.0
        self._shoot_rate:        float = 0.0
        self._preferred_dist:    float = 0.0
        self._bullet_group             = None
        self._all_sprites              = None
        self._bullet_speed:      float = 0.0
        self._bullet_damage:     int   = 0
        self._bullet_armor_pen:  int   = 0
        self._bullet_color:      tuple = (255, 200, 50)

        # новое оружие с магазином/перезарядкой/режимами (None = legacy режим)
        self.enemy_weapon              = None   # EnemyWeapon | None
        self._sound_callback           = None   # (pos, radius) → None

        self.weapon_image: pygame.Surface = None
        self.weapon_rect:  pygame.Rect    = None
        self._weapon_w:    int   = 0
        self._weapon_h:    int   = 0
        self._weapon_color: tuple = (160, 160, 160)

        self.vision_range: float = self.VISION_RANGE
        self.vision_angle: float = self.VISION_ANGLE

        self._patrol_points:  list = []
        self._patrol_index:   int  = 0
        self._patrol_arrived: bool = False
        self.tile_size:       int  = 64

    # ── Public ────────────────────────────────────────────────────────

    def apply_stopping_effect(self, bullet_direction: pygame.math.Vector2, stopping_effect: float) -> None:
        self._knockback_vel = bullet_direction.normalize() * stopping_effect * 420.0
        self._stun_timer    = stopping_effect * 0.45

    def try_deal_contact_damage(self, target: Actor, damage: int, cooldown: float) -> None:
        if self._contact_cooldown > 0:
            return
        if self.rect.colliderect(target.rect):
            target.take_damage(damage)
            self._contact_cooldown = cooldown

    def take_damage(self, amount: int) -> None:
        from actors.effects import DamagePopup
        from combat.calculator import HitZone
        headshot = getattr(self, "last_hit_zone", None) == HitZone.HEAD
        if self._popup_group is not None and amount > 0:
            DamagePopup(self.pos, amount, headshot=headshot, groups=[self._popup_group])
        was_alive = self.alive
        super().take_damage(amount)
        if was_alive and not self.alive:
            self._notify_allies_of_death()
        elif was_alive and self.use_cover and amount > 0:
            if self.state == EnemyState.CHASE and self._cover_cooldown <= 0:
                self.state        = EnemyState.COVER
                self._cover_point = None
                self._cover_cooldown = 8.0   # не чаще раза в 8 сек

    def _notify_allies_of_death(self) -> None:
        # группа реагирует первой — ближайший идёт проверить
        if self.patrol_group:
            self.patrol_group.notify_member_dead(self.pos)

        # общий механизм: враги в радиусе вне группы — ALERT
        if not self.enemies_group:
            return
        for other in self.enemies_group:
            if other is self:
                continue
            if other.patrol_group is self.patrol_group and self.patrol_group:
                continue  # группа уже обработала своих
            if (other.pos - self.pos).length() <= self.VISION_RANGE * 1.5:
                if other.state == EnemyState.IDLE:
                    other.state              = EnemyState.ALERT
                    other._alert_timer       = other.ALERT_TIMEOUT
                    other._alert_react_timer = other.ALERT_REACT_DELAY
                    other._last_known_pos    = pygame.math.Vector2(self.pos)

    def set_patrol(self, points: list[tuple[float, float]]) -> None:
        self._patrol_points = [pygame.math.Vector2(p) for p in points]
        self._patrol_index  = 0

    def hear_sound(self, world_pos: pygame.math.Vector2, radius: float) -> None:
        if self.state == EnemyState.CHASE:
            return
        if (self.pos - world_pos).length() > radius:
            return
        self._last_known_pos    = pygame.math.Vector2(world_pos)
        self._alert_react_timer = self.reaction_delay
        self.state = EnemyState.ALERT

    def hear_reload(self, world_pos: pygame.math.Vector2, radius: float) -> None:
        """
        Игрок перезаряжается — элита немедленно атакует (push on reload).
        Обычные враги игнорируют.
        """
        from core.managers.faction_manager import Faction
        if self.faction != Faction.ELITE:
            return
        if (self.pos - world_pos).length() > radius:
            return
        if self.state == EnemyState.CHASE:
            # уже в бою — просто форсируем движение к игроку
            self._last_known_pos = pygame.math.Vector2(self.target.pos)
            self._cover_cooldown = 0.0   # отменяем укрытие
            if self.state in (EnemyState.COVER, EnemyState.SUPPRESS):
                self.state = EnemyState.CHASE
                self._path = []
            return
        # не в бою — поднимаем тревогу и атакуем
        self._last_known_pos    = pygame.math.Vector2(self.target.pos)
        self._alert_react_timer = 0.0
        self.state              = EnemyState.CHASE
        self._path              = []
        if self.patrol_group:
            self.patrol_group.raise_alarm(self.target.pos, source=self)

    def take_hit_from_direction(self, bullet_velocity: pygame.math.Vector2) -> None:
        if bullet_velocity.length() == 0:
            return
        estimated_origin     = self.pos - bullet_velocity.normalize() * 300.0
        self._last_known_pos = estimated_origin
        self.state           = EnemyState.CHASE
        self._path           = []

    def can_see_target(self) -> bool:
        from core.managers.faction_manager import faction_mgr
        # не атакуем не-враждебных
        target_faction = getattr(self.target, 'faction', None)
        if target_faction is not None:
            if not faction_mgr.is_hostile(self.faction, target_faction,
                                          a_id=id(self)):
                return False

        delta = self.target.pos - self.pos
        if delta.length() > self.vision_range:
            return False

        angle_to_target = math.degrees(math.atan2(delta.y, delta.x))
        facing_angle    = math.degrees(math.atan2(self.facing.y, self.facing.x))
        diff = (angle_to_target - facing_angle + 180) % 360 - 180
        if abs(diff) > self.vision_angle / 2:
            return False

        return not self._ray_hits_wall(self.pos, self.target.pos)

    # ── Vision / geometry ─────────────────────────────────────────────

    def _ray_hits_wall(self, start: pygame.math.Vector2, end: pygame.math.Vector2) -> bool:
        if not self.walls:
            return False
        for wall in self.walls:
            if segment_intersects_rect(start, end, wall.rect):
                return True
        return False

    # ── Movement ──────────────────────────────────────────────────────

    def _apply_separation(self) -> None:
        if not self.enemies_group:
            return
        push = pygame.math.Vector2(0, 0)
        for other in self.enemies_group:
            if other is self:
                continue
            delta = self.pos - other.pos
            dist  = delta.length()
            if 0 < dist < self._separation_radius:
                push += delta.normalize() * (self._separation_radius - dist)
        if push.length() > 0:
            # добавляем как часть velocity, но не превышаем speed
            sep = push.normalize() * self._separation_force
            combined = self.velocity + sep
            if combined.length() > self.speed * 1.4:
                combined = combined.normalize() * self.speed * 1.4
            self.velocity = combined

    def _follow_path_to(self, destination: pygame.math.Vector2, dt: float) -> None:
        self._path_timer -= dt
        if self._path_timer <= 0:
            self._path_timer = self._path_interval
            if self.pathfinder:
                self._path = self.pathfinder.find_path(self.pos, destination)

        if not self._path:
            delta = destination - self.pos
            if delta.length() > 1:
                self.velocity = delta.normalize() * self.speed
            else:
                self.velocity.update(0, 0)
            return

        next_point = self._path[1] if len(self._path) > 1 else self._path[0]
        delta = next_point - self.pos
        # порог перехода к следующей точке — фиксированный, не зависит от speed
        if delta.length() < 18 and len(self._path) > 1:
            self._path.pop(0)
            next_point = self._path[1] if len(self._path) > 1 else self._path[0]
            delta = next_point - self.pos
        if delta.length() > 1:
            self.velocity = delta.normalize() * self.speed
        else:
            self.velocity.update(0, 0)

    # ── State machine ─────────────────────────────────────────────────

    def _update_facing(self) -> None:
        if self.velocity.length() > 0.5:
            target_facing = self.velocity.normalize()
            # плавный поворот — lerp 15% в кадр
            lerp = 0.15
            new_facing = self.facing + (target_facing - self.facing) * lerp
            if new_facing.length() > 0.01:
                self.facing        = new_facing.normalize()
                self._facing_angle = math.degrees(math.atan2(self.facing.y, self.facing.x))

    def _update_state(self, dt: float) -> None:
        if self.state == EnemyState.RETREAT:
            return   # отход не прерывается — только PatrolGroup сбрасывает
        if self.state in (EnemyState.COVER, EnemyState.PEEK,
                            EnemyState.SUPPRESS, EnemyState.FLANK):
            # cover/flank AI управляет переходами сам
            if self.can_see_target():
                self._last_known_pos = pygame.math.Vector2(self.target.pos)
            return

        if self.state == EnemyState.IDLE:
            if self.can_see_target():
                self._last_known_pos = pygame.math.Vector2(self.target.pos)
                self.state = EnemyState.CHASE
                if self.patrol_group:
                    self.patrol_group.raise_alarm(self.target.pos, source=self)

        elif self.state == EnemyState.CHASE:
            if self.can_see_target():
                self._last_known_pos = pygame.math.Vector2(self.target.pos)
            elif self.use_cover and self._cover_cooldown <= 0:
                # военные/элита — подавляют пока идут в укрытие
                self._suppress_timer = 2.5
                self.state           = EnemyState.SUPPRESS
            else:
                self.state = EnemyState.SEARCH
                self._search_rotate_timer = self.SEARCH_ROTATE_TIME
                self._path = []

        elif self.state == EnemyState.SEARCH:
            if self.can_see_target():
                self._last_known_pos = pygame.math.Vector2(self.target.pos)
                self.state = EnemyState.CHASE
                if self.patrol_group:
                    self.patrol_group.raise_alarm(self.target.pos, source=self)

        elif self.state == EnemyState.ALERT:
            self._alert_timer -= dt
            if self.can_see_target():
                self._alert_react_timer -= dt
                if self._alert_react_timer <= 0:
                    self._last_known_pos = pygame.math.Vector2(self.target.pos)
                    self.state = EnemyState.CHASE
                    if self.patrol_group:
                        self.patrol_group.raise_alarm(self.target.pos, source=self)
            else:
                self._alert_react_timer = self.ALERT_REACT_DELAY
            if self._alert_timer <= 0:
                self.state = EnemyState.IDLE

    # ── AI behaviours ─────────────────────────────────────────────────

    def _ai_grunt(self, dt: float) -> None:
        if self.state == EnemyState.RETREAT:
            self._do_retreat(dt)
            return
        if self.state == EnemyState.IDLE:
            self._do_patrol(dt)
        elif self.state == EnemyState.CHASE:
            self._follow_path_to(self.target.pos, dt)
        elif self.state == EnemyState.SEARCH:
            self._do_search(dt)
        elif self.state == EnemyState.ALERT:
            self.velocity.update(0, 0)
            self._do_alert_rotate(dt)

    def _ai_shooter(self, dt: float) -> None:
        if self.state == EnemyState.RETREAT:
            self._do_retreat(dt)
            return
        if self.state in (EnemyState.COVER, EnemyState.PEEK):
            self._do_cover(dt)
            return
        if self.state == EnemyState.SUPPRESS:
            self._do_suppress(dt)
            return
        if self.state == EnemyState.FLANK:
            self._do_flank(dt)
            return
        if self.state == EnemyState.IDLE:
            self._do_patrol(dt)
            return
        elif self.state == EnemyState.SEARCH:
            self._do_search(dt)
            return
        elif self.state == EnemyState.ALERT:
            self.velocity.update(0, 0)
            self._do_alert_rotate(dt)
            return

        delta = self.target.pos - self.pos
        dist  = delta.length()

        # позиция для подхода — на preferred_dist от игрока,
        # с угловым смещением чтобы враги не кучковались
        approach_target = self._calc_approach_pos()

        if dist > self._preferred_dist + 40:
            self._follow_path_to(approach_target, dt)
        elif dist < self._preferred_dist - 40:
            if dist > 1:
                self.velocity = -delta.normalize() * self.speed
        else:
            if dist > 1:
                # стрейф — меняем направление каждые 1.5-2.5 сек
                self._strafe_timer -= dt
                if self._strafe_timer <= 0:
                    import random
                    self._strafe_dir   = random.choice([-1.0, 1.0])
                    self._strafe_timer = random.uniform(1.5, 2.5)
                perp = pygame.math.Vector2(-delta.normalize().y, delta.normalize().x)
                self.velocity = perp * self._strafe_dir * self.speed * 0.55

        if self.enemy_weapon:
            # новый путь — через EnemyWeapon
            self.enemy_weapon.update(dt, self.pos)
            if dist < self._preferred_dist + 120:
                direction = delta.normalize() if dist > 0 else pygame.math.Vector2(1, 0)
                fired = self.enemy_weapon.try_fire(self.pos, direction)

        else:
            # legacy путь
            self._shoot_cooldown = max(0.0, self._shoot_cooldown - dt)
            if self._shoot_cooldown <= 0 and dist < self._preferred_dist + 120:
                self._fire()
                self._shoot_cooldown = self._shoot_rate

    def _calc_approach_pos(self) -> pygame.math.Vector2:
        """
        Позиция для подхода к цели — на preferred_dist с угловым смещением.
        Враги в одной группе расходятся по дуге вокруг игрока.
        """
        import math as _math
        target_pos = self.target.pos
        delta = target_pos - self.pos
        if delta.length() < 1:
            return target_pos

        # базовый угол к цели
        base_angle = _math.atan2(delta.y, delta.x)

        # смещение по углу — зависит от позиции в группе
        angle_offset = 0.0
        if self.patrol_group:
            alive = [m for m in self.patrol_group.members if m.alive]
            if len(alive) > 1:
                try:
                    idx = alive.index(self)
                    # раскладываем по дуге ±60° от центра
                    spread = _math.radians(60)
                    angle_offset = -spread + (2 * spread / (len(alive) - 1)) * idx
                except ValueError:
                    pass

        approach_angle = base_angle + _math.pi + angle_offset  # противоположно — позади игрока
        # точка на preferred_dist от игрока в этом направлении
        return pygame.math.Vector2(
            target_pos.x + _math.cos(approach_angle) * self._preferred_dist,
            target_pos.y + _math.sin(approach_angle) * self._preferred_dist,
        )

    def _do_patrol(self, dt: float) -> None:
        if not self._patrol_points:
            self.velocity.update(0, 0)
            return
        target = self._patrol_points[self._patrol_index]
        if (self.pos - target).length() < self.tile_size // 2:
            self._patrol_index = (self._patrol_index + 1) % len(self._patrol_points)
            self._path = []
            self._path_timer = 0.0
        else:
            self._follow_path_to(target, dt)

    def _do_search(self, dt: float) -> None:
        if (self.pos - self._last_known_pos).length() > 12:
            self._follow_path_to(self._last_known_pos, dt)
        else:
            self.velocity.update(0, 0)
            self._search_rotate_timer -= dt
            self._facing_angle += self.ROTATE_SPEED * dt
            angle_rad   = math.radians(self._facing_angle)
            self.facing = pygame.math.Vector2(math.cos(angle_rad), math.sin(angle_rad))
            if self._search_rotate_timer <= 0:
                self.state               = EnemyState.ALERT
                self._alert_timer        = self.ALERT_TIMEOUT
                self._alert_react_timer  = self.ALERT_REACT_DELAY

    def _do_alert_rotate(self, dt: float) -> None:
        self._facing_angle += self.ROTATE_SPEED * 0.3 * dt
        angle_rad   = math.radians(self._facing_angle)
        self.facing = pygame.math.Vector2(math.cos(angle_rad), math.sin(angle_rad))

    def _start_retreat(self) -> None:
        """Запустить отход от игрока."""
        self.state = EnemyState.RETREAT
        self._path = []
        if self.target:
            delta = self.pos - self.target.pos
            if delta.length() > 1:
                self._retreat_point = self.pos + delta.normalize() * 600

    def _do_retreat(self, dt: float) -> None:
        """Бежать к retreat_point, при достижении — стать IDLE."""
        if self._retreat_point is None:
            # точка не задана — просто бежим от игрока
            delta = self.pos - self.target.pos
            if delta.length() > 1:
                self.velocity = delta.normalize() * self.speed * 1.3
            return
        dist = (self.pos - self._retreat_point).length()
        if dist < self.tile_size:
            self.velocity.update(0, 0)
            self.state          = EnemyState.IDLE
            self._retreat_point = None
        else:
            self._follow_path_to(self._retreat_point, dt)

    def _do_cover(self, dt: float) -> None:
        """Движение к укрытию (COVER) и выглядывание для стрельбы (PEEK)."""
        from core.managers.cover_system import cover_system

        if self.state == EnemyState.COVER:
            if self._cover_point is None:
                # ищем укрытие
                pt = cover_system.find_cover(self.pos, self.target.pos, self.walls)
                if pt is None:
                    # нет укрытий — обычная атака
                    self.state = EnemyState.CHASE
                    return
                self._cover_point = pt

            dist_to_cover = (self.pos - self._cover_point).length()
            if dist_to_cover < 24:
                # добрались — переходим в PEEK
                self.velocity.update(0, 0)
                self.state      = EnemyState.PEEK
                self._peek_timer = 0.0
            else:
                self._follow_path_to(self._cover_point, dt)

            # обновляем оружие пока идём
            if self.enemy_weapon:
                self.enemy_weapon.update(dt, self.pos)

        elif self.state == EnemyState.PEEK:
            self._peek_timer += dt
            self.velocity.update(0, 0)

            # стреляем в peek-фазе
            if self.enemy_weapon:
                self.enemy_weapon.update(dt, self.pos)
                delta = self.target.pos - self.pos
                dist  = delta.length()
                if dist > 0:
                    direction = delta.normalize()
                    self.enemy_weapon.try_fire(self.pos, direction)

            # 1.5 сек выглядываем, потом снова в укрытие
            if self._peek_timer >= 1.5:
                self.state        = EnemyState.COVER
                self._cover_point = None   # ищем снова — вдруг игрок сдвинулся
                self._peek_timer  = 0.0

    def _do_flank(self, dt: float) -> None:
        """Обходной манёвр: идём к фланговой точке, потом атакуем."""
        if self._flank_point is None:
            self.state = EnemyState.CHASE
            return

        dist = (self.pos - self._flank_point).length()

        if self._flank_phase == 0:
            # фаза 0 — движемся к фланговой точке
            if dist < 48:
                # добрались — атаковать
                self._flank_phase = 1
                self._flank_point = None
                self.state        = EnemyState.CHASE
                self._path        = []
            else:
                self._follow_path_to(self._flank_point, dt)
                # по дороге можем стрелять если видим игрока
                if self.enemy_weapon:
                    self.enemy_weapon.update(dt, self.pos)
                    if self.can_see_target():
                        delta = self.target.pos - self.pos
                        if delta.length() > 0:
                            self.enemy_weapon.try_fire(self.pos, delta.normalize())

    def _do_suppress(self, dt: float) -> None:
        """Подавляющий огонь — стоим за укрытием, стреляем в last_known_pos с разбросом."""
        self.velocity.update(0, 0)
        self._suppress_timer -= dt

        if self.enemy_weapon:
            self.enemy_weapon.update(dt, self.pos)
            delta = self._last_known_pos - self.pos
            if delta.length() > 1:
                direction = delta.normalize()
                self.enemy_weapon.try_fire_suppress(self.pos, direction, extra_spread=28.0)

        if self._suppress_timer <= 0:
            # закончили подавлять — идём в укрытие или CHASE
            if self.use_cover and self._cover_cooldown <= 0:
                self.state        = EnemyState.COVER
                self._cover_point = None
            else:
                self.state = EnemyState.CHASE

    # ── Combat ────────────────────────────────────────────────────────

    def _fire(self) -> None:
        """Legacy вызов — используется когда нет enemy_weapon."""
        if self._bullet_group is None:
            return
        delta = self.target.pos - self.pos
        if delta.length() == 0:
            return
        self._spawn_bullet(delta.normalize())

    def _fire_bullet(self, pos, direction) -> None:
        """Callback для EnemyWeapon.on_fire."""
        self._spawn_bullet(direction, pos=pos,
                           speed=self.enemy_weapon.stats.bullet_speed,
                           damage=self.enemy_weapon.stats.damage,
                           armor_pen=self.enemy_weapon.stats.armor_pen,
                           color=self.enemy_weapon.stats.bullet_color)

    def _spawn_bullet(self, direction, pos=None, speed=None,
                      damage=None, armor_pen=None, color=None) -> None:
        from combat.bullet import Bullet
        groups = [self._bullet_group]
        if self._all_sprites:
            groups.append(self._all_sprites)
        p      = pos    or self.pos
        sp     = speed  or self._bullet_speed
        dmg    = damage or self._bullet_damage
        ap     = armor_pen if armor_pen is not None else self._bullet_armor_pen
        col    = color  or self._bullet_color
        Bullet(
            pos=(p.x, p.y),
            direction=direction,
            speed=sp * 1.9,
            lifetime=1.6,
            damage=dmg,
            size=6,
            color=col,
            stopping_effect=0.0,
            armor_pen=ap,
            groups=groups,
        )

    # ── Visual ────────────────────────────────────────────────────────

    def _update_weapon_visual(self) -> None:
        if not self._weapon_w:
            self.weapon_image = None
            return
        base = pygame.Surface((self._weapon_w, self._weapon_h), pygame.SRCALPHA)
        base.fill(self._weapon_color)
        angle       = -math.degrees(math.atan2(self.facing.y, self.facing.x))
        facing_left = self.facing.x < 0
        base = pygame.transform.flip(base, False, facing_left)
        self.weapon_image = pygame.transform.rotate(base, angle)
        self.weapon_rect  = self.weapon_image.get_rect()
        offset = self.facing * 18
        self.weapon_rect.center = (
            round(self.pos.x + offset.x),
            round(self.pos.y + offset.y),
        )

    # ── Debug ─────────────────────────────────────────────────────────

    def draw_debug(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        super().draw_debug(surface, camera_offset)
        self._draw_vision_cone(surface, camera_offset)
        if self._path and self.pathfinder:
            self.pathfinder.draw_debug(surface, camera_offset, self._path)
        if self.state in (EnemyState.SEARCH, EnemyState.ALERT):
            lkp = self._last_known_pos
            sx  = round(lkp.x - camera_offset.x)
            sy  = round(lkp.y - camera_offset.y)
            pygame.draw.circle(surface, (255, 200, 50), (sx, sy), 6, 2)

    def _draw_vision_cone(self, surface: pygame.Surface, camera_offset: pygame.math.Vector2) -> None:
        cx = round(self.pos.x - camera_offset.x)
        cy = round(self.pos.y - camera_offset.y)
        facing_angle = math.degrees(math.atan2(self.facing.y, self.facing.x))
        half  = self.vision_angle / 2
        r     = self.vision_range
        steps = 16
        color = DEBUG_COLORS.get(self.state, (80, 200, 80, 40))

        points = [(cx, cy)]
        for i in range(steps + 1):
            a   = math.radians(facing_angle - half + (self.vision_angle / steps) * i)
            end = pygame.math.Vector2(
                self.pos.x + math.cos(a) * r,
                self.pos.y + math.sin(a) * r,
            )
            if self.walls and self._ray_hits_wall(self.pos, end):
                for wall in self.walls:
                    hit = ray_rect_hit_point(self.pos, end, wall.rect)
                    if hit:
                        end = hit
                        break
            points.append((round(end.x - camera_offset.x), round(end.y - camera_offset.y)))

        if len(points) >= 3:
            pygame.draw.lines(surface, (*color[:3], 120), False, points[1:], 1)
            pygame.draw.line(surface, (*color[:3], 120), points[0], points[1],  1)
            pygame.draw.line(surface, (*color[:3], 120), points[0], points[-1], 1)

        blocked   = self._ray_hits_wall(self.pos, self.target.pos)
        ray_color = (255, 80, 80) if blocked else (80, 255, 80)
        pygame.draw.line(surface, ray_color,
                         (cx, cy),
                         (round(self.target.pos.x - camera_offset.x),
                          round(self.target.pos.y - camera_offset.y)), 1)

    # ── Update ────────────────────────────────────────────────────────

    def update(self, dt: float, walls: pygame.sprite.Group = None) -> None:
        if walls is not None:
            self.walls = walls
        self._contact_cooldown = max(0.0, self._contact_cooldown - dt)
        self._cover_cooldown   = max(0.0, self._cover_cooldown   - dt)
        if self._stun_timer > 0:
            self._stun_timer    -= dt
            self._knockback_vel *= max(0.0, 1.0 - self.KNOCKBACK_FRICTION * dt)
            self.velocity        = self._knockback_vel.copy()
        else:
            self._knockback_vel.update(0, 0)
            self._update_state(dt)
            self._update_facing()
            self._ai_update(dt)
            self._apply_separation()
        super().update(dt, walls)
        self._update_weapon_visual()
