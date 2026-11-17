import pygame
import sys
import time
import math

# ==========================================
# ECHOES OF THE LOST CIVILIZATION
# Person 1 - Game Environment (Front-facing 3D)
# ==========================================

# 1. SETTINGS
ROWS = 12
COLS = 16

TILE_SIZE = 42
WALL_H = 12          # how tall the walls look

MAP_X = 20
MAP_Y = 85
MAP_W = COLS * TILE_SIZE
MAP_H = ROWS * TILE_SIZE

PANEL_X = MAP_X + MAP_W + 20
PANEL_W = 200

WIDTH = PANEL_X + PANEL_W + 20
HEIGHT = MAP_Y + MAP_H + 14 + 70 + 16

FPS = 60

PLAYER_SCALE = 1.3   # change this to make the player bigger or smaller

# Colors
BG = (14, 12, 12)
PANEL_BG = (28, 22, 18)
PANEL_BORDER = (120, 90, 45)
GOLD = (235, 190, 70)
WHITE = (240, 235, 225)
GRAY = (150, 140, 125)
GREEN = (80, 220, 130)

# Dark green floor
FLOOR_A = (24, 62, 38)
FLOOR_B = (19, 52, 31)
FLOOR_LINE = (34, 84, 52)

# Dark brown walls
WALL_TOP = (104, 68, 42)
WALL_TOP_LIGHT = (128, 88, 58)
WALL_FRONT = (62, 38, 22)
WALL_LINE = (28, 16, 9)

# 2. GAME MAP
# 0 = floor | 1 = wall | X = locked door (blocks) | S = start | G = exit
# K = key (decoration) | T = treasure (decoration)
MAP = [
    "1111111111111111",
    "1S0000000K000001",
    "1011101110111101",
    "1000100000100001",
    "1110101110101101",
    "1000001000000001",
    "1011101011110101",
    "1000101000010001",
    "10100000110111T1",
    "100011000X000001",
    "10000000000000G1",
    "1111111111111111"
]

# Grid values (what teammates read): 0 = walkable | 1 = wall | 2 = locked door


# 3. DRAWING HELPERS
def P(x, y):
    return (int(x), int(y))


def draw_text(screen, font, text, color, x, y, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(img, rect)


def shade_color(c, s):
    return (max(0, min(255, c[0] + s)),
            max(0, min(255, c[1] + s)),
            max(0, min(255, c[2] + s)))


def draw_wall(screen, x, y, size, h, shade=0):
    """3D block: a top face lifted up + a front face facing you."""
    top = pygame.Rect(x, y - h, size, size)
    front = pygame.Rect(x, y + size - h, size, h)

    pygame.draw.rect(screen, shade_color(WALL_FRONT, shade), front)
    pygame.draw.rect(screen, shade_color(WALL_TOP, shade), top)

    pygame.draw.line(screen, shade_color(WALL_TOP_LIGHT, shade),
                     (top.x + 1, top.y + 1), (top.right - 2, top.y + 1), 2)
    pygame.draw.line(screen, WALL_LINE,
                     (front.centerx, front.y), (front.centerx, front.bottom), 1)

    pygame.draw.rect(screen, WALL_LINE, top, 1)
    pygame.draw.rect(screen, WALL_LINE, front, 1)


def draw_key(screen, cx, cy, s):
    w = max(2, int(3 * s))
    pygame.draw.circle(screen, GOLD, P(cx - 8 * s, cy - 8 * s), int(7 * s), w)
    pygame.draw.line(screen, GOLD, P(cx - 3 * s, cy - 3 * s), P(cx + 11 * s, cy + 11 * s), w)
    pygame.draw.line(screen, GOLD, P(cx + 6 * s, cy + 6 * s), P(cx + 11 * s, cy + 1 * s), w)
    pygame.draw.line(screen, GOLD, P(cx + 10 * s, cy + 10 * s), P(cx + 14 * s, cy + 6 * s), w)


def draw_door(screen, cx, cy, s):
    rect = pygame.Rect(0, 0, int(30 * s), int(40 * s))
    rect.center = P(cx, cy)
    pygame.draw.rect(screen, (150, 45, 40), rect,
                     border_top_left_radius=int(14 * s), border_top_right_radius=int(14 * s))
    pygame.draw.rect(screen, GOLD, rect, max(1, int(2 * s)),
                     border_top_left_radius=int(14 * s), border_top_right_radius=int(14 * s))
    pygame.draw.circle(screen, GOLD, P(cx + 6 * s, cy + 2 * s), max(2, int(3 * s)))


def draw_chest(screen, cx, cy, s):
    body = pygame.Rect(0, 0, int(34 * s), int(24 * s))
    body.center = P(cx, cy + 4 * s)
    pygame.draw.rect(screen, (150, 90, 40), body, border_radius=int(3 * s))
    lid = pygame.Rect(body.x, body.y - int(8 * s), body.w, int(12 * s))
    pygame.draw.rect(screen, (175, 110, 50), lid,
                     border_top_left_radius=int(10 * s), border_top_right_radius=int(10 * s))
    pygame.draw.rect(screen, GOLD, body, max(1, int(2 * s)), border_radius=int(3 * s))
    pygame.draw.rect(screen, GOLD, (body.centerx - int(3 * s), body.y, int(6 * s), int(10 * s)))


def draw_exit(screen, cx, cy, s):
    rect = pygame.Rect(0, 0, int(32 * s), int(42 * s))
    rect.center = P(cx, cy)
    pygame.draw.rect(screen, (20, 110, 70), rect,
                     border_top_left_radius=int(16 * s), border_top_right_radius=int(16 * s))
    inner = rect.inflate(-int(10 * s), -int(10 * s))
    pygame.draw.rect(screen, GREEN, inner,
                     border_top_left_radius=int(12 * s), border_top_right_radius=int(12 * s))
    pygame.draw.rect(screen, (150, 240, 190), rect, max(1, int(2 * s)),
                     border_top_left_radius=int(16 * s), border_top_right_radius=int(16 * s))


def draw_player(screen, cx, cy, s):
    pygame.draw.rect(screen, (70, 50, 30), (cx - 7 * s, cy + 6 * s, 5 * s, 9 * s))
    pygame.draw.rect(screen, (70, 50, 30), (cx + 2 * s, cy + 6 * s, 5 * s, 9 * s))
    pygame.draw.rect(screen, (190, 130, 60), (cx - 9 * s, cy - 6 * s, 18 * s, 14 * s), border_radius=int(3 * s))
    pygame.draw.circle(screen, (235, 190, 150), P(cx, cy - 11 * s), int(7 * s))
    pygame.draw.ellipse(screen, (140, 90, 45), (cx - 12 * s, cy - 18 * s, 24 * s, 7 * s))
    pygame.draw.rect(screen, (140, 90, 45), (cx - 6 * s, cy - 24 * s, 12 * s, 8 * s), border_radius=int(3 * s))


def draw_shadow(screen, cx, cy, w=26, h=10):
    shadow = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 120), (0, 0, w, h))
    screen.blit(shadow, (cx - w // 2, cy - h // 2))


def draw_wall_icon(screen, x, y, size):
    pygame.draw.rect(screen, WALL_FRONT, (x, y, size, size))
    pygame.draw.rect(screen, WALL_TOP, (x, y, size, size * 2 // 3))
    pygame.draw.rect(screen, WALL_LINE, (x, y, size, size), 2)


# 4. ENVIRONMENT CLASS
class Environment:

    def __init__(self):
        self.grid = []
        for row in MAP:
            new_row = []
            for cell in row:
                if cell == "1":
                    new_row.append(1)
                elif cell == "X":
                    new_row.append(2)
                else:
                    new_row.append(0)
            self.grid.append(new_row)

        self.start = self.find_position("S")
        self.goal = self.find_position("G")
        self.player_pos = list(self.start)

        self.start_time = time.time()
        self.finish_time = None

        # Stats that Person 2 / Person 4 can fill later
        self.stats = {"nodes": "-", "path_len": "-", "path_cost": "-", "time": "-"}

        # Torch glow (made once)
        self.glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        for rad in range(40, 4, -4):
            pygame.draw.circle(self.glow, (255, 140, 40, 8), (40, 40), rad)

        # Player glow
        self.player_glow = pygame.Surface((110, 110), pygame.SRCALPHA)
        for rad in range(55, 5, -5):
            pygame.draw.circle(self.player_glow, (255, 210, 110, 14), (55, 55), rad)

    # ---------- Helpers ----------

    def find_position(self, symbol):
        for r in range(ROWS):
            for c in range(COLS):
                if MAP[r][c] == symbol:
                    return (r, c)
        return None

    def is_walkable(self, row, col):
        if row < 0 or row >= ROWS:
            return False
        if col < 0 or col >= COLS:
            return False
        return self.grid[row][col] == 0

    # ---------- Player ----------

    def move_player(self, dr, dc):
        if self.finish_time is not None:
            return False

        new_row = self.player_pos[0] + dr
        new_col = self.player_pos[1] + dc

        if self.is_walkable(new_row, new_col):
            self.player_pos = [new_row, new_col]
            if self.reached_goal():
                self.finish_time = time.time()
            return True
        return False

    def reset_player(self):
        self.player_pos = list(self.start)
        self.start_time = time.time()
        self.finish_time = None

    def set_player_pos(self, row, col):
        self.player_pos = [row, col]

    def reached_goal(self):
        return tuple(self.player_pos) == self.goal

    def get_elapsed(self):
        end = self.finish_time if self.finish_time is not None else time.time()
        return end - self.start_time

    # ---------- Functions for teammates ----------

    def get_grid(self):
        return self.grid

    def get_start(self):
        return self.start

    def get_goal(self):
        return self.goal

    def set_stats(self, nodes, path_len, path_cost, seconds):
        self.stats = {"nodes": nodes, "path_len": path_len,
                      "path_cost": path_cost, "time": seconds}

    # ---------- Drawing the map ----------

    def draw(self, screen):
        T = TILE_SIZE
        now = time.time()

        # Pass 1: floors (flat, always at the back)
        for r in range(ROWS):
            for c in range(COLS):
                if self.grid[r][c] != 1:
                    x = MAP_X + c * T
                    y = MAP_Y + r * T
                    color = FLOOR_A if (r + c) % 2 == 0 else FLOOR_B
                    pygame.draw.rect(screen, color, (x, y, T, T))
                    pygame.draw.rect(screen, FLOOR_LINE, (x, y, T, T), 1)

        # Start marker
        sr, sc = self.start
        pygame.draw.rect(screen, (200, 170, 80),
                         (MAP_X + sc * T + 5, MAP_Y + sr * T + 5, T - 10, T - 10), 2, border_radius=6)

        # Pass 2: row by row, top to bottom (this gives the 3D depth)
        # In each row: walls -> items -> player.
        # So a wall in a LOWER row covers the player's feet, and the player
        # stands in front of walls in the rows ABOVE.
        pr, pc = self.player_pos

        for r in range(ROWS):

            # Walls of this row
            for c in range(COLS):
                if self.grid[r][c] == 1:
                    x = MAP_X + c * T
                    y = MAP_Y + r * T
                    shade = ((r * 7 + c * 13) % 3) * 5 - 5
                    draw_wall(screen, x, y, T, WALL_H, shade)

                    # Torch on wall faces that look at open floor
                    if r < ROWS - 1 and self.grid[r + 1][c] == 0 and (r * 3 + c) % 4 == 0:
                        tx = x + T // 2
                        ty = y + T - WALL_H // 2
                        flick = int(now * 8 + c) % 2
                        screen.blit(self.glow, (tx - 40, ty - 40))
                        pygame.draw.circle(screen, (255, 150, 40), (tx, ty), 4 + flick)
                        pygame.draw.circle(screen, (255, 225, 110), (tx, ty), 2)

            # Items of this row
            for c in range(COLS):
                cx = MAP_X + c * T + T / 2
                cy = MAP_Y + r * T + T / 2 - 4
                ch = MAP[r][c]

                if ch == "K":
                    bob = math.sin(now * 3) * 3
                    draw_shadow(screen, cx, cy + 14, 16, 7)
                    draw_key(screen, cx, cy + bob, 0.9)
                elif ch == "T":
                    draw_shadow(screen, cx, cy + 16, 30, 10)
                    draw_chest(screen, cx, cy, 0.9)
                elif ch == "X":
                    draw_shadow(screen, cx, cy + 18, 26, 9)
                    draw_door(screen, cx, cy, 0.9)
                elif ch == "G":
                    draw_shadow(screen, cx, cy + 18, 26, 9)
                    draw_exit(screen, cx, cy, 0.9)

            # Player (only drawn in his own row)
            if r == pr:
                px = MAP_X + pc * T + T / 2
                py = MAP_Y + pr * T + T / 2
                bob = math.sin(now * 5) * 1.2
                screen.blit(self.player_glow, (px - 55, py - 55))
                draw_shadow(screen, px, py + 10, 30, 11)
                draw_player(screen, px, py - 10 + bob, PLAYER_SCALE)

        # Win banner
        if self.reached_goal():
            font = pygame.font.Font(None, 56)
            banner = pygame.Rect(0, 0, 420, 90)
            banner.center = (MAP_X + MAP_W // 2, MAP_Y + MAP_H // 2)
            pygame.draw.rect(screen, PANEL_BG, banner, border_radius=12)
            pygame.draw.rect(screen, GOLD, banner, 3, border_radius=12)
            draw_text(screen, font, "YOU ESCAPED!", GOLD, banner.centerx, banner.centery, center=True)

    # ---------- Drawing the interface ----------

    def draw_ui(self, screen):
        title_font = pygame.font.Font(None, 34)
        font = pygame.font.Font(None, 24)
        small = pygame.font.Font(None, 20)
        big = pygame.font.Font(None, 40)

        # Top bar
        draw_text(screen, title_font, "MISSION MODE", WHITE, MAP_X, 28)
        draw_text(screen, font, "Find the key and reach the exit!", GRAY, MAP_X + 230, 33)

        draw_text(screen, small, "TIME", GRAY, WIDTH - 110, 14)
        secs = int(self.get_elapsed())
        draw_text(screen, big, "%02d:%02d" % (secs // 60, secs % 60), GOLD, WIDTH - 110, 30)

        # Legend panel
        legend = pygame.Rect(PANEL_X, MAP_Y, PANEL_W, 300)
        pygame.draw.rect(screen, PANEL_BG, legend, border_radius=8)
        pygame.draw.rect(screen, PANEL_BORDER, legend, 2, border_radius=8)
        draw_text(screen, font, "LEGEND", GOLD, legend.centerx, legend.y + 22, center=True)

        items = ["Player", "Key", "Locked Door", "Treasure", "Exit", "Wall"]
        for i, name in enumerate(items):
            iy = legend.y + 60 + i * 38
            ix = legend.x + 30
            if name == "Player":
                draw_player(screen, ix, iy, 0.6)
            elif name == "Key":
                draw_key(screen, ix, iy, 0.8)
            elif name == "Locked Door":
                draw_door(screen, ix, iy, 0.6)
            elif name == "Treasure":
                draw_chest(screen, ix, iy, 0.7)
            elif name == "Exit":
                draw_exit(screen, ix, iy, 0.6)
            else:
                draw_wall_icon(screen, ix - 12, iy - 12, 24)
            draw_text(screen, small, name, WHITE, legend.x + 60, iy - 7)

        # Controls panel
        ctrl = pygame.Rect(PANEL_X, MAP_Y + 315, PANEL_W, 140)
        pygame.draw.rect(screen, PANEL_BG, ctrl, border_radius=8)
        pygame.draw.rect(screen, PANEL_BORDER, ctrl, 2, border_radius=8)
        draw_text(screen, font, "CONTROLS", GOLD, ctrl.centerx, ctrl.y + 22, center=True)
        draw_text(screen, small, "Arrows / WASD: Move", WHITE, ctrl.x + 15, ctrl.y + 52)
        draw_text(screen, small, "R: Restart", WHITE, ctrl.x + 15, ctrl.y + 78)
        draw_text(screen, small, "ESC: Exit", WHITE, ctrl.x + 15, ctrl.y + 104)

        # Bottom stats bar
        bar = pygame.Rect(MAP_X, MAP_Y + MAP_H + 14, WIDTH - 2 * MAP_X, 70)
        pygame.draw.rect(screen, PANEL_BG, bar, border_radius=8)
        pygame.draw.rect(screen, PANEL_BORDER, bar, 2, border_radius=8)

        labels = [("NODES EXPLORED", self.stats["nodes"]),
                  ("PATH LENGTH", self.stats["path_len"]),
                  ("PATH COST", self.stats["path_cost"]),
                  ("TIME TAKEN", self.stats["time"])]
        col_w = bar.w // 4
        for i, (label, value) in enumerate(labels):
            cx = bar.x + col_w * i + col_w // 2
            draw_text(screen, small, label, GRAY, cx, bar.y + 18, center=True)
            draw_text(screen, big, str(value), GREEN, cx, bar.y + 46, center=True)


# 5. MAIN GAME FUNCTION
def main():
    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Echoes of the Lost Civilization")
    clock = pygame.time.Clock()

    game = Environment()
    running = True

    while running:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_r:
                    game.reset_player()

                elif event.key in (pygame.K_UP, pygame.K_w):
                    game.move_player(-1, 0)

                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    game.move_player(1, 0)

                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    game.move_player(0, -1)

                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    game.move_player(0, 1)

        screen.fill(BG)
        game.draw(screen)
        game.draw_ui(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


# 6. RUN GAME
if __name__ == "__main__":
    main()