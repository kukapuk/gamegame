"""
hud.py — координатор HUD. Собирает HUDDraw, HUDInput, InfoPanels.
"""
import pygame
from typing import Optional
from core.settings import Settings
from actors.player import Player
from items.inventory import Slot, Inventory
from core.ui.grid_backpack_ui import GridBackpackUI
from core.hud.hud_draw import HUDDraw
from core.hud.hud_input import HUDInput
from core.hud.info_panels import InfoPanels
from core.hud.constants import DragState


class HUD(HUDDraw, HUDInput, InfoPanels):
    """
    Весь UI поверх игрового мира.
    Логика разделена на миксины: HUDDraw / HUDInput / InfoPanels.
    """

    POUCH_KEY_LABELS  = ["Z", "X", "C", "V"]
    SLOT_SIZE         = 48
    SMALL_SLOT        = 24
    SLOT_PAD          = 4
    SLOT_BG           = (35, 35, 45)
    SLOT_BORDER       = (70, 70, 90)
    SLOT_TYPED_BG     = (25, 30, 50)
    SLOT_TYPED_BORDER = (60, 80, 140)
    SLOT_HOVER        = (55, 55, 70)
    TITLE_BG          = (28, 30, 45)
    TITLE_DRAG_BG     = (38, 42, 65)
    TEXT_COLOR        = (200, 200, 210)
    TOOLTIP_BG        = (20, 20, 30, 210)
    PANEL_BG          = (20, 22, 32, 230)
    PANEL_BORDER      = (60, 65, 90)
    MARGIN            = 20

    def __init__(self, settings: Settings, player: Player) -> None:
        self.s      = settings
        self.player = player
        self.font_sm = pygame.font.SysFont("monospace", 11)
        self.font_md = pygame.font.SysFont("monospace", 13)

        self.pouch_open:    bool = False
        self.backpack_open: bool = False

        self._drag:               Optional[DragState]    = None
        self._tooltip_text:       str                    = ""
        self._hovered_rect:       Optional[pygame.Rect]  = None
        self._hovered_world_item                         = None
        self._backpack_slot_rects:      list             = []
        self._pouch_panel_slot_rects:   list             = []
        self._info_panels:              list             = []
        self._hovered_item                               = None

        self._grid_ui = GridBackpackUI(settings, player, self.font_sm, self.font_md)

    # ── State ─────────────────────────────────────────────────────────

    def toggle_pouch(self) -> None:
        self.pouch_open = not self.pouch_open

    def open_backpack(self) -> None:
        self.backpack_open = True
        self._grid_ui.open()

    def close_backpack(self) -> None:
        self.backpack_open = False
        self._grid_ui.close()
        if self._drag:
            if self._drag.source_slot:
                self._drag.source_slot.item = self._drag.item
            self._drag = None
        self._hovered_world_item     = None
        self._hovered_rect           = None
        self._tooltip_text           = ""
        self._backpack_slot_rects    = []
        self._pouch_panel_slot_rects = []
        self._info_panels            = []

    def is_open(self) -> bool:
        return self.backpack_open or self.pouch_open

    # ── Helpers ───────────────────────────────────────────────────────

    def _bar_baseline(self) -> int:
        return self.s.screen_height - self.MARGIN

    def _pouch_interactive_rects(self):
        yield from self._quick_slot_rects()
        yield from self._pouch_panel_slot_rects

    def _all_interactive_rects(self):
        yield from self._pouch_interactive_rects()

    def _inv_for_slot(self, slot: Slot) -> Inventory:
        return self.player.pouch

    def _quick_slot_rects(self):
        ox  = self.MARGIN + self.s.player_hp_bar_width + 12
        oy  = self._bar_baseline() - self.SMALL_SLOT
        ss  = self.SMALL_SLOT
        pad = self.SLOT_PAD
        for i, slot in enumerate(self.player.pouch.slots):
            yield slot, pygame.Rect(ox + i * (ss + pad), oy, ss, ss)

    def _get_item_at(self, pos: tuple):
        for slot, rect in self._all_interactive_rects():
            if rect.collidepoint(pos) and not slot.empty:
                return slot, slot.item
        if self.backpack_open:
            item = self._grid_ui.item_at_pos(pos)
            if item:
                return None, item
        return None, None

    def _get_item_only(self, pos: tuple):
        _, item = self._get_item_at(pos)
        return item
