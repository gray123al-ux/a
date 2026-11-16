DUNGEON ASCENSION
A small, turn-based roguelike combat game made with Python + Pygame.

Run:
    pip install -r requirements.txt
    python main.py

Controls:
    Mouse: choose an action / upgrade
    F5: save your adventure
    F9: load your previous adventure
    R: start a new run after defeat or victory
    Esc: save and quit

import random
import sys
import json
import os
import tempfile
import pygame

pygame.init()

WIDTH, HEIGHT = 1120, 760
FPS = 60
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dungeon Ascension | Turn-Based Roguelike")
CLOCK = pygame.time.Clock()

# Save files are stored beside main.py.
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dungeon_ascension_save.json")
SAVE_VERSION = 1

# Palette
BG = (11, 14, 23)
PANEL = (22, 28, 43)
PANEL_LIGHT = (30, 38, 57)
LINE = (54, 65, 88)
TEXT = (239, 243, 251)
MUTED = (151, 164, 187)
GOLD = (241, 198, 105)
GREEN = (103, 213, 157)
RED = (239, 104, 116)
BLUE = (117, 180, 244)
PURPLE = (184, 153, 255)
DARK = (8, 11, 18)

FONT = pygame.font.SysFont("segoeui", 18)
SMALL = pygame.font.SysFont("segoeui", 14)
TINY = pygame.font.SysFont("segoeui", 12)
MED = pygame.font.SysFont("segoeui", 23, bold=True)
BIG = pygame.font.SysFont("segoeui", 34, bold=True)
TITLE = pygame.font.SysFont("segoeui", 38, bold=True)

ENEMIES = [
    {"name": "Moss Goblin", "emoji": "👺", "hp": 34, "attack": 8, "xp": 16, "gold": 8},
    {"name": "Crypt Bat", "emoji": "🦇", "hp": 27, "attack": 10, "xp": 15, "gold": 7},
    {"name": "Stone Golem", "emoji": "🗿", "hp": 48, "attack": 7, "xp": 22, "gold": 12},
    {"name": "Shadow Wolf", "emoji": "🐺", "hp": 39, "attack": 11, "xp": 20, "gold": 10},
]
BOSSES = [
    {"name": "The Ashen Knight", "emoji": "🛡️", "hp": 92, "attack": 13, "xp": 55, "gold": 35},
    {"name": "The Hollow Dragon", "emoji": "🐉", "hp": 125, "attack": 16, "xp": 80, "gold": 50},
]

def clamp(value, low, high):
    return max(low, min(high, value))

def draw_text(surface, text, font, color, x, y, center=False):
    image = font.render(str(text), True, color)
    rect = image.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surface.blit(image, rect)
    return rect

def rounded_rect(surface, rect, color, radius=14, border=None, width=1):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surface, border, rect, width, border_radius=radius)

def draw_bar(surface, x, y, w, h, value, maximum, fill, back=(8, 11, 18)):
    pygame.draw.rect(surface, back, (x, y, w, h), border_radius=h // 2)
    ratio = clamp(value / max(1, maximum), 0, 1)
    if ratio > 0:
        pygame.draw.rect(surface, fill, (x, y, max(2, int(w * ratio)), h), border_radius=h // 2)

class Button:
    def __init__(self, rect, title, subtitle, emoji, action, accent=GOLD):
        self.rect = pygame.Rect(rect)
        self.title = title
        self.subtitle = subtitle
        self.emoji = emoji  
        self.emoji = emoji
        self.action = action
        self.accent = accent

    def draw(self, surface, enabled=True):
        mouse_over = self.rect.collidepoint(pygame.mouse.get_pos())
        fill = PANEL_LIGHT if mouse_over and enabled else PANEL
        border = self.accent if mouse_over and enabled else LINE
        rounded_rect(surface, self.rect, fill, 12, border, 2 if mouse_over else 1)
        draw_text(surface, self.emoji, MED, self.accent, self.rect.x + 15, self.rect.y + 12)
        draw_text(surface, self.title, FONT, TEXT if enabled else MUTED,
                  self.rect.x + 53, self.rect.y + 10)
        draw_text(surface, self.subtitle, TINY, MUTED,
                  self.rect.x + 53, self.rect.y + 37)

    def clicked(self, pos):
        return self.rect.collidepoint(pos)

class Game:
    SAVE_FIELDS = (
        "max_hp", "hp", "max_energy", "energy", "potions", "level", "xp",
        "gold", "attack_bonus", "defense_bonus", "floor", "wins",
        "enemy", "enemy_hp", "enemy_max_hp", "enemy_intent", "enemy_next",
        "guard", "state", "message", "log"
    )

    def __init__(self):
        self.save_status = "No save loaded"
        self.new_run()

    def save_game(self, announce=True):
        """Write a complete snapshot safely using an atomic file replacement."""
        data = {"version": SAVE_VERSION}
        for field in self.SAVE_FIELDS:
            value = getattr(self, field)
            if field == "log":
                value = [[kind, line] for kind, line in value]
            data[field] = value

        folder = os.path.dirname(SAVE_PATH)
        os.makedirs(folder, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=folder, delete=False
            ) as temp:
                json.dump(data, temp, ensure_ascii=False, indent=2)
                temp_path = temp.name
            os.replace(temp_path, SAVE_PATH)
            self.save_status = "Saved"
            if announce:
                self.add_log("Adventure saved.", "event")
        except (OSError, TypeError, ValueError) as exc:
            self.save_status = "Save failed"
            print(f"[Save error] {exc}")
            if announce:
                self.add_log("Could not save the adventure. Check file permissions.", "bad")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def load_game(self, announce=True):
        """Load a validated snapshot. Invalid files are left untouched."""
        if not os.path.exists(SAVE_PATH):
            self.save_status = "No save file"
            if announce:
                self.add_log("No saved adventure was found.", "bad")
            return False

        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as file:
              data = json.load(file)

            if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
                raise ValueError("Unsupported or invalid save version")

            missing = [field for field in self.SAVE_FIELDS if field not in data]
            if missing:
                raise ValueError("Save is missing required game data")

            # Validate basic types and ranges before changing the current game.
            integer_fields = (
                "max_hp", "hp", "max_energy", "energy", "potions", "level",
                "xp", "gold", "attack_bonus", "defense_bonus", "floor", "wins",
                "enemy_hp", "enemy_max_hp"
            )
            for field in integer_fields:
                if not isinstance(data[field], int) or isinstance(data[field], bool):
                    raise ValueError(f"Invalid value: {field}")
            if data["max_hp"] < 1 or not 0 <= data["hp"] <= data["max_hp"]:
                raise ValueError("Invalid player health")
            if data["floor"] < 1 or data["level"] < 1 or data["potions"] < 0:
                raise ValueError("Invalid player progression")
            if data["state"] not in ("battle", "reward", "defeat", "victory"):
                raise ValueError("Invalid game state")
            if data["enemy"] is not None and not isinstance(data["enemy"], dict):
                raise ValueError("Invalid enemy data")
            if not isinstance(data["log"], list):
                raise ValueError("Invalid journal data")

            restored = {}
            for field in self.SAVE_FIELDS:
                value = data[field]
                if field == "log":
                    value = [(str(item[0]), str(item[1])) for item in value
                             if isinstance(item, list) and len(item) == 2]
                    value = value[-7:]
                elif field == "enemy" and value is not None:
                    value = dict(value)
                restored[field] = value

            for field, value in restored.items():
                setattr(self, field, value)

            # Older or malformed snapshots may not contain a usable enemy intent.
            if self.state == "battle":
                if self.enemy is None:
                    raise ValueError("Saved battle has no enemy")
                if not hasattr(self, "enemy_next") or self.enemy_next not in ("attack", "heavy", "focus"):
                    self.enemy_next = "attack"

            self.save_status = "Loaded"
            if announce:
                self.add_log("Saved adventure loaded. Welcome back!", "good")
            return True

        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            self.save_status = "Load failed"
            print(f"[Load error] {exc}")
            if announce:
                self.add_log("Save file is damaged or incompatible; current run was kept.", "bad")
            return False

    def new_run(self):
        self.max_hp = 100
        self.hp = 100
        self.max_energy = 3
        self.energy = 3
        self.potions = 2
        self.level = 1
        self.xp = 0
        self.gold = 0
        self.attack_bonus = 0
        self.defense_bonus = 0
        self.floor = 1
        self.wins = 0
        self.enemy = None
        self.enemy_hp = 0
        self.enemy_max_hp = 0
        self.enemy_intent = "Preparing an attack"
        self.enemy_next = "attack"
        self.guard = False
        self.state = "battle"
        self.message = "Your journey begins. Choose your move."
        self.log = [
            ("event", "You enter the forgotten dungeon."),
            ("normal", "A new threat approaches..."),
        ]
        self.spawn_enemy()
        self.save_game(announce=False)

    def add_log(self, text, kind="normal"):
        self.log.append((kind, text))
        self.log = self.log[-7:]

    def spawn_enemy(self):
        is_boss = self.floor % 5 == 0
        source = BOSSES if is_boss else ENEMIES
        base = randscale = 1 + (self.floor - 1) * (0.11 if not is_boss else 0.09)
        base["hp"] = int(base["hp"] * scale)
        base["attack"] = int(base["attack"] * (1 + (self.floor - 1) * 0.07))
        self.enemy = base
        self.enemy_max_hp = base["hp"]
        self.enemy_hp = base["hp"]
        self.guard = False
        self.energy = self.max_energy
        self.choose_intent()
        self.state = "battle"
        self.add_log(f"Floor {self.floor}: {base['name']} appears!", "event")

    def choose_intent(self):
        choices = ["attack", "heavy", "focus"]
        intent = random.choice(choices)
        if intent == "attack":
            self.enemy_intent = f"Quick strike · {self.enemy['attack']} damage"
        elif intent == "heavy":
            self.enemy_intent = f"Heavy blow · {int(self.enemy['attack'] * 1.55)} damage"
        else:
            self.enemy_intent = "Gathering strength · next attack empowered"
        self.enemy_next = intent

    def gain_xp(self, amount):
        self.xp += amount
        while self.xp >= self.level * 35:
            self.xp -= self.level * 35
            self.level += 1
            self.max_hp += 8
            self.hp = min(self.max_hp, self.hp + 18)
            self.attack_bonus += 1
            self.add_log(f"Level up! You are now level {self.level}. +8 max HP, +1 attack.", "good")

    def player_action(self, action):
        if self.state != "battle" or self.enemy_hp <= 0:
            return
        if action == "attack":
            damage = random.randint(11, 17) + self.attack_bonus
            self.enemy_hp -= damage
            self.add_log(f"You strike for {damage} damage.", "good")
        elif action == "heavy":
            if self.energy < 2:
                self.message = "Not enough energy for a Heavy Strike."
                return
            self.energy -= 2
            damage = random.randint(22, 29) + self.attack_bonus * 2
            self.enemy_hp -= damage
            self.add_log(f"Heavy Strike deals {damage} damage!", "good")
        elif action == "guard":
            self.guard = True
            self.add_log("You raise your guard. Incoming damage is reduced.", "event")
        elif action == "heal":
            if self.potions <= 0:
                self.message = "You have no healing potions left."
                return
            if self.hp >= self.max_hp:
                self.message = "Your health is already full."
                return
            healed = min(30, self.max_hp - self.hp)
            self.hp += healed
            self.potions -= 1
            self.add_log(f"You use a potion and recover {healed} HP.", "good")
        else:
            return

        if self.enemy_hp <= 0:
            self.enemy_defeated()
            return
        self.enemy_turn()om.choice(source).copy()
      self.save_game(announce=False)

    def enemy_turn(self):
        intent = self.enemy_next
        if intent == "focus":
            self.enemy["attack"] += 3
            self.add_log(f"{self.enemy['name']} gathers power for its next turn.", "bad")
        else:
            raw = self.enemy["attack"] if intent == "attack" else int(self.enemy["attack"] * 1.55)
            damage = max(1, raw - self.defense_bonus)
            if self.guard:
                damage = max(1, damage // 2)
            self.hp -= damage
            label = "heavy blow" if intent == "heavy" else "attack"
            self.add_log(f"{self.enemy['name']} uses a {label} for {damage} damage.", "bad")
        self.guard = False
        if self.hp <= 0:
            self.hp = 0
            self.state = "defeat"
            self.add_log("You have fallen. The dungeon awaits another attempt.", "bad")
            self.save_game(announce=False)
            return
        self.choose_intent()
        self.save_game(announce=False)

    def enemy_defeated(self):
        self.wins += 1
        earned_xp = self.enemy["xp"]
        earned_gold = self.enemy["gold"]
        self.gold += earned_gold
        self.gain_xp(earned_xp)
        self.add_log(f"{self.enemy['name']} defeated! +{earned_xp} XP, +{earned_gold} gold.", "good")
        if self.floor % 5 == 0 and self.floor >= 10:
            self.state = "victory"
            self.add_log("You conquered the dungeon. A legendary victory!", "event")
        else:
            self.state = "reward"
            self.message = "Victory! Choose one reward before descending."
        self.save_game(announce=False)

    def take_reward(self, reward):
        if self.state != "reward":
            return
        if reward == "vitality":
            self.max_hp += 15
            self.hp = min(self.max_hp, self.hp + 25)
            self.add_log("Reward: Vitality blessing. +15 max HP and +25 HP.", "good")
        elif reward == "edge":
            self.attack_bonus += 3
            self.add_log("Reward: Sharpened edge. Your attacks deal more damage.", "good")
        elif reward == "ward":
            self.defense_bonus += 2
            self.add_log("Reward: Guardian ward. Incoming damage is reduced.", "good")
        elif reward == "potion":
            self.potions += 1
            self.add_log("Reward: Healing potion added to your bag.", "good")
        self.floor += 1
        self.spawn_enemy()
        self.save_game(announce=False)

game = Game()

# Layout
ACTION_BUTTONS = [
    Button((48, 478, 235, 68), "Quick Attack", "No energy cost", "⚔", "attack", GOLD),
    Button((293, 478, 235, 68), "Heavy Strike", "Costs 2 energy", "💥", "heavy", RED),
    Button((538, 478, 235, 68), "Defend", "Reduce next hit", "🛡", "guard", BLUE),
    Button((783, 478, 235, 68), "Use Potion", "Restore up to 30 HP", "🧪", "heal", GREEN),
]
REWARDS = [
    Button((75, 390, 225, 100), "Vitality", "+15 max HP, heal 25", "❤️", "vitality", GREEN),
    Button((325, 390, 225, 100), "Sharpened Edge", "+3 attack power", "⚔", "edge", GOLD),
    Button((575, 390, 225, 100), "Guardian Ward", "+2 defense", "🛡", "ward", BLUE),
    Button((825, 390, 225, 100), "Healing Potion", "+1 potion", "🧪", "potion", PURPLE),
]

def draw_panel(surface, rect, title=None):
    rounded_rect(surface, rect, PANEL, 16, LINE, 1)
    if title:
        draw_text(surface, title.upper(), SMALL, MUTED, rect.x + 18, rect.y + 15)

def draw_game():
    SCREEN.fill(BG)
    # soft decorative glows
    pygame.draw.circle(SCREEN, (24, 31, 52), (WIDTH // 2, -190), 430)

    # Header
    draw_text(SCREEN, "✦", BIG, GOLD, 35, 25)
    draw_text(SCREEN, "DUNGEON ASCENSION", TITLE, TEXT, 76, 22)
    draw_text(SCREEN, "TURN-BASED ROGUELIKE  ·  DESCEND. ADAPT. ASCEND.", TINY, MUTED, 79, 67)
    # Save / load controls
    save_hover = pygame.Rect(785, 31, 82, 36).collidepoint(pygame.mouse.get_pos())
    load_hover = pygame.Rect(875, 31, 82, 36).collidepoint(pygame.mouse.get_pos())
    rounded_rect(SCREEN, (785, 31, 82, 36), PANEL_LIGHT if save_hover else PANEL,
                 10, GOLD if save_hover else LINE)
    rounded_rect(SCREEN, (875, 31, 82, 36), PANEL_LIGHT if load_hover else PANEL,
                 10, BLUE if load_hover else LINE
                 draw_text(SCREEN, "SAVE", TINY, GOLD, 826, 49, True)
    draw_text(SCREEN, "LOAD", TINY, BLUE, 916, 49, True)
    rounded_rect(SCREEN, (970, 31, 114, 36), (34, 31, 28), 18, (111, 88, 49))
    draw_text(SCREEN, f"FLOOR {game.floor}", SMALL, GOLD, 1027, 49, True)
    draw_text(SCREEN, f"F5 Save  ·  F9 Load  ·  {game.save_status}",
              TINY, MUTED, 785, 76)

    # Stats row
    stats = [
        ("HEALTH", f"{game.hp}/{game.max_hp}", RED),
        ("LEVEL", str(game.level), PURPLE),
        ("GOLD", str(game.gold), GOLD),
        ("POTIONS", str(game.potions), GREEN),
    ]
    for i, (label, value, color) in enumerate(stats):
        x = 36 + i * 267
        draw_panel(SCREEN, (36 + i * 267, 98, 250, 67))
        draw_text(SCREEN, label, TINY, MUTED, x + 15, 109)
        draw_text(SCREEN, value, MED, color, x + 15, 128)

    # Main arena
    draw_panel(SCREEN, (36, 181, 748, 405), "THE BATTLEFIELD")
    rounded_rect(SCREEN, (54, 216, 712, 354), (15, 20, 32), 14, (43, 53, 74))
    draw_text(SCREEN, f"FLOOR {game.floor}  /  ENCOUNTER {game.wins + 1}", TINY, GOLD, 75, 234)
    # decorative floor
    pygame.draw.ellipse(SCREEN, (37, 43, 57), (130, 467, 540, 76))
    pygame.draw.ellipse(SCREEN, (53, 58, 71), (170, 478, 460, 53), 2)

    # Player
    draw_text(SCREEN, "🧙", BIG, TEXT, 235, 313, True)
    draw_text(SCREEN, "THE WAYFARER", SMALL, TEXT, 235, 390, True)
    draw_text(SCREEN, f"Level {game.level} · +{game.attack_bonus} ATK · {game.defense_bonus} DEF",
              TINY, MUTED, 235, 414, True)
    draw_bar(SCREEN, 135, 441, 200, 11, game.hp, game.max_hp, GREEN)
    draw_text(SCREEN, f"{game.hp} / {game.max_hp} HP", TINY, MUTED, 235, 456, True)

    # Enemy
    enemy_emoji = game.enemy["emoji"] if game.enemy else "👾"
    draw_text(SCREEN, enemy_emoji, BIG, TEXT, 572, 313, True)
    draw_text(SCREEN, game.enemy["name"].upper() if game.enemy else "UNKNOWN", SMALL, TEXT, 572, 390, True)
    draw_text(SCREEN, f"THREAT · {game.enemy['attack']} ATK", TINY, MUTED, 572, 414, True)
    draw_bar(SCREEN, 472, 441, 200, 11, game.enemy_hp, game.enemy_max_hp, RED)
    draw_text(SCREEN, f"{max(0, game.enemy_hp)} / {game.enemy_max_hp} HP", TINY, MUTED, 572, 456, True)

    # Intent strip
    if game.state == "battle":
        rounded_rect(SCREEN, (224, 520, 372, 39), (47, 39, 27), 10, (111, 88, 49))
        draw_text(SCREEN, "ENEMY INTENT  ·  " + game.enemy_intent, TINY, GOLD, 410, 539, True)
    elif game.state == "reward":
        rounded_rect(SCREEN, (224, 520, 372, 39), (28, 52, 42), 10, (61, 119, 88))
        draw_text(SCREEN, "VICTORY  ·  CHOOSE A REWARD", TINY, GREEN, 410, 539, True)
    elif game.state in ("defeat", "victory"):
        rounded_rect(SCREEN, (224, 520, 372, 39), (53, 30, 37), 10, (132, 64, 76))
        draw_text(SCREEN, "RUN ENDED  ·  PRESS R TO PLAY AGAIN", TINY, RED, 410, 539, True)

    # Actions
    draw_panel(SCREEN, (36, 602, 748, 126), "YOUR TURN")
    if game.state == "battle":
        for button in ACTION_BUTTONS:
            enabled = not (button.action == "heavy" and game.energy < 2)
            enabled = enabled and not (button.action == "heal" and (game.potions <= 0 or game.hp == game.max_hp))
            button.draw(SCREEN, enabled)
    else:
        label = "Choose a reward on the right." if game.state == "reward" else "Press R to begin a new run."
        draw_text(SCREEN, label, FONT, MUTED, 410, 665, True)

    # Side panels
    draw_panel(SCREEN, (802, 181, 282, 247), "HERO STATUS")
    draw_text(SCREEN, "✦  THE WAYFARER", MED, TEXT, 822, 219)
    draw_text(SCREEN, f"Level {game.level}", SMALL, PURPLE, 822, 253)
    xp_needed = game.level * 35
    draw_bar(SCREEN, 822, 279, 242, 8, game.xp, xp_needed, PURPLE)
    draw_text(SCREEN, f"XP  {game.xp} / {xp_needed}", TINY, MUTED, 822, 292)
    draw_text(SCREEN, f"⚔  Attack bonus: +{game.attack_bonus}", SMALL, GOLD, 822, 328)
    draw_text(SCREEN, f"🛡  Defense: +{game.defense_bonus}", SMALL, BLUE, 822, 355)
    draw_text(SCREEN, f"⚡  Energy: {game.energy} / {game.max_energy}", SMALL, GREEN, 822, 382)
    draw_panel(SCREEN, (802, 445, 282, 283), "DUNGEON JOURNAL")
    y = 481for kind, line in game.log[-7:]:
        color = GOLD if kind == "event" else GREEN if kind == "good" else RED if kind == "bad" else MUTED
        # Wrap journal lines to fit
        words = line.split()
        current = ""
        chunks = []
        for word in words:
            trial = (current + " " + word).strip()
            if SMALL.size(trial)[0] > 242 and current:
                chunks.append(current)
                current = word
            else:
                current = trial
        if current:
            chunks.append(current)
        for chunk in chunks:
            draw_text(SCREEN, "› " + chunk, TINY, color, 822, y)
            y += 20
            if y > 704:
                break
        if y > 704:
            break

    # Reward overlay panel
    if game.state == "reward":
        rounded_rect(SCREEN, (50, 250, 1020, 270), (14, 19, 31), 18, GOLD, 2)
        draw_text(SCREEN, "VICTORY — CLAIM YOUR REWARD", BIG, GOLD, WIDTH // 2, 292, True)
        draw_text(SCREEN, "Choose one upgrade to prepare for the next floor.", SMALL, MUTED, WIDTH // 2, 334, True)
        for button in REWARDS:
            button.draw(SCREEN)
    elif game.state in ("defeat", "victory"):
        rounded_rect(SCREEN, (245, 260, 630, 230), (14, 19, 31), 18, RED if game.state == "defeat" else GOLD, 2)
        title = "YOUR RUN HAS ENDED" if game.state == "defeat" else "DUNGEON CONQUERED!"
        draw_text(SCREEN, title, BIG, RED if game.state == "defeat" else GOLD, WIDTH // 2, 305, True)
        draw_text(SCREEN, f"Floors cleared: {game.floor - 1}     Enemies defeated: {game.wins}", FONT, TEXT, WIDTH // 2, 354, True)
        draw_text(SCREEN, f"Final level: {game.level}     Gold collected: {game.gold}", SMALL, MUTED, WIDTH // 2, 388, True)
        draw_text(SCREEN, "Press R to start a fresh run", SMALL, GOLD, WIDTH // 2, 437, True)

    draw_text(SCREEN, "TIP: Watch the enemy intent before choosing your move.", TINY, MUTED, 39, 738)
    pygame.display.flip()

def handle_click(pos):
    if pygame.Rect(785, 31, 82, 36).collidepoint(pos):
        game.save_game()
        return
    if pygame.Rect(875, 31, 82, 36).collidepoint(pos):
        game.load_game()
        return

    if game.state == "battle":
        for button in ACTION_BUTTONS:
            if button.clicked(pos):
                game.player_action(button.action)
                return
    elif game.state == "reward":
        for button in REWARDS:
            if button.clicked(pos):
                game.take_reward(button.action)
                return

def main():
    running = True
    while running:
        CLOCK.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F5:
                    game.save_game()
                elif event.key == pygame.K_F9:
                    game.load_game()
                elif event.key == pygame.K_r and game.state in ("defeat", "victory"):
                    game.new_run()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                handle_click(event.pos)
        draw_game()
    game.save_game(announce=False)
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
