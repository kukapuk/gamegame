"""Константы и DragState для HUD."""
import pygame
from dataclasses import dataclass
from typing import Optional


@dataclass
class DragState:
    item:               object
    source_inv:         object
    source_slot:        object
    source_world_item:  object = None
    icon_size:          int    = 40


HUD_CONSTANTS = dict(
    POUCH_KEY_LABELS  = ["Z", "X", "C", "V"],
    SLOT_SIZE         = 48,
    SMALL_SLOT        = 24,
    SLOT_PAD          = 4,
    SLOT_BG           = (35, 35, 45),
    SLOT_BORDER       = (70, 70, 90),
    SLOT_TYPED_BG     = (25, 30, 50),
    SLOT_TYPED_BORDER = (60, 80, 140),
    SLOT_HOVER        = (55, 55, 70),
    TITLE_BG          = (28, 30, 45),
    TITLE_DRAG_BG     = (38, 42, 65),
    TEXT_COLOR        = (200, 200, 210),
    TOOLTIP_BG        = (20, 20, 30, 210),
    PANEL_BG          = (20, 22, 32, 230),
    PANEL_BORDER      = (60, 65, 90),
    MARGIN            = 20,
)
