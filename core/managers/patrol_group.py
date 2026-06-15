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
        Все остальные немедленно получают CHASE к known_pos.
        source — враг-инициатор (чтобы не уведомлять его повторно).
        """
        from actors.enemy import EnemyState
        self._alarmed         = True
        self._cooldown_timer  = self.COOLDOWN_TIME

        for member in self.members:
            if not member.alive:
                continue
            if member is source:
                continue
            if member.state == EnemyState.CHASE:
                # уже в бою — просто обновляем позицию
                member._last_known_pos = pygame.math.Vector2(known_pos)
                continue
            # переводим в CHASE
            member._last_known_pos   = pygame.math.Vector2(known_pos)
            member._alert_react_timer = 0.0   # без задержки реакции
            member.state              = EnemyState.CHASE
            member._path              = []

    CHECK_DELAY = 10.0   # секунд до отправки проверяющего

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

    def draw_debug(self, surface: pygame.Surface,
                   camera_offset: pygame.math.Vector2) -> None:
        """Рисует линии между членами группы и статус."""
        if not self.members:
            return
        alive = [m for m in self.members if m.alive]
        color = (255, 80, 80) if self._alarmed else (80, 200, 80)
        # линии между соседями
        for i in range(len(alive) - 1):
            a = alive[i].pos - camera_offset
            b = alive[i + 1].pos - camera_offset
            pygame.draw.line(surface, (*color, 120),
                             (round(a.x), round(a.y)),
                             (round(b.x), round(b.y)), 1)
        # метка группы над первым живым
        if alive:
            font = pygame.font.SysFont("monospace", 10)
            label = font.render(f"[{self.name}]", True, color)
            p = alive[0].pos - camera_offset
            surface.blit(label, (round(p.x) - label.get_width() // 2,
                                 round(p.y) - 40))
