"""
dialog_manager.py — система диалогов с typewriter-анимацией.

Возможности:
  - Посимвольный вывод текста с переменной скоростью
  - Ключевые слова в тегах: [key]слово[/key] — подсвечиваются цветом
  - Перебивание: пробел во время печати → on_interrupt реплика NPC
  - Скорости: slow / normal / fast / urgent
  - Пробел / Enter — ускорить (показать весь текст) или перейти дальше

Формат JSON узла:
  {
    "text": "Стой! [key]Кто[/key] ты такой?",
    "typing_speed": "normal",       // slow/normal/fast/urgent
    "on_interrupt": "node_id",      // реакция на перебивание
    "choices": [...]
  }
"""

import json
import os
import re
import pygame
from core.settings import Settings


# ── Скорости печати (секунд на символ) ────────────────────────────────
SPEEDS = {
    "slow":   0.07,
    "normal": 0.035,
    "fast":   0.018,
    "urgent": 0.008,
}

# ── Цвета ──────────────────────────────────────────────────────────────
TAG_COLORS = {
    "key":     (255, 220, 80),    # ключевое слово — жёлтый
    "danger":  (220, 80,  80),    # опасность — красный
    "person":  (120, 200, 255),   # имя персонажа — голубой
    "place":   (140, 220, 140),   # место — зелёный
    "hint":    (180, 140, 255),   # подсказка — фиолетовый
}

TAG_RE = re.compile(r'\[(\w+)\](.*?)\[/\1\]', re.DOTALL)


def parse_tagged(text: str) -> list[tuple[str, tuple]]:
    """
    Парсит текст с тегами в список (символ, цвет).
    Возвращает list[(char, color)] где color — RGB tuple.
    """
    DEFAULT = (210, 215, 225)
    result  = []
    pos     = 0

    for m in TAG_RE.finditer(text):
        # обычный текст до тега
        if m.start() > pos:
            for ch in text[pos:m.start()]:
                result.append((ch, DEFAULT))
        # текст внутри тега
        color = TAG_COLORS.get(m.group(1), (255, 255, 100))
        for ch in m.group(2):
            result.append((ch, color))
        pos = m.end()

    # остаток
    for ch in text[pos:]:
        result.append((ch, DEFAULT))

    return result


class DialogManager:

    PANEL_H      = 200
    PANEL_BG     = (14, 16, 24, 230)
    PANEL_BORDER = (60, 70, 100)
    NAME_COLOR   = (140, 180, 255)
    TEXT_COLOR   = (210, 215, 225)
    CHOICE_COLOR = (160, 200, 140)
    CHOICE_NUM   = (100, 140, 80)
    DIM_COLOR    = (0, 0, 0, 120)
    INTERRUPT_COLOR = (180, 120, 80)   # цвет подсказки о перебивании

    def __init__(self, settings: Settings) -> None:
        self.s        = settings
        self.active   = False
        self._data    = None
        self._node_id = "start"
        self._npc_name = ""

        self._font_name   = pygame.font.SysFont("monospace", 14, bold=True)
        self._font_text   = pygame.font.SysFont("monospace", 14)
        self._font_choice = pygame.font.SysFont("monospace", 13)
        self._font_hint   = pygame.font.SysFont("monospace", 11)

        # typewriter state
        self._chars:        list[tuple[str, tuple]] = []   # (char, color)
        self._visible:      int   = 0      # сколько символов показано
        self._char_timer:   float = 0.0
        self._char_delay:   float = SPEEDS["normal"]
        self._typing_done:  bool  = False

        # перебивание
        self._can_interrupt: bool = False
        self._interrupt_node: str | None = None

        # кеш строк для рендера
        self._line_cache: list | None = None

    # ── Public ────────────────────────────────────────────────────────

    def start(self, dialog_file: str) -> None:
        path = os.path.join("dialogs", dialog_file)
        if not os.path.exists(path):
            print(f"[dialog] file not found: {path}")
            return
        with open(path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._node_id  = "start"
        self._npc_name = self._data.get("npc_name", "???")
        self.active    = True
        self._load_node()

    def update(self, dt: float) -> None:
        if not self.active or self._typing_done:
            return
        self._char_timer += dt
        added = False
        while self._char_timer >= self._char_delay and self._visible < len(self._chars):
            self._char_timer -= self._char_delay
            self._visible += 1
            added = True
        if added:
            self._line_cache = None   # инвалидируем кеш строк
        if self._visible >= len(self._chars):
            self._typing_done = True

    def handle_key(self, key: int) -> None:
        if not self.active:
            return
        node = self._current_node()
        if not node:
            return

        # Пробел — перебить (только пока печатает) или продолжить (когда закончил)
        if key in (pygame.K_SPACE, pygame.K_RETURN):
            if not self._typing_done:
                if self._can_interrupt and self._interrupt_node:
                    self._node_id = self._interrupt_node
                    self._load_node()
                # если нет on_interrupt — пробел ничего не делает во время печати
            else:
                choices = node.get("choices", [])
                if not choices:
                    self.active = False
            return

        # Выбор цифрой
        if self._typing_done:
            choices = node.get("choices", [])
            for i, choice in enumerate(choices):
                if key == pygame.K_1 + i:
                    next_node = choice.get("next")
                    if next_node and next_node in self._data["nodes"]:
                        self._node_id = next_node
                        self._load_node()
                    else:
                        self.active = False
                    return

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        node = self._current_node()
        if not node:
            self.active = False
            return

        w, h    = self.s.screen_width, self.s.screen_height
        panel_y = h - self.PANEL_H
        pad     = 20

        # затемнение
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill(self.DIM_COLOR)
        surface.blit(dim, (0, 0))

        # панель
        panel = pygame.Surface((w, self.PANEL_H), pygame.SRCALPHA)
        panel.fill(self.PANEL_BG)
        surface.blit(panel, (0, panel_y))
        pygame.draw.line(surface, self.PANEL_BORDER, (0, panel_y), (w, panel_y), 1)

        # имя NPC
        name_surf = self._font_name.render(self._npc_name, True, self.NAME_COLOR)
        surface.blit(name_surf, (pad, panel_y + 12))

        # текст (typewriter)
        text_y = panel_y + 36
        max_w  = w - pad * 2 - 20
        self._draw_typewriter(surface, pad, text_y, max_w)

        # подсказка о перебивании
        if not self._typing_done and self._can_interrupt:
            hint = self._font_hint.render(
                "[ПРОБЕЛ] — перебить", True, self.INTERRUPT_COLOR)
            surface.blit(hint, (w - hint.get_width() - pad, panel_y + 12))

        # выборы или подсказка
        choices = node.get("choices", [])
        if self._typing_done:
            if not choices:
                hint = self._font_hint.render(
                    "[ПРОБЕЛ] продолжить", True, (80, 85, 110))
                surface.blit(hint, (pad, panel_y + self.PANEL_H - 24))
            else:
                choice_y = panel_y + self.PANEL_H - len(choices) * 22 - 12
                for i, choice in enumerate(choices):
                    num  = self._font_choice.render(f"{i+1}.", True, self.CHOICE_NUM)
                    text = self._font_choice.render(choice["text"], True, self.CHOICE_COLOR)
                    surface.blit(num,  (pad, choice_y))
                    surface.blit(text, (pad + 22, choice_y))
                    choice_y += 22
        else:
            # пока печатает — ничего не показываем внизу
            pass

    # ── Private ───────────────────────────────────────────────────────

    def _load_node(self) -> None:
        node = self._current_node()
        if not node:
            self.active = False
            return

        raw_text = node.get("text", "")
        self._chars       = parse_tagged(raw_text)
        self._visible     = 0
        self._char_timer  = 0.0
        self._typing_done = False
        self._line_cache  = None

        speed = node.get("typing_speed", "normal")
        self._char_delay = SPEEDS.get(speed, SPEEDS["normal"])

        self._interrupt_node = node.get("on_interrupt")
        self._can_interrupt  = bool(self._interrupt_node)

    def _draw_typewriter(self, surface: pygame.Surface,
                         x: int, y: int, max_w: int) -> None:
        """Рисует видимые символы с цветами по словам."""
        if self._line_cache is None:
            self._line_cache = self._build_lines(max_w)

        line_h = self._font_text.get_height() + 4
        for line_surfs in self._line_cache:
            cx = x
            for word_surf in line_surfs:
                surface.blit(word_surf, (cx, y))
                cx += word_surf.get_width()
            y += line_h

    def _build_lines(self, max_w: int) -> list:
        """
        Строит список строк для рендера.
        Каждая строка — list[Surface].
        Алгоритм: сначала собираем runs (text, color),
        потом раскладываем по строкам с переносом по словам.
        """
        visible_chars = self._chars[:self._visible]
        if not visible_chars:
            return [[]]

        # 1. Собираем runs — последовательности одного цвета
        runs: list[tuple[str, tuple]] = []
        cur_text, cur_color = "", visible_chars[0][1]
        for ch, color in visible_chars:
            if color == cur_color:
                cur_text += ch
            else:
                if cur_text:
                    runs.append((cur_text, cur_color))
                cur_text  = ch
                cur_color = color
        if cur_text:
            runs.append((cur_text, cur_color))

        # 2. Разбиваем runs на токены (слова+пробелы), сохраняя цвет
        tokens: list[tuple[str, tuple]] = []
        for text, color in runs:
            # разбиваем по пробелам, сохраняя пробелы как отдельные токены
            i = 0
            while i < len(text):
                if text[i] == ' ':
                    tokens.append((' ', color))
                    i += 1
                elif text[i] == '\n':
                    tokens.append(('\n', color))
                    i += 1
                else:
                    # собираем слово до пробела/переноса
                    j = i
                    while j < len(text) and text[j] not in (' ', '\n'):
                        j += 1
                    tokens.append((text[i:j], color))
                    i = j

        # 3. Раскладываем токены по строкам
        lines: list[list[pygame.Surface]] = [[]]
        line_w = 0

        for text, color in tokens:
            if text == '\n':
                lines.append([])
                line_w = 0
                continue

            surf = self._font_text.render(text, True, color)
            sw   = surf.get_width()

            # перенос строки если не влезает (не переносим пробелы в начало строки)
            if line_w + sw > max_w and line_w > 0:
                if text == ' ':
                    continue   # пробел в начале новой строки — пропускаем
                lines.append([])
                line_w = 0

            lines[-1].append(surf)
            line_w += sw

        return lines

    def _current_node(self) -> dict | None:
        if not self._data:
            return None
        return self._data["nodes"].get(self._node_id)
