Echoes of the Lost Civilization - AI Learning Edition

Files:
- main.py       Game controller with algorithm recommendation, lessons, AI demo,
                and interactive practice in the same maze.
- environment.py Original visual environment and maze.
- algorithms.py BFS, DFS and A* implementations.
- mechanics.py  Game mechanics module (keys, door and inventory).

How to run:
1. Extract all four .py files into the SAME folder.
2. Open a terminal in that folder.
3. Install pygame: python -m pip install pygame
4. Run: python main.py

New learning flow:
1. Click Start. The game evaluates BFS, DFS and A* on the current maze.
2. The selection screen displays a recommendation based on shortest route,
   then fewer explored nodes as a tie-breaker. The recommended algorithm is highlighted.
3. Choose an algorithm to open its short lesson.
4. Click Watch AI Demonstration to watch the solver explore and reach the goal.
   On the results screen, press P to practice the same algorithm.
5. Or click Practice This Algorithm directly from the lesson screen.
6. In Practice, use Arrow Keys or WASD to move through the route selected by
   the algorithm. Correct moves advance; incorrect or blocked moves show feedback.
   Press ESC to return to the lesson or Restart Practice to start again.

Existing controls:
- AI demo: SPACE pause/resume, R restart, S skip to results, ESC back to selection.
- Main menu still includes a direct Manual Mode option for free exploration.
- Manual mode: Arrow Keys/WASD move, H toggles hint, R restarts, ESC returns.

Important:
- Run main.py only; keep all four Python files together.
- The learning/practice flow stays inside the same game and same maze.
- The practice stage asks the player to reproduce the selected algorithm's
  calculated route; it is not a free-form maze run.
