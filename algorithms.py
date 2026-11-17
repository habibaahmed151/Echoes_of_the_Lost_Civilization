"""
Echoes of the Lost Civilization
Person 2 - AI Search Algorithms

Compatible with environment.py:
    0 = walkable floor
    1 = wall
    2 = obstacle
Coordinates are (row, column), matching Environment.get_start()/get_goal().
"""

from collections import deque
from heapq import heappush, heappop
from time import perf_counter


def _valid_position(grid, position):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    r, c = position
    return 0 <= r < rows and 0 <= c < cols and grid[r][c] == 0


def _neighbors(grid, position):
    """Return walkable neighbors in up, right, down, left order."""
    r, c = position
    candidates = ((r - 1, c), (r, c + 1), (r + 1, c), (r, c - 1))
    return [p for p in candidates if _valid_position(grid, p)]


def _reconstruct_path(parent, start, goal):
    if goal != start and goal not in parent:
        return []

    path = [goal]
    while path[-1] != start:
        path.append(parent[path[-1]])
    path.reverse()
    return path


def bfs(grid, start, goal):
    """Breadth-First Search. Finds a shortest path on this unweighted grid."""
    started = perf_counter()
    if not _valid_position(grid, start) or not _valid_position(grid, goal):
        return _result([], 0, started)

    queue = deque([start])
    visited = {start}
    parent = {}
    explored = 0

    while queue:
        current = queue.popleft()
        explored += 1
        if current == goal:
            break

        for nxt in _neighbors(grid, current):
            if nxt not in visited:
                visited.add(nxt)
                parent[nxt] = current
                queue.append(nxt)

    path = _reconstruct_path(parent, start, goal) if goal in visited else []
    return _result(path, explored, started)


def dfs(grid, start, goal):
    """Depth-First Search. Finds a path, but not necessarily the shortest."""
    started = perf_counter()
    if not _valid_position(grid, start) or not _valid_position(grid, goal):
        return _result([], 0, started)

    stack = [start]
    visited = {start}
    parent = {}
    explored = 0

    while stack:
        current = stack.pop()
        explored += 1
        if current == goal:
            break

        # Reverse so the visit order is consistent with BFS (up, right, down, left).
        for nxt in reversed(_neighbors(grid, current)):
            if nxt not in visited:
                visited.add(nxt)
                parent[nxt] = current
                stack.append(nxt)

    path = _reconstruct_path(parent, start, goal) if goal in visited else []
    return _result(path, explored, started)


def astar(grid, start, goal):
    """A* Search using Manhattan distance and unit movement costs."""
    started = perf_counter()
    if not _valid_position(grid, start) or not _valid_position(grid, goal):
        return _result([], 0, started)

    def heuristic(position):
        return abs(position[0] - goal[0]) + abs(position[1] - goal[1])

    open_heap = []
    heappush(open_heap, (heuristic(start), 0, start))
    parent = {}
    g_score = {start: 0}
    closed = set()
    explored = 0

    while open_heap:
        _, current_cost, current = heappop(open_heap)

        if current in closed:
            continue

        closed.add(current)
        explored += 1

        if current == goal:
            break

        for nxt in _neighbors(grid, current):
            tentative_g = current_cost + 1
            if tentative_g < g_score.get(nxt, float("inf")):
                g_score[nxt] = tentative_g
                parent[nxt] = current
                heappush(
                    open_heap,
                    (tentative_g + heuristic(nxt), tentative_g, nxt)
                )

    path = _reconstruct_path(parent, start, goal) if goal in closed else []
    return _result(path, explored, started)


def _result(path, explored_nodes, started):
    elapsed_ms = (perf_counter() - started) * 1000
    return {
        "path": path,                         # list of (row, column)
        "found": bool(path),
        "path_length": max(0, len(path) - 1), # number of moves
        "explored_nodes": explored_nodes,
        "execution_time_ms": elapsed_ms,
    }


def find_path(grid, start, goal, algorithm="bfs"):
    """
    Common interface for the game.
    algorithm: "bfs", "dfs", or "astar"
    Returns a result dictionary (see _result).
    """
    methods = {"bfs": bfs, "dfs": dfs, "astar": astar}
    key = algorithm.lower().replace("*", "star").strip()
    if key not in methods:
        raise ValueError("algorithm must be 'bfs', 'dfs', or 'astar'")
    return methods[key](grid, start, goal)


def find_path_from_environment(environment, algorithm="bfs"):
    """
    Direct connection to Person 1's Environment class.
    No edits/imports inside environment.py are required.
    """
    return find_path(
        environment.get_grid(),
        environment.get_start(),
        environment.get_goal(),
        algorithm
    )


def compare_algorithms(environment):
    """Run all three algorithms on the same Environment and return their results."""
    return {
        name: find_path_from_environment(environment, name)
        for name in ("bfs", "dfs", "astar")
    }


if __name__ == "__main__":
    # Standalone integration test using the actual environment.py map.
    from environment import Environment

    game = Environment()
    for name, result in compare_algorithms(game).items():
        print(f"\n{name.upper()}")
        print("Found:", result["found"])
        print("Path length:", result["path_length"])
        print("Explored nodes:", result["explored_nodes"])
        print(f"Execution time: {result['execution_time_ms']:.3f} ms")
        print("Path:", result["path"])
