"""
patrol_group.py — групповая координация врагов.

PatrolGroup объединяет нескольких врагов в отряд.
Когда один член группы переходит в CHASE (увидел / услышал игрока),
он вызывает group.raise_alarm(pos) — все остальные немедленно
получают CHASE с той же последней известной позицией («рация»).

Использование в TMX:
  Добавить property patrol_group="group_name" к объектам врагов.
  SpawnManager собирает группы и вызывает PatrolGroup.add(enemy).

Жизненный цикл:
  IDLE     — патруль, рация молчит
  ALERTED  — один заметил, все получили тревогу
  COMBAT   — все в бою (CHASE)
  COOLDOWN — игрок пропал, группа возвращается к патрулю
"""
from __future__ import annotations
import pygame


class PatrolGroup:
    """
    Отряд врагов с общей тревогой.
    Хранит ссылки на членов, не владеет ими.
    """

    COOLDOWN_TIME = 20.0   # секунд до возврата в IDLE после потери игрока

    def __init__(self, name: str) -> None:
        self.name:    str         = name
        self.members: list        = []   # list[Enemy]
        self._cooldown_timer: float = 0.0
        self._alarmed: bool         = False
        self._pending_check             = None   # (checker_enemy, dead_pos) | None
        self._check_timer: float        = 0.0
        self._retreating: bool          = False
        self._initial_count: int        = 0   # задаётся после add()

    # ── Public API ────────────────────────────────────────────────────

    def add(self, enemy) -> None:
        """Добавить врага в группу, установить обратную ссылку."""
        self.members.append(enemy)
        enemy.patrol_group = self
        self._initial_count = len(self.members)

    def raise_alarm(self, known_pos: pygame.math.Vector2, source=None) -> None:
        """
        Тревога — один член группы заметил игрока.
        Назначаем flanker (один), остальные — CHASE.
        source — враг-инициатор (не уведомляем повторно).
        """
        from actors.enemy import EnemyState
        self._alarmed         = True
        self._cooldown_timer  = self.COOLDOWN_TIME

        # кандидаты — живые, не source, не уже в CHASE/FLANK
        others = [m for m in self.members
                  if m.alive and m is not source
                  and m.state not in (EnemyState.CHASE, EnemyState.FLANK)]

        # flanker — один, дальше всего от source (чтобы зашёл с другой стороны)
        flanker = None
        if source and len(others) >= 2:
            flanker = max(others, key=lambda m: (m.pos - source.pos).length())

        for member in self.members:
            if not member.alive:
                continue
            if member is source:
                continue
            if member.state == EnemyState.CHASE:
                member._last_known_pos = pygame.math.Vector2(known_pos)
                continue

            member._last_known_pos    = pygame.math.Vector2(known_pos)
            member._alert_react_timer = 0.0

            if member is flanker:
                flank_pos = self._calc_flank_pos(known_pos, source)
                member._flank_point = flank_pos
                member._flank_phase = 0
                member.state        = EnemyState.FLANK
                member._path        = []
            else:
                member.state = EnemyState.CHASE
                member._path = []

    CHECK_DELAY = 10.0   # секунд до отправки проверяющего

    @staticmethod
    def _calc_flank_pos(
        target_pos: pygame.math.Vector2,
        attacker,
        flank_dist: float = 220.0,
    ) -> pygame.math.Vector2:
        """
        Вычислить фланговую точку — перпендикуляр от линии attacker→target.
        Чередуем левый/правый фланг случайно.
        """
        import math, random
        if attacker is None:
            angle = random.uniform(0, math.pi * 2)
            return target_pos + pygame.math.Vector2(
                math.cos(angle), math.sin(angle)) * flank_dist

        delta = target_pos - attacker.pos
        if delta.length() < 1:
            delta = pygame.math.Vector2(1, 0)
        perp = pygame.math.Vector2(-delta.y, delta.x).normalize()
        side = random.choice([-1, 1])
        return target_pos + perp * side * flank_dist

    def notify_member_dead(self, dead_pos: pygame.math.Vector2) -> None:
        """
        Член группы погиб или не выходит на связь.
        Остальные получают ALERT сразу, ближайший идёт проверить через CHECK_DELAY секунд.
        """
        from actors.enemy import EnemyState

        alive = [m for m in self.members if m.alive]
        if not alive:
            return

        # тихая гибель — просто запускаем таймер, никого не будим
        checker = min(alive, key=lambda m: (m.pos - dead_pos).length())
        self._pending_check = (checker, pygame.math.Vector2(dead_pos))
        self._check_timer   = self.CHECK_DELAY

        # проверяем порог потерь для отступления
        self._check_retreat(alive)

    def notify_lost_target(self) -> None:
        """
        Вызывается когда член группы потерял цель (CHASE→SEARCH).
        Если никто в группе не видит игрока — начинаем cooldown.
        """
        from actors.enemy import EnemyState
        any_chasing = any(
            m.alive and m.state == EnemyState.CHASE
            for m in self.members
        )
        if not any_chasing:
            # никто не видит — держим SEARCH/ALERT, не сбрасываем сразу
            pass

    def update(self, dt: float) -> None:
        """Вызывать каждый кадр из game_scene или spawn_manager."""
        # таймер отложенной проверки места гибели
        if self._pending_check is not None:
            self._check_timer -= dt
            if self._check_timer <= 0:
                checker, dead_pos = self._pending_check
                self._pending_check = None
                if checker.alive:
                    from actors.enemy import EnemyState
                    checker._last_known_pos      = dead_pos
                    checker.state                = EnemyState.SEARCH
                    checker._search_rotate_timer = checker.SEARCH_ROTATE_TIME
                    checker._path                = []

        # при любой смерти — проверяем порог отступления
        if not self._retreating:
            alive = [m for m in self.members if m.alive]
            self._check_retreat(alive)

        if not self._alarmed:
            return
        from actors.enemy import EnemyState
        any_active = any(
            m.alive and m.state in (EnemyState.CHASE, EnemyState.SEARCH)
            for m in self.members
        )
        if any_active:
            self._cooldown_timer = self.COOLDOWN_TIME
        else:
            self._cooldown_timer -= dt
            if self._cooldown_timer <= 0:
                self._alarmed = False

    RETREAT_THRESHOLD = 0.5   # 50% потерь → отход

    def _check_retreat(self, alive: list) -> None:
        """Если бандиты потеряли >= RETREAT_THRESHOLD группы — все отходят."""
        if self._retreating:
            return
        if self._initial_count == 0:
            return
        lost = self._initial_count - len(alive)
        if lost / self._initial_count < self.RETREAT_THRESHOLD:
            return

        from actors.enemy import EnemyState
        from core.managers.faction_manager import Faction
        self._retreating = True

        for member in alive:
            if member.faction != Faction.BANDIT:
                continue   # военные и элита держатся
            if member.state == EnemyState.RETREAT:
                continue
            member._broken = True
            member._start_retreat()

    # ── Debug ─────────────────────────────────────────────────────────

    # цвет и метка для каждого состояния
    _STATE_STYLE = None  # инициализируется лениво

    @staticmethod
    def _get_state_style():
        from actors.enemy import EnemyState
        return {
            EnemyState.IDLE:     ((120, 120, 120), "idle"),
            EnemyState.ALERT:    ((180, 120, 220), "alert"),
            EnemyState.SEARCH:   ((220, 180,  60), "search"),
            EnemyState.CHASE:    ((220,  80,  80), "chase"),
            EnemyState.SUPPRESS: ((220,  80, 180), "supr"),
            EnemyState.COVER:    (( 60, 180, 220), "cover"),
            EnemyState.PEEK:     ((220, 140,  60), "peek"),
            EnemyState.FLANK:    (( 80, 220, 180), "flank"),
            EnemyState.RETREAT:  (( 80, 160, 220), "run"),
        }

    def draw_debug(self, surface: pygame.Surface,
                   camera_offset: pygame.math.Vector2) -> None:
        if not self.members:
            return

        from actors.enemy import EnemyState
        style = self._get_state_style()
        alive = [m for m in self.members if m.alive]

        font_small = pygame.font.SysFont("monospace", 10)
        font_name  = pygame.font.SysFont("monospace", 9)

        group_color = (255, 80, 80) if self._alarmed else (160, 160, 160)

        # линия группы между соседями
        for i in range(len(alive) - 1):
            a = alive[i].pos - camera_offset
            b = alive[i + 1].pos - camera_offset
            pygame.draw.line(surface, (*group_color, 80),
                             (round(a.x), round(a.y)),
                             (round(b.x), round(b.y)), 1)

        for m in alive:
            mp = m.pos - camera_offset
            mx, my = round(mp.x), round(mp.y)

            state_color, state_label = style.get(
                m.state, ((160, 160, 160), m.state[:4]))

            # кружок-роль над головой
            pygame.draw.circle(surface, state_color, (mx, my - 22), 6)
            pygame.draw.circle(surface, (0, 0, 0),   (mx, my - 22), 6, 1)

            # метка состояния
            lbl = font_small.render(state_label, True, state_color)
            surface.blit(lbl, (mx - lbl.get_width() // 2, my - 36))

            # имя группы под меткой состояния (мелко, серым)
            grp = font_name.render(f"[{self.name}]", True, group_color)
            surface.blit(grp, (mx - grp.get_width() // 2, my - 47))

            # линия к цели действия
            if m.state == EnemyState.FLANK and m._flank_point:
                fp = m._flank_point - camera_offset
                pygame.draw.line(surface, state_color,
                                 (mx, my), (round(fp.x), round(fp.y)), 1)
                pygame.draw.circle(surface, state_color,
                                   (round(fp.x), round(fp.y)), 4, 1)

            elif m.state == EnemyState.COVER and m._cover_point:
                cp = m._cover_point - camera_offset
                pygame.draw.line(surface, state_color,
                                 (mx, my), (round(cp.x), round(cp.y)), 1)
                pygame.draw.circle(surface, state_color,
                                   (round(cp.x), round(cp.y)), 4, 1)

            elif m.state == EnemyState.SUPPRESS:
                lkp = m._last_known_pos - camera_offset
                # пунктирная линия к точке подавления
                dx = round(lkp.x) - mx
                dy = round(lkp.y) - my
                length = max(1, int((dx**2 + dy**2) ** 0.5))
                for t in range(0, length, 10):
                    px = mx + dx * t // length
                    py = my + dy * t // length
                    pygame.draw.circle(surface, state_color, (px, py), 1)

            elif m.state == EnemyState.CHASE:
                tp = m.target.pos - camera_offset
                pygame.draw.line(surface, (*state_color, 60),
                                 (mx, my), (round(tp.x), round(tp.y)), 1)
