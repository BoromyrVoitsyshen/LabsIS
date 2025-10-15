import pygame as pg
import random
from collections import deque, defaultdict
from dataclasses import dataclass


# =====================
# Завантаження налаштувань
# =====================
def load_settings(filename="settings.txt"):
    settings = {}
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                # Спробуємо перетворити значення на число (int)
                if value.isdigit():
                    settings[key] = int(value)
                else:
                    settings[key] = value
    except FileNotFoundError:
        print(f"Помилка: Файл налаштувань '{filename}' не знайдено. Використовуються значення за замовчуванням.")
    except Exception as e:
        print(f"Помилка при читанні файлу налаштувань: {e}. Використовуються значення за замовчуванням.")
    return settings

# Завантажуємо налаштування один раз при старті
SETTINGS = load_settings()

# =====================
# Параметри екрану/сітки
# =====================
# Значення за замовчуванням, якщо у файлі їх немає
TILE = SETTINGS.get('TILE', 24)
GRID_W = SETTINGS.get('GRID_W', 27)
GRID_H = SETTINGS.get('GRID_H', 21)
SCREEN_W, SCREEN_H = GRID_W * TILE, GRID_H * TILE
FPS = SETTINGS.get('FPS', 60)

PAC_STEP_MS = SETTINGS.get('PAC_STEP_MS', 180)
GHOST_STEP_MS = SETTINGS.get('GHOST_STEP_MS', 220)

PELLET_SCORE = SETTINGS.get('PELLET_SCORE', 10)

# Складність за замовчуванням (число від 0 до 5)
DEFAULT_DIFFICULTY = SETTINGS.get('DIFFICULTY', 1)

# Кольори
BLACK = (0, 0, 0)
BLUE = (33, 33, 222)
YELLOW = (255, 210, 0)
WHITE = (240, 240, 240)
PINK = (255, 120, 180)
CYAN = (120, 220, 255)
ORANGE = (255, 170, 50)
RED = (255, 70, 70)
GREY = (90, 90, 90)

# Коди клітинок
WALL = 1
FLOOR = 0
GATE = 2
PEN = 3

DIRS = {
    pg.K_LEFT: (-1, 0), pg.K_a: (-1, 0),
    pg.K_RIGHT: (1, 0), pg.K_d: (1, 0),
    pg.K_UP: (0, -1), pg.K_w: (0, -1),
    pg.K_DOWN: (0, 1), pg.K_s: (0, 1)
}

DIR_LIST = [(-1,0),(1,0),(0,-1),(0,1)]

# Залишаємо лише кольори привидів. Ролі будуть призначатися динамічно.
GHOST_COLORS = [PINK, CYAN, ORANGE, RED]

# Словник для зручного перемикання складності клавішами
DIFFICULTY_KEYS = {
    pg.K_0: 0, pg.K_1: 1, pg.K_2: 2, pg.K_3: 3, pg.K_4: 4, pg.K_5: 5
}

# Назви рівнів складності для відображення в HUD
DIFFICULTY_NAMES = ['Novice', 'Apprentice', 'Adept', 'Expert', 'Master', 'Legendary']

# =====================
# Допоміжні функції
# =====================

def in_bounds(x, y):
    return 0 <= x < GRID_W and 0 <= y < GRID_H

def manhattan(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def neighbors4(x, y):
    for dx, dy in DIR_LIST:
        nx, ny = x+dx, y+dy
        if in_bounds(nx, ny):
            yield nx, ny

def line_of_sight(grid, a, b):
    """Брезенхем по клітинках: чи є пряма видимість без стін?"""
    (x0,y0),(x1,y1) = a, b
    dx = abs(x1-x0); dy = abs(y1-y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x,y = x0,y0
    while True:
        if grid[y][x] == WALL:
            return False
        if (x,y) == (x1,y1):
            return True
        e2 = 2*err
        if e2 > -dy:
            err -= dy; x += sx
        if e2 < dx:
            err += dx; y += sy

def find_path_step_bfs(grid, start_pos, end_pos):
    """
    Знаходить перший крок найкоротшого шляху від start_pos до end_pos за допомогою BFS.
    Враховує стіни.
    """
    q = deque([(start_pos, [])])  # Черга: (поточна_позиція, шлях_до_неї)
    visited = {start_pos}

    while q:
        (x, y), path = q.popleft()

        if (x, y) == end_pos:
            # Якщо шлях знайдено, повертаємо перший крок
            if not path:
                return (0, 0) # Вже на місці
            return path[0]

        # Додаємо сусідів до черги
        for dx, dy in DIR_LIST:
            nx, ny = x + dx, y + dy
            
            if in_bounds(nx, ny) and (nx, ny) not in visited and grid[ny][nx] != WALL:
                visited.add((nx, ny))
                new_path = path + [(dx, dy)]
                q.append(((nx, ny), new_path))
    
    # Якщо шлях не знайдено (дуже рідкісний випадок)
    return (0, 0)

# =====================
# Генерація лабіринту — без тупиків і без тунелів за межі карти
# =====================

def _seal_outer_border(grid):
    """Суцільні стіни по краях (жодних виходів за карту)."""
    w, h = GRID_W, GRID_H
    for x in range(w):
        grid[0][x] = WALL
        grid[h-1][x] = WALL
    for y in range(h):
        grid[y][0] = WALL
        grid[y][w-1] = WALL

def _remove_dead_ends(grid, forbid=set()):
    """Прибирає всі тупики: кожна FLOOR-клітинка має ≥2 виходи. Зовнішню рамку не чіпаємо."""
    w, h = GRID_W, GRID_H
    changed = True
    while changed:
        changed = False
        for y in range(1, h-1):
            for x in range(1, w-1):
                if (x, y) in forbid:
                    continue
                if grid[y][x] != FLOOR:
                    continue
                exits = 0
                walls = []
                for nx, ny in neighbors4(x, y):
                    if grid[ny][nx] == FLOOR:
                        exits += 1
                    elif grid[ny][nx] == WALL and (nx, ny) not in forbid and 1 <= nx < w-1 and 1 <= ny < h-1:
                        walls.append((nx, ny))
                if exits >= 2:
                    continue
                if walls:
                    wx, wy = random.choice(walls)
                    grid[wy][wx] = FLOOR
                    changed = True
    _seal_outer_border(grid)

def generate_maze_braid(w, h):
    # Ініціалізація стінами
    grid = [[WALL for _ in range(w)] for __ in range(h)]

    # DFS-карвінг по «камерах» (непарні координати)
    def carve(x, y):
        dirs = [(2,0),(-2,0),(0,2),(0,-2)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x+dx, y+dy
            if 1 <= nx < w-1 and 1 <= ny < h-1 and grid[ny][nx] == WALL:
                grid[y+dy//2][x+dx//2] = FLOOR
                grid[ny][nx] = FLOOR
                carve(nx, ny)

    sx, sy = 1, 1
    grid[sy][sx] = FLOOR
    carve(sx, sy)

    # Braid до повного зникнення тупиків + закриття рамки
    _seal_outer_border(grid)
    _remove_dead_ends(grid)
    return grid

def add_ghost_pen(grid):
    # Створити клітку привидів у центрі з воротами
    cx, cy = GRID_W//2, GRID_H//2
    pen_w, pen_h = 7, 5
    x0 = cx - pen_w//2
    y0 = cy - pen_h//2
    for y in range(y0, y0+pen_h):
        for x in range(x0, x0+pen_w):
            if x==x0 or x==x0+pen_w-1 or y==y0 or y==y0+pen_h-1:
                grid[y][x] = WALL
            else:
                grid[y][x] = PEN
    gate_x = cx
    grid[y0][gate_x] = GATE
    return (gate_x, y0), (cx, cy)

def _repair_after_pen(grid):
    """Після вставки PEN/GATE прибрати нові тупики поза кліткою, не змінюючи контур клітки."""
    forbid = set()
    w, h = GRID_W, GRID_H
    for y in range(h):
        for x in range(w):
            if grid[y][x] in (PEN, GATE):
                forbid.add((x, y))
    # Додати стіни, що межують із PEN (контур клітки)
    for y in range(h):
        for x in range(w):
            if grid[y][x] == WALL:
                for nx, ny in neighbors4(x, y):
                    if grid[ny][nx] == PEN:
                        forbid.add((x, y))
                        break
    _remove_dead_ends(grid, forbid=forbid)

# =====================
# Ігрові сутності + плавність
# =====================
class Pacman:
    def __init__(self, grid, start):
        self.grid = grid
        self.x, self.y = start             
        self.color = YELLOW
        self.score = 0
        self.alive = True
        self.desired_dir = (0,0)            
        self.held_dir = (0,0)               
        self.last_dir = (0,0)               
        self.single_step_queue = deque()

        # Для плавного рендера:
        self.render_from = (self.x, self.y)
        self.render_to = (self.x, self.y)
        self.move_t = 1.0                   

    def request_step(self, d):
        self.single_step_queue.append(d)
        self.desired_dir = d

    def hold(self, d):
        self.held_dir = d
        self.desired_dir = d

    def release(self, d):
        if self.held_dir == d:
            self.held_dir = (0,0)

    def can_move(self, d):
        nx, ny = self.x + d[0], self.y + d[1]
        if not in_bounds(nx, ny):
            return False
        cell = self.grid[ny][nx]
        return cell in (FLOOR, GATE, PEN)

    def step(self):
        chosen = None
        if self.single_step_queue:
            d = self.single_step_queue.popleft()
            if self.can_move(d):
                chosen = d
        if chosen is None and self.held_dir != (0,0) and self.can_move(self.held_dir):
            chosen = self.held_dir
        if chosen is None and self.last_dir != (0,0) and self.can_move(self.last_dir):
            chosen = self.last_dir
        if chosen is not None:
            # для анімації: зберегти попередню точку
            self.render_from = (self.x, self.y)
            self.x += chosen[0]; self.y += chosen[1]
            self.render_to = (self.x, self.y)
            self.move_t = 0.0
            self.last_dir = chosen
        else:
            # стоїмо — анімація завершена
            self.render_from = (self.x, self.y)
            self.render_to = (self.x, self.y)
            self.move_t = 1.0

    def tick_anim(self, dt_ms):
        # оновити прогрес анімації
        self.move_t = min(1.0, self.move_t + (dt_ms / PAC_STEP_MS))

    @property
    def pos(self):
        return (self.x, self.y)

    def render_pos_px(self):
        # лерп між from/to
        fx, fy = self.render_from
        tx, ty = self.render_to
        t = self.move_t
        rx = (fx*(1-t) + tx*t) * TILE + TILE//2
        ry = (fy*(1-t) + ty*t) * TILE + TILE//2
        return int(rx), int(ry)

class Ghost:
    def __init__(self, grid, start, color):
        self.grid = grid
        self.x, self.y = start
        self.color = color
        self.role = None  # Роль буде призначена в класі Game
        self.dir = random.choice(DIR_LIST)
        self.memory_seen = None

        # Плавність
        self.render_from = (self.x, self.y)
        self.render_to = (self.x, self.y)
        self.move_t = 1.0

    def step_ai(self, difficulty_level, pac_pos, pac_dir, all_pellets):
        """Головний метод ШІ, що керує поведінкою привида."""
        target = pac_pos  # Ціль за замовчуванням - Пакмен

        # --- Рівень 2+: Логіка для випередження (Ambush) ---
        if difficulty_level >= 2 and self.role == 'AMBUSHER':
            # Цілимось на 4 клітинки вперед від Пакмена
            ax = pac_pos[0] + pac_dir[0] * 4
            ay = pac_pos[1] + pac_dir[1] * 4
            # Обмежуємо ціль межами карти
            ax = max(1, min(GRID_W - 2, ax))
            ay = max(1, min(GRID_H - 2, ay))
            target = (ax, ay)

        # --- Рівень 3+: Логіка патрулювання для "CHASER" ---
        is_patrolling = False
        if difficulty_level >= 3 and self.role == 'CHASER':
            # Якщо Пакмен далеко (дистанція > 7), переходимо в патруль
            if manhattan(self.pos, pac_pos) > 7:
                is_patrolling = True

        # --- Рівень 4+: Логіка патрулювання для "AMBUSHER" ---
        if difficulty_level >= 4 and self.role == 'AMBUSHER':
            if manhattan(self.pos, pac_pos) > 7:
                is_patrolling = True

        # --- Визначення цілі для патрулювання ---
        if is_patrolling:
            # Рівень 4+: патрулюємо по клітинках з пелетами
            if difficulty_level >= 4 and all_pellets:
                target = random.choice(list(all_pellets))
            # Рівень 3: просто випадковий рух по мапі
            else:
                lx = max(1, min(GRID_W - 2, self.x + random.choice([-4, -3, -2, 2, 3, 4])))
                ly = max(1, min(GRID_H - 2, self.y + random.choice([-4, -3, -2, 2, 3, 4])))
                target = (lx, ly)

        # --- Вибір наступного кроку до цілі ---
        step = find_path_step_bfs(self.grid, self.pos, target)
        
        # Якщо застрягли, робимо будь-який можливий хід
        if step == (0, 0):
            valid = []
            for dx, dy in DIR_LIST:
                nx, ny = self.x + dx, self.y + dy
                if in_bounds(nx, ny) and self.grid[ny][nx] != WALL:
                    valid.append((dx, dy))
            if valid:
                step = random.choice(valid)

        self.dir = step

        # для анімації:
        self.render_from = (self.x, self.y)
        self.x += step[0]
        self.y += step[1]
        self.render_to = (self.x, self.y)
        self.move_t = 0.0

    def tick_anim(self, dt_ms):
        self.move_t = min(1.0, self.move_t + (dt_ms / GHOST_STEP_MS))

    @property
    def pos(self):
        return (self.x, self.y)

    def render_pos_px(self):
        fx, fy = self.render_from
        tx, ty = self.render_to
        t = self.move_t
        rx = (fx*(1-t) + tx*t) * TILE + TILE//2
        ry = (fy*(1-t) + ty*t) * TILE + TILE//2
        return int(rx), int(ry)

# =====================
# Гра
# =====================
class Game:
    def __init__(self):
        pg.init()
        pg.display.set_caption("Pacman — Python / pygame")
        self.screen = pg.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pg.time.Clock()
        self.font = pg.font.SysFont("arial", 20)
        self.big_font = pg.font.SysFont("arial", 64, bold=True)

        self.difficulty = DEFAULT_DIFFICULTY
        self.ghost_role_swap_cooldown = 0 
        self.reset()

    def reset(self):
        # Генерація лабіринту й клітки
        self.grid = generate_maze_braid(GRID_W, GRID_H)
        self.gate_pos, pen_center = add_ghost_pen(self.grid)
        _repair_after_pen(self.grid)  # приберемо потенційні тупики після вставки PEN

        # Пелети
        self.pellets = set()
        for y in range(GRID_H):
            for x in range(GRID_W):
                if self.grid[y][x] == FLOOR:
                    self.pellets.add((x,y))
        # прибрати пелети біля клітки
        gx, gy = self.gate_pos
        for y in range(gy-2, gy+4):
            for x in range(gx-3, gx+4):
                if in_bounds(x,y) and (x,y) in self.pellets:
                    self.pellets.discard((x,y))

        # Пакмен — старт
        self.pac = Pacman(self.grid, (1, GRID_H-2))

        # Привиди — у клітці
        self.ghosts = []
        spawn_points = []
        for y in range(GRID_H):
            for x in range(GRID_W):
                if self.grid[y][x] == PEN:
                    spawn_points.append((x,y))
        random.shuffle(spawn_points)
        for i, color in enumerate(GHOST_COLORS):
            sp = spawn_points[i % len(spawn_points)]
            self.ghosts.append(Ghost(self.grid, sp, color))

        # Призначаємо ролі привидам залежно від складності
        self.assign_ghost_roles()
        self.pac_step_acc = 0
        self.ghost_step_acc = 0
        self.running = True
        self.win = False
        self.ghost_role_swap_cooldown = 0

    def assign_ghost_roles(self):
        """Призначає ролі привидам на основі поточного рівня складності."""
        num_ghosts = len(self.ghosts)
        
        if self.difficulty <= 1:
            # Усі переслідувачі
            for g in self.ghosts:
                g.role = 'CHASER'
        
        elif self.difficulty >= 2:
            # Половина - переслідувачі, половина - засідники
            for i, g in enumerate(self.ghosts):
                if i < num_ghosts // 2:
                    g.role = 'CHASER'
                else:
                    g.role = 'AMBUSHER'

    # ========= Ввід =========
    def handle_event(self, e):
        if e.type == pg.QUIT:
            self.running = False
        elif e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE:
                self.running = False
            elif e.key == pg.K_r:
                self.reset()
            elif e.key in DIFFICULTY_KEYS:
                self.difficulty = DIFFICULTY_KEYS[e.key]
                self.assign_ghost_roles() # Оновлюємо ролі при зміні складності

            elif e.key in DIRS:
                d = DIRS[e.key]
                self.pac.request_step(d)  # одноразовий крок на натискання
                self.pac.hold(d)          # також позначити як утримуваний (для автоповтору)
        elif e.type == pg.KEYUP:
            if e.key in DIRS:
                d = DIRS[e.key]
                self.pac.release(d)

    # ========= Оновлення =========
    def update(self, dt):
        # Оновлюємо таймер кулдауну для динамічної зміни ролей 
        if self.ghost_role_swap_cooldown > 0:
            self.ghost_role_swap_cooldown -= dt
            
        # Пакмен: дискретний крок за таймером
        self.pac_step_acc += dt
        while self.pac_step_acc >= PAC_STEP_MS and self.pac.alive and not self.win:
            self.pac_step_acc -= PAC_STEP_MS
            self.pac.step()
            # з’їсти пелет
            if self.pac.pos in self.pellets:
                self.pellets.remove(self.pac.pos)
                self.pac.score += PELLET_SCORE
                if not self.pellets:
                    self.win = True
        # оновити інтерполяцію
        self.pac.tick_anim(dt)

        # Привиди: також дискретні кроки
        self.ghost_step_acc += dt
        while self.ghost_step_acc >= GHOST_STEP_MS and self.pac.alive and not self.win:
            self.ghost_step_acc -= GHOST_STEP_MS
            pac_pos = self.pac.pos
            pac_dir = self.pac.last_dir

            # --- Рівень 5: Динамічна зміна ролі переслідувача З КУЛДАУНОМ ---
            # Перевіряємо, чи можна змінювати ролі
            if self.difficulty == 5 and len(self.ghosts) > 1 and self.ghost_role_swap_cooldown <= 0:
                # Знаходимо найближчого привида
                closest_ghost = min(self.ghosts, key=lambda g: manhattan(g.pos, pac_pos))
                
                # Знаходимо поточного переслідувача
                current_chaser = None
                for g in self.ghosts:
                    if g.role == 'CHASER':
                        current_chaser = g
                        break
                
                # Якщо найближчий - не переслідувач, міняємо ролі
                if current_chaser and closest_ghost is not current_chaser:
                    # Простий обмін ролями
                    current_chaser.role, closest_ghost.role = closest_ghost.role, current_chaser.role
                    # <<< ВСТАНОВЛЮЄМО КУЛДАУН ПІСЛЯ ЗМІНИ
                    self.ghost_role_swap_cooldown = 3000  # 3000 мс = 3 секунди

            # --- Оновлення ШІ для кожного привида ---
            order = list(range(len(self.ghosts)))
            random.shuffle(order)
            for idx in order:
                g = self.ghosts[idx]
                
                # --- Рівень 0: Активний лише один привид ---
                if self.difficulty == 0 and idx > 0:
                    continue # Пропускаємо всіх, крім першого
                    
                g.step_ai(self.difficulty, pac_pos, pac_dir, self.pellets)

            # Перевірка зіткнення
            for g in self.ghosts:
                if g.pos == self.pac.pos:
                    self.pac.alive = False
                    break        
    
        # Оновлюємо анімацію для ВСІХ привидів кожен кадр
        for g in self.ghosts:
            g.tick_anim(dt)

    # ========= Малювання =========
    def draw_grid(self):
        # Тло
        self.screen.fill(BLACK)
        # Стіни / підлога / ворота
        for y in range(GRID_H):
            for x in range(GRID_W):
                rect = (x*TILE, y*TILE, TILE, TILE)
                cell = self.grid[y][x]
                if cell == WALL:
                    pg.draw.rect(self.screen, BLUE, rect)
                else:
                    pg.draw.rect(self.screen, (10,10,10), rect)
                    if cell == GATE:
                        pg.draw.rect(self.screen, GREY, rect)
        # Пелети
        for (x,y) in self.pellets:
            cx, cy = x*TILE + TILE//2, y*TILE + TILE//2
            pg.draw.circle(self.screen, WHITE, (cx,cy), 3)

    def _draw_pacman(self):
        px, py = self.pac.render_pos_px()
        radius = TILE//2 - 2
        pg.draw.circle(self.screen, self.pac.color, (px,py), radius)
        # простенька «щелепа» у напрямку руху (мигтить з частотою кроку)
        dx, dy = self.pac.last_dir
        if (dx,dy) != (0,0):
            open_amt = 6  # виріз
            mouth_rect = pg.Rect(px-2, py-2, 4, 4)
            if dx<0: mouth_rect.x -= radius-open_amt
            if dx>0: mouth_rect.x += radius-open_amt
            if dy<0: mouth_rect.y -= radius-open_amt
            if dy>0: mouth_rect.y += radius-open_amt
            pg.draw.rect(self.screen, BLACK, mouth_rect)

    def _draw_ghost(self, ghost: 'Ghost'):
        gx, gy = ghost.render_pos_px()
        body_w = TILE - 4
        body_h = TILE - 2
        left = gx - body_w//2
        top  = gy - body_h//2

        # Тіло: округлений прямокутник
        rect = pg.Rect(left, top, body_w, body_h)
        pg.draw.rect(self.screen, ghost.color, rect, border_radius=body_w//3)

        # Напівкругла «голова» (додаємо коло зверху)
        head_r = body_w//2
        pg.draw.circle(self.screen, ghost.color, (gx, top+head_r//2), head_r//2 + 2)

        # «Бахрома» знизу: 4 півкола
        scallops = 4
        step = body_w // scallops
        for i in range(scallops):
            cx = left + step//2 + i*step
            cy = top + body_h - 1
            pg.draw.circle(self.screen, ghost.color, (cx, cy), step//2)

        # Очі
        eye_offset_x = body_w//5
        eye_y = top + body_h//3
        eye_r = max(3, body_w//8)
        # зіниці — у напрямку руху
        dx, dy = ghost.dir
        pupil_dx = dx * max(1, eye_r//3)
        pupil_dy = dy * max(1, eye_r//3)

        # Ліве око
        ex1, ey1 = gx - eye_offset_x, eye_y
        pg.draw.circle(self.screen, WHITE, (ex1, ey1), eye_r)
        pg.draw.circle(self.screen, BLACK, (ex1 + pupil_dx, ey1 + pupil_dy), eye_r//2)
        # Праве око
        ex2, ey2 = gx + eye_offset_x, eye_y
        pg.draw.circle(self.screen, WHITE, (ex2, ey2), eye_r)
        pg.draw.circle(self.screen, BLACK, (ex2 + pupil_dx, ey2 + pupil_dy), eye_r//2)

    def draw_entities(self):
        self._draw_pacman()
        for g in self.ghosts:
            self._draw_ghost(g)

    def draw_hud(self):
        fps = self.clock.get_fps()
        
        # Отримуємо назву складності за її числовим індексом
        difficulty_name = "Unknown" # Значення за замовчуванням на випадок помилки
        if 0 <= self.difficulty < len(DIFFICULTY_NAMES):
            difficulty_name = DIFFICULTY_NAMES[self.difficulty]

        txt = f"Score: {self.pac.score}   Pellets left: {len(self.pellets)}   Difficulty: {difficulty_name}   FPS: {fps:.0f}"
        surf = self.font.render(txt, True, WHITE)
        self.screen.blit(surf, (8, 4))

    def draw_overlay_text(self, text, color):
        overlay = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
        overlay.fill((0,0,0,180))
        self.screen.blit(overlay, (0,0))
        size = min(SCREEN_W//len(text)*2, SCREEN_H//3)
        size = max(36, min(120, size))
        font = pg.font.SysFont("arial", size, bold=True)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(SCREEN_W//2, SCREEN_H//2))
        self.screen.blit(surf, rect)
        hint = self.font.render("Натисніть R, щоб перезапустити", True, WHITE)
        hint_rect = hint.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + size))
        self.screen.blit(hint, hint_rect)

    def draw(self):
        self.draw_grid()
        self.draw_entities()
        self.draw_hud()
        if not self.pac.alive:
            self.draw_overlay_text("GAME OVER", RED)
        if self.win:
            self.draw_overlay_text("YOU WIN!", YELLOW)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            for e in pg.event.get():
                self.handle_event(e)
            self.update(dt)
            self.draw()
            pg.display.flip()
        pg.quit()


# (Функції вже вище — просто лишаємо завершальний блок нижче)

if __name__ == "__main__":
    Game().run()