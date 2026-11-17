"""
Echoes of the Lost Civilization - main.py  (Person 4)

Flow: Main Menu -> Algorithm Select -> Maze + AI Visualization -> Results
                                    +-> Algorithm Comparison Dashboard
                                    +-> Manual Mode (you walk the maze yourself) -> Manual Results

Integration with the team's files:
  environment.py (Person 1): Environment().get_grid() / get_start() / get_goal(), drawing helpers
  algorithms.py  (Person 2): find_path(grid, start, goal, "bfs" | "dfs" | "astar")
                             -> {"path", "found", "path_length", "explored_nodes", "execution_time_ms"}

algorithms.py returns only the NUMBER of explored nodes, not which cells. To animate the
search, this file re-runs a "trace" copy of each algorithm that records the visiting order.
The trace is checked against Person 2's numbers; if they ever differ, the animation falls
back to showing only the final path (the numbers always come from algorithms.py).

File layout:
  PART 1  Logic (validation, tracing, calling algorithms.py)  - no drawing
  PART 2  UI    (buttons, drawing, game states, main loop)
"""
import sys
import math
import time
import heapq
from collections import deque

import pygame

try:
    import environment
except ImportError:
    sys.exit("environment.py not found. Put main.py in the same folder as environment.py.")
try:
    import algorithms
except ImportError:
    algorithms = None

try:
    from mechanics import GameMechanics
except ImportError as exc:
    sys.exit(f"mechanics.py could not be imported: {exc}")

# =====================================================================
# PART 1 - LOGIC
# =====================================================================
ALGOS = ["BFS", "DFS", "A*"]
ALGO_KEYS = {"BFS": "bfs", "DFS": "dfs", "A*": "astar"}   # names find_path() understands


class MazeError(Exception):
    """Raised when the maze from environment.py is not usable."""


def validate_maze(grid, start, goal):
    """Checks the maze given by environment.py. 0 = floor, 1 = wall, 2 = locked door (blocked)."""
    if not grid or not grid[0]:
        raise MazeError("The maze is empty.")
    cols = len(grid[0])
    for r, row in enumerate(grid):
        if len(row) != cols:
            raise MazeError(f"The maze is not rectangular: row {r} has {len(row)} cells, expected {cols}.")
        for c, v in enumerate(row):
            if v not in (0, 1, 2):
                raise MazeError(f"Invalid cell {v!r} at row {r}, col {c}. Expected 0, 1 or 2.")
    for name, pos in (("Start", start), ("Goal", goal)):
        if pos is None:
            raise MazeError(f"The maze has no {name} cell ({name[0]}).")
        r, c = pos
        if not (0 <= r < len(grid) and 0 <= c < cols):
            raise MazeError(f"The {name} cell {pos} is outside the maze.")
        if grid[r][c] != 0:
            raise MazeError(f"The {name} cell {pos} is not on a walkable floor tile.")
    if tuple(start) == tuple(goal):
        raise MazeError("Start and Goal are the same cell.")


def load_environment():
    """Creates Person 1's Environment, validates it, returns (env, grid, start, goal)."""
    env = environment.Environment()
    grid, start, goal = env.get_grid(), env.get_start(), env.get_goal()
    validate_maze(grid, start, goal)
    return env, grid, tuple(start), tuple(goal)


# ---------- trace copies of Person 2's algorithms (same logic, but they record the order) ----------
def _valid(grid, pos):
    r, c = pos
    return 0 <= r < len(grid) and 0 <= c < len(grid[0]) and grid[r][c] == 0


def _neighbors(grid, pos):
    r, c = pos
    return [p for p in ((r - 1, c), (r, c + 1), (r + 1, c), (r, c - 1)) if _valid(grid, p)]


def _rebuild(parent, start, goal):
    if goal != start and goal not in parent:
        return []
    path = [goal]
    while path[-1] != start:
        path.append(parent[path[-1]])
    path.reverse()
    return path


def trace_bfs(grid, start, goal):
    order = []
    if not _valid(grid, start) or not _valid(grid, goal):
        return [], order
    queue, visited, parent = deque([start]), {start}, {}
    while queue:
        cur = queue.popleft()
        order.append(cur)
        if cur == goal:
            break
        for nxt in _neighbors(grid, cur):
            if nxt not in visited:
                visited.add(nxt)
                parent[nxt] = cur
                queue.append(nxt)
    return (_rebuild(parent, start, goal) if goal in visited else []), order


def trace_dfs(grid, start, goal):
    order = []
    if not _valid(grid, start) or not _valid(grid, goal):
        return [], order
    stack, visited, parent = [start], {start}, {}
    while stack:
        cur = stack.pop()
        order.append(cur)
        if cur == goal:
            break
        for nxt in reversed(_neighbors(grid, cur)):
            if nxt not in visited:
                visited.add(nxt)
                parent[nxt] = cur
                stack.append(nxt)
    return (_rebuild(parent, start, goal) if goal in visited else []), order


def trace_astar(grid, start, goal):
    order = []
    if not _valid(grid, start) or not _valid(grid, goal):
        return [], order
    h = lambda p: abs(p[0] - goal[0]) + abs(p[1] - goal[1])
    heap = [(h(start), 0, start)]
    parent, g_score, closed = {}, {start: 0}, set()
    while heap:
        _, cost, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        order.append(cur)
        if cur == goal:
            break
        for nxt in _neighbors(grid, cur):
            tentative = cost + 1
            if tentative < g_score.get(nxt, float("inf")):
                g_score[nxt] = tentative
                parent[nxt] = cur
                heapq.heappush(heap, (tentative + h(nxt), tentative, nxt))
    return (_rebuild(parent, start, goal) if goal in closed else []), order


TRACERS = {"bfs": trace_bfs, "dfs": trace_dfs, "astar": trace_astar}


def _path_ok(grid, start, goal, path):
    """True if `path` is a real 4-direction walk from start to goal over floor tiles
    (or if an empty path is correct because the goal is unreachable)."""
    try:
        if not path:
            return not trace_bfs(grid, start, goal)[0]
        if path[0] != start or path[-1] != goal:
            return False
        if not all(_valid(grid, p) for p in path):
            return False
        return all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(path, path[1:]))
    except Exception:
        return False


def _call_algorithms(key, grid, start, goal):
    """Calls Person 2's code on a COPY of the grid. Returns its result dict, or None."""
    if algorithms is None:
        return None
    copy = [row[:] for row in grid]
    fn = getattr(algorithms, "find_path", None)
    if callable(fn):
        return fn(copy, start, goal, key)
    fn = getattr(algorithms, key, None)
    return fn(copy, start, goal) if callable(fn) else None


def run_algorithm(label, grid, start, goal):
    """Runs one algorithm and returns a result dict used by the whole UI."""
    key = ALGO_KEYS[label]
    t0 = time.perf_counter()
    t_path, order = TRACERS[key]([row[:] for row in grid], start, goal)
    trace_ms = (time.perf_counter() - t0) * 1000

    source = "built-in solver (algorithms.py not found)" if algorithms is None else \
        "built-in solver (algorithms.py has no find_path)"
    path, nodes, time_ms, has_trace = t_path or None, len(order), trace_ms, True

    try:
        res = _call_algorithms(key, grid, start, goal)
        if isinstance(res, dict):
            their_path = [tuple(p) for p in res.get("path") or []]
            if _path_ok(grid, start, goal, their_path):
                path = their_path or None
                nodes = res.get("explored_nodes", len(order))
                time_ms = res.get("execution_time_ms", trace_ms)
                source = "algorithms.py"
                # animation is only trusted if our trace reproduces Person 2's result
                has_trace = (their_path == t_path and nodes == len(order))
                if not has_trace:
                    print(f"[note] {label}: the search animation could not be matched with "
                          f"algorithms.py, so only the final path will be animated.")
            else:
                print(f"[warning] {label}: algorithms.py returned an invalid path - using built-in solver.")
                source = "built-in solver (algorithms.py gave an invalid path)"
        elif res is not None:
            print(f"[warning] {label}: algorithms.py did not return a dict - using built-in solver.")
            source = "built-in solver (unexpected output from algorithms.py)"
    except Exception as e:
        print(f"[warning] {label}: algorithms.py failed ({e}) - using built-in solver.")
        source = "built-in solver (algorithms.py raised an error)"

    return {"label": label, "path": path, "ok": bool(path), "nodes": nodes,
            "time_ms": time_ms, "explored": order if has_trace else [],
            "has_trace": has_trace, "source": source}


# =====================================================================
# PART 2 - UI
# =====================================================================
E = environment
WIDTH, HEIGHT = E.WIDTH, E.HEIGHT
MAP_X, MAP_Y, MAP_W, MAP_H = E.MAP_X, E.MAP_Y, E.MAP_W, E.MAP_H
PANEL_X, PANEL_W, T = E.PANEL_X, E.PANEL_W, E.TILE_SIZE

BG = (30, 20, 10)
GOLD = (230, 190, 90)
SAND = (235, 215, 160)
WALL = (120, 85, 40)
START_C = (60, 140, 220)
EXPLORED_C = (240, 170, 70)
PATH_C = (60, 200, 90)
WHITE = (245, 245, 245)
GREY = (150, 140, 120)
RED = (230, 70, 70)
ALGO_COLORS = {"BFS": (80, 150, 230), "DFS": (210, 120, 60), "A*": (90, 190, 110)}

MENU, SELECT, PLAYING, RESULT, COMPARE, ERROR = "menu", "select", "playing", "result", "compare", "error"
MANUAL, MANUAL_RESULT = "manual", "manual_result"
LEARN, PRACTICE = "learn", "practice"

# (ms per explored cell, ms per final-path cell)
SPEEDS = {"Slow": (120, 220), "Normal": (45, 90), "Fast": (8, 30)}
END_PAUSE = 1500   # ms to wait after the animation before showing the results
MOVE_DELAY = 130   # manual mode: ms between steps while a key is held down
MANUAL_END_PAUSE = 1200   # manual mode: ms to show 'YOU ESCAPED!' before the results

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Echoes of the Lost Civilization")
clock = pygame.time.Clock()
font_title = pygame.font.SysFont("georgia", 48, bold=True)
font_big = pygame.font.SysFont("arial", 30, bold=True)
font = pygame.font.SysFont("arial", 22)
font_btn = pygame.font.SysFont("arial", 20, bold=True)
font_tiny = pygame.font.SysFont("arial", 15, bold=True)
font_small = pygame.font.SysFont("arial", 18)
font_banner = pygame.font.Font(None, 56)

# translucent tile overlays for the search visualization
OV_EXPLORED = pygame.Surface((T, T), pygame.SRCALPHA)
OV_EXPLORED.fill((*EXPLORED_C, 120))
OV_PATH = pygame.Surface((T, T), pygame.SRCALPHA)
OV_PATH.fill((*PATH_C, 170))


class Button:
    def __init__(self, text, center, size=(260, 55), fnt=None):
        self.text = text
        self.font = fnt or font_big
        self.rect = pygame.Rect(0, 0, *size)
        self.rect.center = center

    def draw(self, active=False):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        lit = hover or active
        pygame.draw.rect(screen, GOLD if lit else WALL, self.rect, border_radius=10)
        pygame.draw.rect(screen, SAND, self.rect, 3, border_radius=10)
        label = self.font.render(self.text, True, BG if lit else WHITE)
        screen.blit(label, label.get_rect(center=self.rect.center))

    def clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos))


def text_center(txt, f, color, y, x=WIDTH // 2):
    surf = f.render(str(txt), True, color)
    screen.blit(surf, surf.get_rect(center=(x, y)))


def text_left(txt, f, color, x, y):
    screen.blit(f.render(str(txt), True, color), (x, y))


def wrap_text(txt, f, max_w):
    lines, line = [], ""
    for word in txt.split():
        test = (line + " " + word).strip()
        if f.size(test)[0] <= max_w:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def panel(rect):
    pygame.draw.rect(screen, E.PANEL_BG, rect, border_radius=8)
    pygame.draw.rect(screen, E.PANEL_BORDER, rect, 2, border_radius=8)


# ---------- buttons ----------
CX = WIDTH // 2
btn_start = Button("Start", (CX, 320))
btn_menu_manual = Button("Manual Mode", (CX, 395))
btn_exit = Button("Exit", (CX, 470))

btn_algos = [Button(a, (CX, y)) for a, y in zip(ALGOS, (235, 305, 375))]
btn_manual = Button("Play Manually", (CX, 450), (300, 55))
btn_sel_compare = Button("Compare Results", (CX, 520), (300, 50))
btn_sel_back = Button("Back", (CX, 590), (160, 45))
btn_learn_demo = Button("Watch AI Demonstration", (CX, 465), (330, 52))
btn_learn_practice = Button("Practice This Algorithm", (CX, 530), (330, 52))
btn_learn_back = Button("Back", (CX, 600), (160, 42))

# Define the right-panel centre before creating any buttons that use it.
PCX = PANEL_X + PANEL_W // 2            # centre of the right-hand panel
btn_practice_restart = Button("Restart Practice", (PCX, MAP_Y + 80), (180, 40), font_btn)
btn_practice_back = Button("Lesson", (PCX, MAP_Y + 130), (180, 40), font_btn)
btn_pause = Button("Pause", (PCX, MAP_Y + 55), (170, 38), font_btn)
btn_restart = Button("Restart", (PCX, MAP_Y + 100), (170, 38), font_btn)
btn_speeds = {s: Button(s, (PANEL_X + x, MAP_Y + 185), (56, 32), font_tiny)
              for s, x in zip(SPEEDS, (40, 100, 160))}
btn_back_select = Button("Algorithms", (PCX, MAP_Y + 240), (170, 38), font_btn)

btn_man_restart = Button("Restart", (PCX, MAP_Y + 55), (170, 38), font_btn)
btn_man_hint = Button("Hint: Off", (PCX, MAP_Y + 100), (170, 38), font_btn)
btn_man_back = Button("Algorithms", (PCX, MAP_Y + 145), (170, 38), font_btn)
btn_man_again = Button("Play Again", (CX - 260, 610), (220, 52))
btn_man_algos = Button("Algorithms", (CX, 610), (220, 52))
btn_man_menu = Button("Main Menu", (CX + 260, 610), (220, 52))

btn_res_another = Button("Try Another", (CX - 260, 610), (220, 52))
btn_res_compare = Button("Compare", (CX, 610), (220, 52))
btn_res_menu = Button("Main Menu", (CX + 260, 610), (220, 52))

btn_cmp_another = Button("Try Another", (CX - 150, 630), (260, 48))
btn_cmp_menu = Button("Main Menu", (CX + 150, 630), (260, 48))

btn_err_back = Button("Back to Menu", (CX, 480), (300, 55))


def held_direction():
    """Manual mode: returns (d_row, d_col) of the movement key currently held, or None."""
    k = pygame.key.get_pressed()
    if k[pygame.K_UP] or k[pygame.K_w]:
        return (-1, 0)
    if k[pygame.K_DOWN] or k[pygame.K_s]:
        return (1, 0)
    if k[pygame.K_LEFT] or k[pygame.K_a]:
        return (0, -1)
    if k[pygame.K_RIGHT] or k[pygame.K_d]:
        return (0, 1)
    return None


# ---------- game state ----------
class Game:
    def __init__(self):
        self.state = MENU
        self.env = self.grid = self.start = self.goal = None
        self.results = {}          # label -> result dict (kept per maze, used by the dashboard)
        self.current = None        # result dict of the algorithm being shown
        self.selected = None
        self.recommended = None
        self.recommendation_reason = ""
        self.practice_pos = None
        self.practice_step = 0
        self.practice_message = "Use the arrow keys or WASD to choose the next cell."
        self.practice_done = False
        self.speed = "Normal"
        self.error_msg = ""
        # manual mode
        self.manual_pos = None
        self.manual_moves, self.manual_time = 0, 0
        self.manual_started = self.manual_done = False
        self.trail, self.hint_set = set(), set()
        self.show_hint = self.hint_used = False
        self.optimal = None
        self.move_cd = 0
        self.mechanics = None
        self.manual_results = {}
        self.manual_message = "Find the gold key, unlock the door, then reach the exit."
        self.reset_anim()

    def reset_anim(self):
        self.phase = "explore"     # explore -> path -> wait
        self.idx = 0
        self.acc = 0               # ms accumulated since the last animation step
        self.paused = False
        self.explored_set, self.path_set = set(), set()
        self.head = None           # latest cell the search looked at
        self.ai_pos = self.start   # where the AI character stands

    def new_session(self):
        """Called by Start: load + validate the maze, forget old comparison results."""
        try:
            self.env, self.grid, self.start, self.goal = load_environment()
        except MazeError as e:
            self.error_msg, self.state = str(e), ERROR
            return
        except Exception as e:
            self.error_msg, self.state = f"Could not load the maze: {e}", ERROR
            return
        self.results = {}
        # Evaluate the available solvers on this maze and recommend the most efficient
        # shortest-path option (fewest moves, then fewest explored nodes).
        self.recommendation_results = {a: run_algorithm(a, self.grid, self.start, self.goal) for a in ALGOS}
        candidates = [(len(r["path"]) - 1, r["nodes"], a) for a, r in self.recommendation_results.items()
                      if r["ok"]]
        self.recommended = min(candidates)[2] if candidates else "BFS"
        rr = self.recommendation_results[self.recommended]
        self.recommendation_reason = (f"It finds a {len(rr['path']) - 1}-move route while exploring "
                                      f"{rr['nodes']} nodes on this maze.") if rr["ok"] else "No available solver found a route."
        self.state = SELECT

    def solve(self, label):
        self.selected = label
        self.current = run_algorithm(label, self.grid, self.start, self.goal)
        self.results[label] = self.current
        res = self.current
        # keep Person 1's stats dictionary up to date as well
        self.env.set_stats(res["nodes"], len(res["path"]) - 1 if res["ok"] else "-",
                           len(res["path"]) - 1 if res["ok"] else "-", f"{res['time_ms']:.3f} ms")
        self.reset_anim()
        self.state = PLAYING

    def begin_practice(self):
        self.practice_pos = self.start
        self.practice_step = 0
        self.practice_done = False
        self.practice_message = 'Your turn: choose the next cell on the highlighted AI route.'
        self.ai_pos = self.practice_pos
        self.explored_set = {self.start}
        self.path_set = set(self.current['path'] or [])
        self.state = PRACTICE

    def practice_move(self, dr, dc):
        if self.practice_done or not self.current or not self.current['ok']:
            return
        path = self.current['path']
        nxt = (self.practice_pos[0] + dr, self.practice_pos[1] + dc)
        if not _valid(self.grid, nxt):
            self.practice_message = 'That cell is blocked. Choose a walkable neighboring cell.'
            return
        expected = path[self.practice_step + 1] if self.practice_step + 1 < len(path) else None
        if nxt != expected:
            self.practice_message = 'Not the next step on this route. Think about the algorithm and try again.'
            return
        self.practice_pos = nxt
        self.practice_step += 1
        self.ai_pos = nxt
        self.explored_set.add(nxt)
        if nxt == self.goal:
            self.practice_done = True
            self.practice_message = 'Excellent! You followed the algorithm and reached the goal.'
        else:
            self.practice_message = 'Correct move! Now choose the next cell.'

    def toggle_pause(self):
        self.paused = not self.paused

    # ----- manual mode -----
    def start_manual(self):
        # environment.py uses X for the locked door; mechanics.py uses D for a gold door.
        symbol_grid = [list(row) for row in E.MAP]
        for r, row in enumerate(symbol_grid):
            for c, symbol in enumerate(row):
                if symbol == "X":
                    symbol_grid[r][c] = "D"

        self.mechanics = GameMechanics(symbol_grid, required_keys=("gold",),
                                       max_moves=None, consume_keys=False)
        problems = self.mechanics.validate()
        if problems:
            self.error_msg = "Map / mechanics error: " + " ".join(problems)
            self.state = ERROR
            return

        self.manual_pos = self.start
        self.manual_moves, self.manual_time = 0, 0
        self.manual_started = self.manual_done = False
        self.trail = {self.start}
        self.show_hint = self.hint_used = False
        self.move_cd, self.acc = 0, 0
        self.manual_message = "Find the gold key, unlock the door, then reach the exit."

        # Compare algorithms on the same maze, assuming the player has the key
        # and can therefore pass through the locked door.
        comparison_grid = [row[:] for row in self.grid]
        for r, row in enumerate(comparison_grid):
            for c, value in enumerate(row):
                if value == 2:
                    comparison_grid[r][c] = 0
        self.manual_results = {
            label: run_algorithm(label, comparison_grid, self.start, self.goal)
            for label in ALGOS
        }
        valid_lengths = [len(res["path"]) - 1 for res in self.manual_results.values()
                         if res["ok"] and res["path"]]
        self.optimal = min(valid_lengths) if valid_lengths else None
        best = min((res for res in self.manual_results.values() if res["ok"]),
                   key=lambda res: len(res["path"]) - 1, default=None)
        self.hint_set = set(best["path"]) if best else set()
        self.sync_manual_view()
        self.state = MANUAL

    def sync_manual_view(self):
        """Feeds the shared maze drawing: trail = orange, hint = green, player = you."""
        self.ai_pos = self.manual_pos
        self.explored_set = set(self.trail)
        self.path_set = set(self.hint_set) if self.show_hint else set()
        self.head = None

    def toggle_hint(self):
        self.show_hint = not self.show_hint
        if self.show_hint:
            self.hint_used = True
        self.sync_manual_view()

    def try_move(self, dr, dc):
        if self.manual_done or self.mechanics is None:
            return False
        new = (self.manual_pos[0] + dr, self.manual_pos[1] + dc)
        result = self.mechanics.move_player(new)
        self.manual_message = result.get("message") or ""
        if not result["allowed"]:
            if result.get("event") == "door_locked":
                self.manual_message = "Door locked! Collect the gold key first."
            return False

        self.manual_pos = tuple(self.mechanics.player_pos)
        self.manual_started = True
        self.manual_moves = self.mechanics.moves_used
        self.trail.add(self.manual_pos)

        if result["event"] == "goal":
            self.manual_done, self.acc = True, 0
            self.manual_message = "You escaped! The key opened the way."
        elif result["event"] == "goal_locked":
            self.manual_message = "Exit locked. Collect the gold key first."
        elif result["event"] == "key":
            self.manual_message = "Gold key collected! Now find the locked door."
        elif result["event"] == "door_open":
            self.manual_message = "Door unlocked! Keep going to the exit."
        self.sync_manual_view()
        return True

    def update_manual(self, dt):
        if self.manual_done:
            self.acc += dt
            if self.acc >= MANUAL_END_PAUSE:
                self.state = MANUAL_RESULT
            return
        if self.mechanics and self.mechanics.check_lose():
            self.manual_message = self.mechanics.lost_reason
            self.state = MANUAL_RESULT
            return
        if self.manual_started:
            self.manual_time += dt
        self.move_cd = max(0, self.move_cd - dt)
        d = held_direction()
        if d is None:
            self.move_cd = 0
        elif self.move_cd == 0:
            self.try_move(*d)
            self.move_cd = MOVE_DELAY

    def update(self, dt):
        """Advance the animation. Uses elapsed time so speed is independent of FPS."""
        if self.state == MANUAL:
            self.update_manual(dt)
            return
        if self.paused:
            return
        self.acc += dt
        while self.state == PLAYING:
            if self.phase == "explore":
                delay = SPEEDS[self.speed][0]
            elif self.phase == "path":
                delay = SPEEDS[self.speed][1]
            else:
                delay = END_PAUSE
            if self.acc < delay:
                break
            self.acc -= delay
            self.step()

    def step(self):
        res = self.current
        if self.phase == "explore":
            if self.idx < len(res["explored"]):
                self.head = res["explored"][self.idx]
                self.explored_set.add(self.head)
                self.idx += 1
            else:
                self.head = None
                self.phase, self.idx = ("path", 0) if res["ok"] else ("wait", 0)
        elif self.phase == "path":
            if self.idx < len(res["path"]):
                self.ai_pos = res["path"][self.idx]
                self.path_set.add(self.ai_pos)
                self.idx += 1
            else:
                self.phase = "wait"
        else:
            self.state = RESULT


# ---------- drawing: the maze (uses Person 1's drawing helpers) ----------
def draw_world(g):
    grid, now = g.grid, time.time()
    rows, cols = len(grid), len(grid[0])

    # pass 1: floors + search overlays (always behind the walls)
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != 1:
                x, y = MAP_X + c * T, MAP_Y + r * T
                pygame.draw.rect(screen, E.FLOOR_A if (r + c) % 2 == 0 else E.FLOOR_B, (x, y, T, T))
                pygame.draw.rect(screen, E.FLOOR_LINE, (x, y, T, T), 1)
                if (r, c) in g.path_set:
                    screen.blit(OV_PATH, (x, y))
                elif (r, c) in g.explored_set:
                    screen.blit(OV_EXPLORED, (x, y))
    sr, sc = g.start
    pygame.draw.rect(screen, (200, 170, 80),
                     (MAP_X + sc * T + 5, MAP_Y + sr * T + 5, T - 10, T - 10), 2, border_radius=6)
    if g.head:
        pygame.draw.rect(screen, WHITE, (MAP_X + g.head[1] * T + 2, MAP_Y + g.head[0] * T + 2, T - 4, T - 4),
                         3, border_radius=4)

    # pass 2: row by row (walls -> items -> AI character) to get the 3D depth
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                x, y = MAP_X + c * T, MAP_Y + r * T
                E.draw_wall(screen, x, y, T, E.WALL_H, ((r * 7 + c * 13) % 3) * 5 - 5)
                if r < rows - 1 and grid[r + 1][c] == 0 and (r * 3 + c) % 4 == 0:
                    tx, ty = x + T // 2, y + T - E.WALL_H // 2
                    flick = int(now * 8 + c) % 2
                    screen.blit(g.env.glow, (tx - 40, ty - 40))
                    pygame.draw.circle(screen, (255, 150, 40), (tx, ty), 4 + flick)
                    pygame.draw.circle(screen, (255, 225, 110), (tx, ty), 2)

        for c in range(cols):
            cx, cy = MAP_X + c * T + T / 2, MAP_Y + r * T + T / 2 - 4
            ch = E.MAP[r][c] if r < len(E.MAP) and c < len(E.MAP[r]) else "0"
            if ch == "K":
                key_pos = (r, c)
                if not (g.mechanics and key_pos not in g.mechanics.keys):
                    E.draw_shadow(screen, cx, cy + 14, 16, 7)
                    E.draw_key(screen, cx, cy + math.sin(now * 3) * 3, 0.9)
            elif ch == "T":
                chest = g.mechanics.chests.get((r, c)) if g.mechanics else None
                if not chest or not chest["open"]:
                    E.draw_shadow(screen, cx, cy + 16, 30, 10)
                    E.draw_chest(screen, cx, cy, 0.9)
            elif ch == "X":
                door = g.mechanics.doors.get((r, c)) if g.mechanics else None
                if not door or not door["open"]:
                    E.draw_shadow(screen, cx, cy + 18, 26, 9)
                    E.draw_door(screen, cx, cy, 0.9)
                else:
                    pygame.draw.rect(screen, (105, 75, 35),
                                     (MAP_X + c * T + 8, MAP_Y + r * T + 8, T - 16, T - 16),
                                     2, border_radius=4)
            elif ch == "G":
                E.draw_shadow(screen, cx, cy + 18, 26, 9)
                E.draw_exit(screen, cx, cy, 0.9)

        if g.ai_pos and r == g.ai_pos[0]:
            px, py = MAP_X + g.ai_pos[1] * T + T / 2, MAP_Y + r * T + T / 2
            screen.blit(g.env.player_glow, (px - 55, py - 55))
            E.draw_shadow(screen, px, py + 10, 30, 11)
            E.draw_player(screen, px, py - 10 + math.sin(now * 5) * 1.2, E.PLAYER_SCALE)

    banner_text = None
    if g.state == MANUAL and g.manual_done:
        banner_text = "YOU ESCAPED!"
    elif g.state == PLAYING and g.phase == "wait" and g.current["ok"]:
        banner_text = "GOAL REACHED!"
    if banner_text:
        banner = pygame.Rect(0, 0, 420, 90)
        banner.center = (MAP_X + MAP_W // 2, MAP_Y + MAP_H // 2)
        pygame.draw.rect(screen, E.PANEL_BG, banner, border_radius=12)
        pygame.draw.rect(screen, E.GOLD, banner, 3, border_radius=12)
        E.draw_text(screen, font_banner, banner_text, E.GOLD, banner.centerx, banner.centery, center=True)


def draw_side_panels(g):
    ctrl = pygame.Rect(PANEL_X, MAP_Y, PANEL_W, 275)
    panel(ctrl)
    text_center("CONTROLS", font, GOLD, ctrl.y + 22, PCX)
    btn_pause.text = "Resume" if g.paused else "Pause"
    btn_pause.draw(active=g.paused)
    btn_restart.draw()
    text_center("Speed", font_small, WHITE, MAP_Y + 150, PCX)
    for name, b in btn_speeds.items():
        b.draw(active=(name == g.speed))
    btn_back_select.draw()

    draw_legend_panel((("AI", "player"), ("Start", "start"), ("Goal", "goal"),
                       ("Explored", "explore"), ("Final Path", "path")))


def draw_legend_panel(items):
    legend = pygame.Rect(PANEL_X, MAP_Y + 290, PANEL_W, MAP_H - 290)
    panel(legend)
    text_center("LEGEND", font, GOLD, legend.y + 22, PCX)
    ix = legend.x + 30
    for i, (name, kind) in enumerate(items):
        iy = legend.y + 56 + i * 34
        if kind == "player":
            E.draw_player(screen, ix, iy, 0.6)
        elif kind == "goal":
            E.draw_exit(screen, ix, iy, 0.5)
        else:
            color = {"start": (200, 170, 80), "explore": EXPLORED_C, "path": PATH_C}[kind]
            pygame.draw.rect(screen, color, (ix - 12, iy - 12, 24, 24), 3 if kind == "start" else 0,
                             border_radius=5)
        text_left(name, font_small, WHITE, legend.x + 60, iy - 10)


def draw_stats(stats):
    bar = pygame.Rect(MAP_X, MAP_Y + MAP_H + 14, WIDTH - 2 * MAP_X, 70)
    panel(bar)
    col_w = bar.w // 4
    for i, (label, value) in enumerate(stats):
        cx = bar.x + col_w * i + col_w // 2
        text_center(label, font_small, GREY, bar.y + 18, cx)
        text_center(value, font_big, E.GREEN, bar.y + 47, cx)


def draw_stats_bar(g):
    res = g.current
    searching = g.phase == "explore"
    nodes = len(g.explored_set) if (searching and res["has_trace"]) else res["nodes"]
    plen = "-" if (searching or not res["ok"]) else len(res["path"]) - 1
    stats = [("NODES EXPLORED", nodes), ("PATH LENGTH", plen), ("PATH COST", plen),
             ("TIME TAKEN", f"{res['time_ms']:.3f} ms")]
    draw_stats(stats)


# ---------- drawing: screens ----------
def draw_menu(g):
    text_center("Echoes of the", font_title, GOLD, 150)
    text_center("Lost Civilization", font_title, GOLD, 215)
    btn_start.draw()
    btn_menu_manual.draw()
    btn_exit.draw()


def draw_select(g):
    rows, cols = len(g.grid), len(g.grid[0])
    text_center("Choose Maze Solving Algorithm", font_big, GOLD, 110)
    text_center("Choose an algorithm, or follow the recommended learning path", font, SAND, 155)
    text_center(f"Maze {rows} x {cols}   |   Start {g.start}   |   Goal {g.goal}", font_small, GREY, 190)
    text_center(f"AI recommendation: {g.recommended}", font_big, PATH_C, 445)
    text_center(g.recommendation_reason, font_small, SAND, 475)
    for b in btn_algos:
        b.draw(active=(b.text == g.recommended))
    if g.results:
        btn_sel_compare.draw()
    btn_sel_back.draw()


def draw_playing(g):
    if g.paused:
        status = "Paused"
    elif g.phase == "explore":
        status = "Searching..."
    elif g.phase == "path":
        status = "Walking the final path..."
    else:
        status = "Done!"
    text_left(f"{g.selected}  -  {status}", font_big, GOLD, MAP_X, 10)
    if g.phase == "wait" and not g.current["ok"]:
        text_left("No path found! Try another algorithm.", font, RED, MAP_X, 50)
    else:
        text_left("SPACE: Pause/Resume   R: Restart   S: Skip   ESC: Back", font_small, SAND, MAP_X, 52)
    draw_world(g)
    draw_side_panels(g)
    draw_stats_bar(g)


def draw_learn(g):
    text_center("Learn the Recommended Algorithm", font_title, GOLD, 75)
    text_center(f"Recommended: {g.selected}", font_big, PATH_C, 145)
    lessons = {
        "BFS": ["Breadth-First Search explores the maze level by level.",
                "It uses a QUEUE (First In, First Out).", "In an unweighted maze, BFS finds a shortest path."],
        "DFS": ["Depth-First Search follows one branch as far as possible.",
                "It uses a STACK (Last In, First Out).", "It can use less memory, but does not guarantee the shortest path."],
        "A*": ["A* combines the distance already travelled (G) with an estimate to the goal (H).",
              "F = G + H. Here H is Manhattan distance.", "It prioritizes promising cells and often explores fewer nodes."],
    }
    y = 235
    for line in lessons.get(g.selected, []):
        text_center(line, font, WHITE, y)
        y += 48
    text_center("First watch the AI solve the maze, then solve the same route yourself.", font_small, SAND, 405)
    btn_learn_demo.draw()
    btn_learn_practice.draw()
    btn_learn_back.draw()


def draw_practice(g):
    text_left(f"Practice: {g.selected} | Follow the algorithm's route", font_big, GOLD, MAP_X, 10)
    text_left("Arrows / WASD: choose the next move   |   ESC: Lesson", font_small, SAND, MAP_X, 52)
    # Reuse the game's maze renderer; highlight the target route and current position.
    g.ai_pos = g.practice_pos
    g.path_set = set(g.current["path"] or [])
    g.explored_set = set(g.current["path"][:g.practice_step + 1]) if g.current and g.current["path"] else {g.start}
    draw_world(g)
    box = pygame.Rect(PANEL_X, MAP_Y, PANEL_W, 185)
    panel(box)
    text_center("YOUR PROGRESS", font, GOLD, box.y + 22, PCX)
    text_center(f"Steps: {g.practice_step} / {len(g.current['path']) - 1}", font, WHITE, box.y + 65, PCX)
    text_center("Goal reached!" if g.practice_done else "Find the next green cell", font_small, PATH_C, box.y + 100, PCX)
    btn_practice_restart.rect.center = (PCX, MAP_Y + 145)
    btn_practice_restart.draw()
    text_left(g.practice_message[:78], font_tiny, GOLD, MAP_X, MAP_Y + MAP_H + 1)
    if g.practice_done:
        text_center("Practice complete! You applied the algorithm.", font_big, PATH_C, HEIGHT - 48)


def draw_result(g):
    res = g.current
    text_center("Maze Solving Results", font_title, GOLD, 70)
    if res["ok"]:
        text_center("Goal Reached!", font_big, PATH_C, 135)
    else:
        text_center("No path found! Try another algorithm.", font_big, RED, 135)
    plen = len(res["path"]) - 1 if res["ok"] else "-"
    lines = [
        ("Algorithm", g.selected),
        ("Path Length", plen),
        ("Nodes Explored", res["nodes"]),
        ("Execution Time", f"{res['time_ms']:.3f} ms"),
        ("Status", "Success" if res["ok"] else "Failed"),
    ]
    y = 215
    for k, v in lines:
        text_center(f"{k}:  {v}", font_big, WHITE, y)
        y += 55
    text_center(f"Solver used: {res['source']}", font_small, GREY, 515)
    text_center("Press P to practice this algorithm", font_small, SAND, 555)
    btn_res_another.draw()
    btn_res_compare.draw()
    btn_res_menu.draw()


def manual_efficiency(g):
    """Shortest possible moves divided by the moves you used, in percent (None if unknown)."""
    if g.manual_done and g.optimal and g.manual_moves:
        return round(100 * g.optimal / g.manual_moves)
    return None


def draw_manual(g):
    text_left("Manual Mode - collect the key and escape!", font_big, GOLD, MAP_X, 10)
    text_left("Arrows / WASD: Move   H: Hint   R: Restart   ESC: Back", font_small, SAND, MAP_X, 52)
    draw_world(g)

    ctrl = pygame.Rect(PANEL_X, MAP_Y, PANEL_W, 180)
    panel(ctrl)
    text_center("CONTROLS", font, GOLD, ctrl.y + 20, PCX)
    btn_man_restart.rect.center = (PCX, MAP_Y + 58)
    btn_man_hint.rect.center = (PCX, MAP_Y + 101)
    btn_man_back.rect.center = (PCX, MAP_Y + 144)
    btn_man_restart.draw()
    btn_man_hint.text = "Hint: On" if g.show_hint else "Hint: Off"
    btn_man_hint.draw(active=g.show_hint)
    btn_man_back.draw()

    compare = pygame.Rect(PANEL_X, MAP_Y + 192, PANEL_W, 205)
    panel(compare)
    text_center("AI COMPARISON", font, GOLD, compare.y + 18, PCX)
    text_left("ALGO   PATH  NODES", font_tiny, SAND, compare.x + 9, compare.y + 42)
    for i, label in enumerate(ALGOS):
        res = g.manual_results.get(label)
        y = compare.y + 66 + i * 27
        if res and res["ok"]:
            path_len = len(res["path"]) - 1
            line = f"{label:<4}   {path_len:<4}  {res['nodes']}"
        else:
            line = f"{label:<4}   --    --"
        text_left(line, font_tiny, ALGO_COLORS[label], compare.x + 9, y)
        if res:
            text_left(f"{res['time_ms']:.3f} ms", font_tiny, WHITE, compare.x + 9, y + 13)

    inv = g.mechanics.get_inventory() if g.mechanics else {"keys": [], "treasures": [], "score": 0}
    inv_panel = pygame.Rect(PANEL_X, MAP_Y + 409, PANEL_W, MAP_H - 409)
    panel(inv_panel)
    text_center("INVENTORY", font, GOLD, inv_panel.y + 18, PCX)
    keys = ", ".join(inv["keys"]) if inv["keys"] else "None"
    text_left(f"Keys: {keys}", font_tiny, WHITE, inv_panel.x + 10, inv_panel.y + 42)
    text_left(f"Treasure: {len(inv['treasures'])}", font_tiny, WHITE, inv_panel.x + 10, inv_panel.y + 64)
    text_left(f"Score: {inv['score']}", font_tiny, WHITE, inv_panel.x + 10, inv_panel.y + 86)

    text_left(g.manual_message[:100], font_tiny, GOLD, MAP_X, MAP_Y + MAP_H + 1)
    eff = manual_efficiency(g)
    draw_stats([("YOUR MOVES", g.manual_moves), ("YOUR TIME", f"{g.manual_time / 1000:.1f} s"),
                ("BEST AI PATH", g.optimal if g.optimal is not None else "-"),
                ("EFFICIENCY", f"{eff}%" if eff is not None else "-")])


def draw_manual_result(g):
    text_center("You Escaped!", font_title, GOLD, 70)
    if g.optimal is not None and g.manual_moves == g.optimal:
        text_center("Perfect run - you found the shortest path!", font_big, PATH_C, 135)
    else:
        text_center("Can you find a shorter route?", font_big, SAND, 135)
    eff = manual_efficiency(g)
    lines = [("Moves", g.manual_moves),
             ("Time", f"{g.manual_time / 1000:.1f} s"),
             ("Shortest Path", g.optimal if g.optimal is not None else "-"),
             ("Efficiency", f"{eff}%" if eff is not None else "-"),
             ("Hint used", "Yes" if g.hint_used else "No")]
    y = 215
    for k, v in lines:
        text_center(f"{k}:  {v}", font_big, WHITE, y)
        y += 55
    best_algo = min(g.manual_results.items(),
                    key=lambda item: len(item[1]["path"]) - 1 if item[1]["ok"] else float("inf"))
    if best_algo[1]["ok"]:
        text_center(f"Best AI: {best_algo[0]} ({len(best_algo[1]['path']) - 1} moves)",
                    font_small, PATH_C, 500)
    text_center(f"Your moves: {g.manual_moves}  |  AI best: {g.optimal if g.optimal is not None else '-'}",
                font_small, SAND, 530)
    btn_man_again.draw()
    btn_man_algos.draw()
    btn_man_menu.draw()


def draw_bar_chart(title, x, y, w, values, fmt):
    """values: {label: number or None}"""
    text_center(title, font, GOLD, y, x + w // 2)
    base = y + 175
    pygame.draw.line(screen, SAND, (x, base), (x + w, base), 2)
    nums = [v for v in values.values() if v is not None]
    max_v = max(nums) if nums else 0
    slot = w // len(ALGOS)
    for i, label in enumerate(ALGOS):
        cx = x + slot * i + slot // 2
        v = values.get(label)
        if v is not None:
            bh = max(3, int(v / max_v * 110)) if max_v > 0 else 3
            pygame.draw.rect(screen, ALGO_COLORS[label], (cx - 28, base - bh, 56, bh))
            text_center(fmt(v), font_small, WHITE, base - bh - 12, cx)
        else:
            text_center("-", font_small, GREY, base - 12, cx)
        text_center(label, font_small, WHITE, base + 18, cx)


def draw_compare(g):
    text_center("Algorithm Comparison Dashboard", font_big, GOLD, 50)
    cols_x = [130, 310, 500, 700]
    for x, head in zip(cols_x, ("Algorithm", "Path Length", "Nodes Explored", "Time")):
        text_left(head, font, GOLD, x, 90)
    pygame.draw.line(screen, SAND, (100, 122), (WIDTH - 100, 122), 2)

    for i, label in enumerate(ALGOS):
        y = 135 + i * 34
        res = g.results.get(label)
        text_left(label, font, ALGO_COLORS[label], cols_x[0], y)
        if res is None:
            text_left("Not run yet", font, GREY, cols_x[1], y)
            continue
        cells = [str(len(res["path"]) - 1) if res["ok"] else "No path",
                 str(res["nodes"]), f"{res['time_ms']:.3f} ms"]
        for x, val in zip(cols_x[1:], cells):
            text_left(val, font, WHITE, x, y)

    if len(g.results) < 2:
        text_center("Run more algorithms on this maze to compare them.", font_small, SAND, 262)

    nodes = {a: r["nodes"] for a, r in g.results.items()}
    times = {a: r["time_ms"] for a, r in g.results.items()}
    draw_bar_chart("Nodes Explored", 60, 305, 380, nodes, lambda v: str(int(v)))
    draw_bar_chart("Execution Time (ms)", WIDTH - 440, 305, 380, times, lambda v: f"{v:.3f}")
    btn_cmp_another.draw()
    btn_cmp_menu.draw()


def draw_error(g):
    text_center("Maze Error", font_title, RED, 150)
    y = 250
    for line in wrap_text(g.error_msg, font_big, WIDTH - 140):
        text_center(line, font_big, WHITE, y)
        y += 42
    text_center("Please fix the maze in environment.py and run the game again.",
                font_small, SAND, y + 25)
    btn_err_back.draw()


DRAWERS = {MENU: draw_menu, SELECT: draw_select, LEARN: draw_learn, PRACTICE: draw_practice, PLAYING: draw_playing,
           RESULT: draw_result, COMPARE: draw_compare, ERROR: draw_error,
           MANUAL: draw_manual, MANUAL_RESULT: draw_manual_result}


# ---------- events ----------
def handle_event(g, event):
    """Returns False when the game should quit."""
    s = g.state
    if s == MENU:
        if btn_start.clicked(event):
            g.new_session()
        elif btn_menu_manual.clicked(event):
            g.new_session()
            if g.state == SELECT:          # maze loaded fine -> go straight into manual play
                g.start_manual()
        elif btn_exit.clicked(event):
            return False

    elif s == SELECT:
        for b in btn_algos:
            if b.clicked(event):
                g.selected = b.text
                g.current = run_algorithm(b.text, g.grid, g.start, g.goal)
                g.state = LEARN
                return True
        if btn_manual.clicked(event):
            g.start_manual()
        elif g.results and btn_sel_compare.clicked(event):
            g.state = COMPARE
        elif btn_sel_back.clicked(event):
            g.state = MENU

    elif s == LEARN:
        if btn_learn_demo.clicked(event):
            g.solve(g.selected)
        elif btn_learn_practice.clicked(event):
            if g.current is None:
                g.current = run_algorithm(g.selected, g.grid, g.start, g.goal)
            g.begin_practice()
        elif btn_learn_back.clicked(event):
            g.state = SELECT

    elif s == PRACTICE:
        if btn_practice_restart.clicked(event):
            g.begin_practice()
        if event.type == pygame.KEYDOWN:
            moves = {pygame.K_UP: (-1, 0), pygame.K_w: (-1, 0),
                     pygame.K_DOWN: (1, 0), pygame.K_s: (1, 0),
                     pygame.K_LEFT: (0, -1), pygame.K_a: (0, -1),
                     pygame.K_RIGHT: (0, 1), pygame.K_d: (0, 1)}
            if event.key in moves:
                g.practice_move(*moves[event.key])
            elif event.key == pygame.K_ESCAPE:
                g.state = LEARN

    elif s == PLAYING:
        if btn_pause.clicked(event):
            g.toggle_pause()
        elif btn_restart.clicked(event):
            g.reset_anim()
        elif btn_back_select.clicked(event):
            g.state = SELECT
        else:
            for name, b in btn_speeds.items():
                if b.clicked(event):
                    g.speed = name
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                g.toggle_pause()
            elif event.key == pygame.K_r:
                g.reset_anim()
            elif event.key == pygame.K_s:
                g.state = RESULT
            elif event.key == pygame.K_ESCAPE:
                g.state = SELECT

    elif s == RESULT:
        if btn_res_another.clicked(event):
            g.state = SELECT
        elif btn_res_compare.clicked(event):
            g.state = COMPARE
        elif btn_res_menu.clicked(event):
            g.state = MENU
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            g.begin_practice()

    elif s == COMPARE:
        if btn_cmp_another.clicked(event):
            g.state = SELECT
        elif btn_cmp_menu.clicked(event):
            g.state = MENU

    elif s == MANUAL:
        if btn_man_restart.clicked(event):
            g.start_manual()
        elif btn_man_hint.clicked(event):
            g.toggle_hint()
        elif btn_man_back.clicked(event):
            g.state = SELECT
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                g.start_manual()
            elif event.key == pygame.K_h:
                g.toggle_hint()
            elif event.key == pygame.K_ESCAPE:
                g.state = SELECT

    elif s == MANUAL_RESULT:
        if btn_man_again.clicked(event):
            g.start_manual()
        elif btn_man_algos.clicked(event):
            g.state = SELECT
        elif btn_man_menu.clicked(event):
            g.state = MENU

    elif s == ERROR:
        if btn_err_back.clicked(event):
            g.state = MENU
    return True


# ---------- main loop ----------
def main():
    game = Game()
    running = True
    while running:
        dt = min(clock.get_time(), 100)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif not handle_event(game, event):
                running = False

        if game.state in (PLAYING, MANUAL):
            game.update(dt)

        screen.fill(BG)
        DRAWERS[game.state](game)
        pygame.display.update()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
