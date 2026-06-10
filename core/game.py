import pygame
from core.settings import Settings
from core.camera import Camera
from entities.player import Player


class Game:
    """
    Central game loop and renderer.

    Responsibilities:
      - create window & clock
      - own the sprite groups
      - run the main loop (event → update → draw)
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screen = pygame.display.set_mode(
            (settings.screen_width, settings.screen_height)
        )
        pygame.display.set_caption(settings.title)
        self.clock = pygame.time.Clock()
        self.running = True

        # Sprite groups
        self.all_sprites = pygame.sprite.Group()

        # Entities
        spawn = (settings.screen_width // 2, settings.screen_height // 2)
        self.player = Player(spawn, settings, groups=[self.all_sprites])

        # Camera
        self.camera = Camera(settings)

        # Debug flag (toggle with F1)
        self.debug = False

    # Main loop

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.settings.fps) / 1000.0  # seconds
            self._handle_events()
            self._update(dt)
            self._draw()

    # Loop phases

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_F1:
                    self.debug = not self.debug

    def _update(self, dt: float) -> None:
        self.all_sprites.update(dt)
        self.camera.follow(self.player)

    def _draw(self) -> None:
        self.screen.fill(self.settings.bg_color)
        self._draw_grid()
        self._draw_sprites()
        if self.debug:
            self._draw_debug_info()
        pygame.display.flip()

    def _draw_grid(self) -> None:
        """Faint grid so movement is clearly visible."""
        gs = self.settings.grid_size
        offset = self.camera.get_offset()
        w, h = self.settings.screen_width, self.settings.screen_height

        # Starting tile (world coords), snapped to grid
        start_x = int(offset.x // gs) * gs
        start_y = int(offset.y // gs) * gs

        x = start_x
        while x < offset.x + w + gs:
            sx = x - offset.x
            pygame.draw.line(self.screen, self.settings.grid_color,
                             (sx, 0), (sx, h))
            x += gs

        y = start_y
        while y < offset.y + h + gs:
            sy = y - offset.y
            pygame.draw.line(self.screen, self.settings.grid_color,
                             (0, sy), (w, sy))
            y += gs

    def _draw_sprites(self) -> None:
        for sprite in self.all_sprites:
            screen_rect = self.camera.apply(sprite.rect)
            self.screen.blit(sprite.image, screen_rect)

    def _draw_debug_info(self) -> None:
        font = pygame.font.SysFont("monospace", 16)
        lines = [
            f"FPS: {self.clock.get_fps():.0f}",
            f"pos: ({self.player.pos.x:.0f}, {self.player.pos.y:.0f})",
            f"vel: ({self.player.velocity.x:.0f}, {self.player.velocity.y:.0f})",
            f"facing: ({self.player.facing.x:.2f}, {self.player.facing.y:.2f})",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (180, 220, 180))
            self.screen.blit(surf, (10, 10 + i * 20))
        # draw collision rect
        self.player.draw_debug(self.screen, self.camera.get_offset())
