import pygame
from core.settings import Settings


class PauseScene:
    """
    Пауза. Рисуется поверх замороженного кадра игры.
    Escape — возобновить.
    update() возвращает:
        "running" — остаёмся на паузе
        "resume"  — возобновить игру
        "menu"    — выйти в главное меню
        "quit"    — выйти из игры
    """

    OVERLAY_ALPHA = 160
    PANEL_COLOR   = (16, 18, 28, 230)
    PANEL_BORDER  = (60, 65, 100)
    TITLE_COLOR   = (210, 215, 230)
    BTN_COLOR     = (30, 33, 48)
    BTN_HOVER     = (45, 50, 72)
    BTN_BORDER    = (70, 75, 110)
    BTN_TEXT      = (190, 195, 215)
    BTN_W         = 220
    BTN_H         = 48
    BTN_RADIUS    = 8

    def __init__(self, settings: Settings, screen: pygame.Surface,
                 frozen_frame: pygame.Surface) -> None:
        self.s            = settings
        self.screen       = screen
        self.frozen_frame = frozen_frame   # снимок кадра в момент паузы

        self._font_title = pygame.font.SysFont("monospace", 32, bold=True)
        self._font_btn   = pygame.font.SysFont("monospace", 16)
        self._font_hint  = pygame.font.SysFont("monospace", 12)

        cx = settings.screen_width  // 2
        cy = settings.screen_height // 2

        self._buttons = [
            {"label": "1. Resume",      "action": "resume",
             "rect": pygame.Rect(cx - self.BTN_W // 2, cy - 10,  self.BTN_W, self.BTN_H)},
            {"label": "2. Main Menu",   "action": "menu",
             "rect": pygame.Rect(cx - self.BTN_W // 2, cy + 58,  self.BTN_W, self.BTN_H)},
            {"label": "3. Exit Game",   "action": "quit",
             "rect": pygame.Rect(cx - self.BTN_W // 2, cy + 126, self.BTN_W, self.BTN_H)},
        ]
        self._hovered: int = -1

    def update(self, dt: float) -> str:
        mouse_pos = pygame.mouse.get_pos()
        self._hovered = -1
        for i, btn in enumerate(self._buttons):
            if btn["rect"].collidepoint(mouse_pos):
                self._hovered = i

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "resume"
                for i, btn in enumerate(self._buttons):
                    if event.key == pygame.K_1 + i:
                        return btn["action"]
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for btn in self._buttons:
                    if btn["rect"].collidepoint(event.pos):
                        return btn["action"]

        self._draw()
        return "running"

    def _draw(self) -> None:
        # замороженный кадр
        self.screen.blit(self.frozen_frame, (0, 0))

        # затемнение
        overlay = pygame.Surface(
            (self.s.screen_width, self.s.screen_height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, self.OVERLAY_ALPHA))
        self.screen.blit(overlay, (0, 0))

        # панель
        cx = self.s.screen_width  // 2
        cy = self.s.screen_height // 2
        pw, ph = self.BTN_W + 60, self.BTN_H * 3 + 80 + 150
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill(self.PANEL_COLOR)
        px = cx - pw // 2
        py = cy - ph // 2
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, self.PANEL_BORDER,
                         (px, py, pw, ph), 1, border_radius=10)

        # заголовок
        title = self._font_title.render("PAUSED", True, self.TITLE_COLOR)
        self.screen.blit(title, title.get_rect(center=(cx, py + 38)))

        # кнопки
        for i, btn in enumerate(self._buttons):
            color = self.BTN_HOVER if i == self._hovered else self.BTN_COLOR
            pygame.draw.rect(self.screen, color,           btn["rect"], border_radius=self.BTN_RADIUS)
            pygame.draw.rect(self.screen, self.BTN_BORDER, btn["rect"], 1, border_radius=self.BTN_RADIUS)
            lbl = self._font_btn.render(btn["label"], True, self.BTN_TEXT)
            self.screen.blit(lbl, lbl.get_rect(center=btn["rect"].center))

        # display.flip() — handled by GLRenderer in app.py
