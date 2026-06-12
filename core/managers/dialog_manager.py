import json
import os
import pygame
from core.settings import Settings


class DialogManager:
    """
    Управляет диалогами. Загружает JSON, отслеживает текущий узел,
    рисует окно диалога внизу экрана.
    Выбор ответа — цифры 1-9.
    """

    PANEL_H      = 200
    PANEL_BG     = (14, 16, 24, 230)
    PANEL_BORDER = (60, 70, 100)
    NAME_COLOR   = (140, 180, 255)
    TEXT_COLOR   = (210, 215, 225)
    CHOICE_COLOR = (160, 200, 140)
    CHOICE_NUM   = (100, 140, 80)
    DIM_COLOR    = (0, 0, 0, 120)

    def __init__(self, settings: Settings) -> None:
        self.s          = settings
        self.active     = False
        self._data      = None
        self._node_id   = "start"
        self._npc_name  = ""

        self._font_name   = pygame.font.SysFont("monospace", 14, bold=True)
        self._font_text   = pygame.font.SysFont("monospace", 14)
        self._font_choice = pygame.font.SysFont("monospace", 13)

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

    def handle_key(self, key: int) -> None:
        if not self.active:
            return
        node = self._current_node()
        if not node:
            return

        choices = node.get("choices", [])

        if not choices:
            self.active = False
            return

        for i, choice in enumerate(choices):
            if key == pygame.K_1 + i:
                next_node = choice.get("next")
                if next_node and next_node in self._data["nodes"]:
                    self._node_id = next_node
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

        w, h  = self.s.screen_width, self.s.screen_height
        panel_y = h - self.PANEL_H

        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill(self.DIM_COLOR)
        surface.blit(dim, (0, 0))

        panel = pygame.Surface((w, self.PANEL_H), pygame.SRCALPHA)
        panel.fill(self.PANEL_BG)
        surface.blit(panel, (0, panel_y))
        pygame.draw.rect(surface, self.PANEL_BORDER, (0, panel_y, w, self.PANEL_H), 1)
        pygame.draw.line(surface, self.PANEL_BORDER, (0, panel_y), (w, panel_y), 1)

        pad = 20

        name_surf = self._font_name.render(self._npc_name, True, self.NAME_COLOR)
        surface.blit(name_surf, (pad, panel_y + 14))

        text        = node.get("text", "")
        text_lines  = self._wrap_text(text, w - pad * 2 - 100)
        text_y      = panel_y + 38
        for line in text_lines:
            surf = self._font_text.render(line, True, self.TEXT_COLOR)
            surface.blit(surf, (pad, text_y))
            text_y += surf.get_height() + 4

        choices = node.get("choices", [])
        if not choices:
            hint = self._font_choice.render("[ Press any key to close ]", True, (100, 100, 120))
            surface.blit(hint, (pad, panel_y + self.PANEL_H - 30))
        else:
            choice_y = panel_y + self.PANEL_H - len(choices) * 22 - 12
            for i, choice in enumerate(choices):
                num  = self._font_choice.render(f"{i + 1}.", True, self.CHOICE_NUM)
                text_s = self._font_choice.render(choice["text"], True, self.CHOICE_COLOR)
                surface.blit(num,    (pad, choice_y))
                surface.blit(text_s, (pad + 22, choice_y))
                choice_y += 22

    def _current_node(self) -> dict | None:
        if not self._data:
            return None
        return self._data["nodes"].get(self._node_id)

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        words  = text.split(" ")
        lines  = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            if self._font_text.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
