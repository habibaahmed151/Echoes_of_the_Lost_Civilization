"""
mechanics.py  -  Person 3: Puzzles & Game Mechanics
Echoes of the Lost Civilization

Grid symbols (agree on them with Person 1):
    0 = open path        1 = wall
    S = start            G = goal
    K = gold key         k = silver key
    D = gold door        d = silver door
    T = treasure chest   P = puzzle tile      X = trap

Usage from main.py (Person 4):
    mech = GameMechanics(grid, max_moves=80)
    res = mech.move_player((row, col))      # when the player tries to move
    if res["allowed"]: draw player at mech.player_pos
    show res["message"]; use res["event"] to play effects
    mech.get_inventory()                    # keys, treasures, score, moves_left
    mech.check_win() / mech.check_lose()
"""
import copy

# ---------------- Settings (edit freely) ----------------
KEY_SYMBOLS = {"K": "gold", "k": "silver"}
DOOR_SYMBOLS = {"D": "gold", "d": "silver"}
REWARDS = {"treasure": 100, "puzzle": 50}
TRAP_PENALTY = {"points": 30, "moves": 2}
TREASURE_NAMES = ["Golden Idol", "Ancient Crown", "Ruby Amulet", "Jade Scarab"]
DEFAULT_PUZZLES = [
    {"question": "What comes next?  2, 4, 8, 16, ?", "answer": "32"},
    {"question": "Complete the sequence: A, C, E, G, ?", "answer": "I"},
    {"question": "How many sides does a pyramid base have (square pyramid)?", "answer": "4"},
]


class GameMechanics:
    def __init__(self, grid, max_moves=None, required_keys=("gold",),
                 puzzles=None, max_attempts=3, consume_keys=False):
        """
        max_moves      : None = unlimited moves
        required_keys  : keys the player must hold to win at the goal
        puzzles        : list of {"question","answer"} (kept on reset)
        max_attempts   : wrong answers allowed per puzzle (None = unlimited)
        consume_keys   : True = a key disappears after opening its door
        """
        self.grid = grid
        self.max_moves = max_moves
        self.required_keys = list(required_keys)
        self.puzzles_config = copy.deepcopy(puzzles or DEFAULT_PUZZLES)
        self.max_attempts = max_attempts
        self.consume_keys = consume_keys
        self.reset()

    # ------------------------------------------------------------
    # Setup / Reset  (reset keeps the custom puzzles and settings)
    # ------------------------------------------------------------
    def reset(self):
        self.moves_used = 0
        self.score = 0
        self.inventory = {"keys": [], "treasures": []}
        self.game_over = False
        self.won = False
        self.lost_reason = ""
        self.start = None
        self.goal = None
        self.keys = {}           # pos -> key_id
        self.doors = {}          # pos -> {"key", "open"}
        self.chests = {}         # pos -> {"name", "points", "open"}
        self.traps = {}          # pos -> {"triggered"}
        self.puzzle_tiles = {}   # pos -> {"question","answer","solved","attempts"}
        self.active_puzzle = None
        self._load_from_grid()
        self.player_pos = self.start

    def _load_from_grid(self):
        p_i = t_i = 0
        for r, row in enumerate(self.grid):
            for c, cell in enumerate(row):
                pos, cell = (r, c), str(cell)
                if cell == "S":
                    self.start = pos
                elif cell == "G":
                    self.goal = pos
                elif cell in KEY_SYMBOLS:
                    self.keys[pos] = KEY_SYMBOLS[cell]
                elif cell in DOOR_SYMBOLS:
                    self.doors[pos] = {"key": DOOR_SYMBOLS[cell], "open": False}
                elif cell == "T":
                    name = TREASURE_NAMES[t_i % len(TREASURE_NAMES)]
                    t_i += 1
                    self.chests[pos] = {"name": name, "points": REWARDS["treasure"], "open": False}
                elif cell == "X":
                    self.traps[pos] = {"triggered": False}
                elif cell == "P":
                    pz = self.puzzles_config[p_i % len(self.puzzles_config)]
                    p_i += 1
                    self.puzzle_tiles[pos] = {"question": pz["question"], "answer": pz["answer"],
                                              "solved": False, "attempts": 0}

    def validate(self):
        """Returns a list of map problems (call once after building the map)."""
        w = []
        if self.start is None: w.append("No start 'S' on the map.")
        if self.goal is None: w.append("No goal 'G' on the map.")
        on_map = set(self.keys.values())
        for k in self.required_keys:
            if k not in on_map:
                w.append(f"Required key '{k}' is not on the map (game can't be won).")
        for pos, d in self.doors.items():
            if d["key"] not in on_map:
                w.append(f"Door at {pos} needs a '{d['key']}' key that is not on the map.")
        return w

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def in_bounds(self, pos):
        r, c = pos
        return 0 <= r < len(self.grid) and 0 <= c < len(self.grid[0])

    def is_wall(self, pos):
        return str(self.grid[pos[0]][pos[1]]) == "1"

    def is_blocked(self, pos):
        """Static check: wall, closed door or unsolved puzzle."""
        if not self.in_bounds(pos) or self.is_wall(pos):
            return True
        if pos in self.doors and not self.doors[pos]["open"]:
            return True
        if pos in self.puzzle_tiles and not self.puzzle_tiles[pos]["solved"]:
            return True
        return False

    def _is_adjacent(self, pos):
        r, c = self.player_pos
        return abs(pos[0] - r) + abs(pos[1] - c) == 1   # up/down/left/right only

    @property
    def moves_left(self):
        return None if self.max_moves is None else max(0, self.max_moves - self.moves_used)

    def has_key(self, key_id):
        return key_id in self.inventory["keys"]

    def _missing_keys(self):
        return [k for k in self.required_keys if not self.has_key(k)]

    @staticmethod
    def _result(allowed, message="", event="none"):
        return {"allowed": allowed, "message": message, "event": event}

    # ------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------
    def get_inventory(self):
        return {"keys": list(self.inventory["keys"]),
                "treasures": list(self.inventory["treasures"]),
                "score": self.score,
                "moves_left": self.moves_left}

    # ------------------------------------------------------------
    # Keys / Doors / Treasure / Traps
    # ------------------------------------------------------------
    def collect_key(self, pos):
        if pos in self.keys:
            self.inventory["keys"].append(self.keys.pop(pos))
            return True
        return False

    def open_door(self, pos):
        door = self.doors.get(pos)
        if door is None:
            return False, "No door here."
        if door["open"]:
            return True, "Door already open."
        if self.has_key(door["key"]):
            door["open"] = True
            if self.consume_keys:
                self.inventory["keys"].remove(door["key"])
            return True, f"{door['key'].capitalize()} door unlocked!"
        return False, f"Door is locked! You need the {door['key']} key."

    def open_treasure(self, pos):
        """Returns points gained (0 if no chest / already open)."""
        chest = self.chests.get(pos)
        if chest and not chest["open"]:
            chest["open"] = True
            self.score += chest["points"]
            self.inventory["treasures"].append(chest["name"])
            return chest["points"]
        return 0

    def trigger_trap(self, pos):
        """One-time trap: lose points and moves. Returns True if triggered."""
        trap = self.traps.get(pos)
        if trap and not trap["triggered"]:
            trap["triggered"] = True
            self.score = max(0, self.score - TRAP_PENALTY["points"])
            self.moves_used += TRAP_PENALTY["moves"]
            return True
        return False

    # ------------------------------------------------------------
    # Puzzles
    # ------------------------------------------------------------
    def start_puzzle(self, pos):
        pz = self.puzzle_tiles.get(pos)
        if pz and not pz["solved"]:
            self.active_puzzle = pos
            return pz["question"]
        return None

    def solve_puzzle(self, answer, pos=None):
        """True if correct. Too many wrong answers = lose (check game_over)."""
        pos = pos or self.active_puzzle
        pz = self.puzzle_tiles.get(pos)
        if pz is None or pz["solved"] or self.game_over:
            return False
        if str(answer).strip().lower() == pz["answer"].strip().lower():
            pz["solved"] = True
            self.score += REWARDS["puzzle"]
            self.active_puzzle = None
            return True
        pz["attempts"] += 1
        if self.max_attempts is not None and pz["attempts"] >= self.max_attempts:
            self.fail_puzzle()
        return False

    def fail_puzzle(self):
        self.game_over = True
        self.lost_reason = "You failed the challenge!"

    # ------------------------------------------------------------
    # Movement - main entry point for Person 4
    # ------------------------------------------------------------
    def move_player(self, new_pos):
        """
        Returns {"allowed": bool, "message": str, "event": str}
        events: none, invalid, wall, door_locked, door_open, puzzle, key,
                treasure, trap, goal_locked, goal (win), lose
        """
        if self.game_over:
            return self._result(False, "Game over.", "win" if self.won else "lose")

        new_pos = tuple(new_pos)
        if not self.in_bounds(new_pos):
            return self._result(False, "Out of the map.", "invalid")
        if not self._is_adjacent(new_pos):                     # fix 1
            return self._result(False, "You can only move one step at a time.", "invalid")
        if self.is_wall(new_pos):
            return self._result(False, "A wall blocks the way.", "wall")

        event, msg = "none", ""

        if new_pos in self.doors and not self.doors[new_pos]["open"]:
            opened, dmsg = self.open_door(new_pos)
            if not opened:
                return self._result(False, dmsg, "door_locked")
            event, msg = "door_open", dmsg

        if new_pos in self.puzzle_tiles and not self.puzzle_tiles[new_pos]["solved"]:
            return self._result(False, self.start_puzzle(new_pos), "puzzle")

        # ---- the step is allowed ----
        self.player_pos = new_pos
        self.moves_used += 1

        if self.collect_key(new_pos):
            event, msg = "key", f"You collected the {self.inventory['keys'][-1]} key!"
        elif new_pos in self.chests and not self.chests[new_pos]["open"]:
            name = self.chests[new_pos]["name"]
            pts = self.open_treasure(new_pos)
            event, msg = "treasure", f"You found {name}! +{pts} points"
        elif self.trigger_trap(new_pos):
            event = "trap"
            msg = f"Trap! -{TRAP_PENALTY['points']} points, -{TRAP_PENALTY['moves']} moves"
        elif new_pos == self.goal:                              # fix 2
            missing = self._missing_keys()
            if missing:
                event, msg = "goal_locked", f"You need the {', '.join(missing)} key first!"
            else:
                self.won, self.game_over = True, True
                event, msg = "goal", "You reached the goal. You win!"

        if not self.won and self.check_lose():
            event, msg = "lose", self.lost_reason
        return self._result(True, msg, event)

    # ------------------------------------------------------------
    # Win / Lose
    # ------------------------------------------------------------
    def check_win(self):
        return self.won

    def check_lose(self):
        if self.won:
            return False
        if self.max_moves is not None and self.moves_used >= self.max_moves:
            self.game_over = True
            self.lost_reason = "You ran out of moves!"
        return self.game_over and not self.won


# ----------------------------------------------------------------
# Standalone tests:  python mechanics.py
# ----------------------------------------------------------------
if __name__ == "__main__":
    # --- full run: gold key, trap, silver key, silver door, gold door, treasure, puzzle
    grid = [["S", "0", "K", "X", "k"],
            ["1", "1", "1", "1", "d"],
            ["T", "P", "0", "D", "G"]]
    m = GameMechanics(grid, max_moves=30)
    assert m.validate() == []
    assert m.move_player((2, 4))["event"] == "invalid"          # no teleporting
    for p in [(0, 1), (0, 2)]: m.move_player(p)
    assert m.inventory["keys"] == ["gold"]
    assert m.move_player((0, 3))["event"] == "trap" and m.moves_used == 5
    assert m.move_player((0, 4))["event"] == "key"
    assert m.move_player((1, 4))["event"] == "door_open"
    assert m.move_player((2, 4))["event"] == "goal" and m.check_win()
    print("Full run OK:", m.get_inventory())

    # --- goal without the required key is NOT a win
    m2 = GameMechanics([["S", "G"]], required_keys=("gold",))
    assert m2.validate() != []
    assert m2.move_player((0, 1))["event"] == "goal_locked" and not m2.check_win()

    # --- door needs the matching key
    m3 = GameMechanics([["S", "d", "k"]])
    assert m3.move_player((0, 1))["event"] == "door_locked"

    # --- treasure + puzzle + custom puzzle kept after reset
    custom = [{"question": "1+1?", "answer": "2"}]
    m4 = GameMechanics([["S", "T", "P", "G"]], required_keys=(), puzzles=custom, max_attempts=2)
    assert m4.move_player((0, 1))["event"] == "treasure" and m4.score == 100
    assert m4.move_player((0, 2))["event"] == "puzzle"
    assert not m4.solve_puzzle("5") and not m4.solve_puzzle("7") and m4.check_lose()
    m4.reset()
    assert not m4.game_over and m4.puzzle_tiles[(0, 2)]["question"] == "1+1?"   # fix 3
    m4.move_player((0, 1)); m4.move_player((0, 2))
    assert m4.solve_puzzle("2") and m4.score == 150
    m4.move_player((0, 2)); assert m4.move_player((0, 3))["event"] == "goal"

    # --- out of moves = lose
    m5 = GameMechanics([["S", "0", "0", "G"]], max_moves=2, required_keys=())
    m5.move_player((0, 1)); assert m5.move_player((0, 2))["event"] == "lose"
    print("All tests passed")
