
import copy
import json
import random

import streamlit as st

st.set_page_config(
    page_title="Dungeon Ascension",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SAVE_VERSION = 2
MAX_SAVE_SIZE = 1_000_000
FINAL_FLOOR = 10

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

REWARDS = {
    "vitality": ("❤️ Vitality", "+15 maximum HP and restore up to 25 HP"),
    "edge": ("⚔️ Sharpened Edge", "+3 attack power"),
    "ward": ("🛡️ Guardian Ward", "+2 defense"),
    "potion": ("🧪 Healing Potion", "+1 potion"),
}

INTENTS = {"attack", "heavy", "focus"}
STATES = {"battle", "reward", "defeat", "victory"}

BASE_SAVE_FIELDS = {
    "max_hp", "hp", "max_energy", "energy", "potions", "level", "xp",
    "gold", "attack_bonus", "defense_bonus", "floor", "wins", "enemy",
    "enemy_hp", "enemy_max_hp", "enemy_intent", "enemy_next", "guard",
    "state", "message", "log",
}

NEW_SAVE_FIELDS = {
    "damage_dealt", "damage_taken", "potions_used", "bosses_defeated",
}

SAVE_FIELDS = BASE_SAVE_FIELDS | NEW_SAVE_FIELDS

INTEGER_FIELDS = [
    "max_hp", "hp", "max_energy", "energy", "potions", "level", "xp",
    "gold", "attack_bonus", "defense_bonus", "floor", "wins",
    "enemy_hp", "enemy_max_hp", "damage_dealt", "damage_taken",
    "potions_used", "bosses_defeated",
]


# --------------------------------------------------
# GAME DATA
# --------------------------------------------------

def add_log(g, message, kind="normal"):
    g["log"].append({
        "kind": kind,
        "text": str(message)[:300],
    })
    g["log"] = g["log"][-12:]


def choose_intent(g):
    intent = random.choice(["attack", "heavy", "focus"])
    g["enemy_next"] = intent

    if intent == "attack":
        g["enemy_intent"] = f"Quick strike · {g['enemy']['attack']} damage"
    elif intent == "heavy":
        damage = int(g["enemy"]["attack"] * 1.55)
        g["enemy_intent"] = f"Heavy blow · {damage} damage"
    else:
        g["enemy_intent"] = "Gathering strength · next attack empowered"


def spawn_enemy(g):
    floor = g["floor"]
    is_boss = floor % 5 == 0

    if floor == 5:
        template = BOSSES[0]
    elif floor == 10:
        template = BOSSES[1]
    else:
        template = random.choice(ENEMIES)

    enemy = copy.deepcopy(template)

    hp_scale = 1 + (floor - 1) * (0.09 if is_boss else 0.11)
    attack_scale = 1 + (floor - 1) * 0.07

    enemy["hp"] = max(1, int(enemy["hp"] * hp_scale))
    enemy["attack"] = max(1, int(enemy["attack"] * attack_scale))

    g["enemy"] = enemy
    g["enemy_max_hp"] = enemy["hp"]
    g["enemy_hp"] = enemy["hp"]
    g["guard"] = False
    g["energy"] = g["max_energy"]
    g["state"] = "battle"

    choose_intent(g)

    label = "BOSS" if is_boss else "Enemy"
    add_log(
        g,
        f"Floor {floor}: {label} — {enemy['name']} appears!",
        "event",
    )


def new_game():
    g = {
        "max_hp": 100,
        "hp": 100,
        "max_energy": 3,
        "energy": 3,
        "potions": 2,
        "level": 1,
        "xp": 0,
        "gold": 0,
        "attack_bonus": 0,
        "defense_bonus": 0,
        "floor": 1,
        "wins": 0,
        "enemy": None,
        "enemy_hp": 0,
        "enemy_max_hp": 0,
        "enemy_intent": "",
        "enemy_next": "attack",
        "guard": False,
        "state": "battle",
        "message": "Your journey begins. Choose your move.",
        "damage_dealt": 0,
        "damage_taken": 0,
        "potions_used": 0,
        "bosses_defeated": 0,
        "log": [
            {"kind": "event", "text": "You enter the forgotten dungeon."},
            {"kind": "normal", "text": "A new threat approaches..."},
        ],
    }

    spawn_enemy(g)
    return g


# --------------------------------------------------
# PROGRESSION
# --------------------------------------------------

def gain_xp(g, amount):
    g["xp"] += amount

    while g["xp"] >= g["level"] * 35:
        g["xp"] -= g["level"] * 35
        g["level"] += 1
        g["max_hp"] += 8
        g["hp"] = min(g["max_hp"], g["hp"] + 18)
        g["attack_bonus"] += 1

        add_log(
            g,
            f"Level up! Level {g['level']}. +8 max HP and +1 attack.",
            "good",
        )


def enemy_defeated(g):
    enemy_name = g["enemy"]["name"]
    earned_xp = g["enemy"]["xp"]
    earned_gold = g["enemy"]["gold"]

    g["wins"] += 1
    g["gold"] += earned_gold
    gain_xp(g, earned_xp)

    if g["floor"] % 5 == 0:
        g["bosses_defeated"] += 1
        add_log(g, f"Boss defeated: {enemy_name}!", "event")

    add_log(
        g,
        f"{enemy_name} defeated! +{earned_xp} XP and +{earned_gold} gold.",
        "good",
    )

    if g["floor"] == FINAL_FLOOR:
        g["state"] = "victory"
        g["message"] = "You conquered the dungeon!"
        add_log(g, "The Hollow Dragon has fallen. A legendary victory!", "event")
    else:
        g["state"] = "reward"
        g["message"] = "Victory! Choose one reward before descending."

        if g["floor"] == 5:
            add_log(g, "Halfway milestone reached! The final floors await.", "event")


def take_reward(g, reward):
    if g["state"] != "reward" or reward not in REWARDS:
        return

    if reward == "vitality":
        g["max_hp"] += 15
        g["hp"] = min(g["max_hp"], g["hp"] + 25)
        add_log(g, "Vitality blessing: +15 max HP and up to 25 HP.", "good")

    elif reward == "edge":
        g["attack_bonus"] += 3
        add_log(g, "Sharpened Edge: +3 attack power.", "good")

    elif reward == "ward":
        g["defense_bonus"] += 2
        add_log(g, "Guardian Ward: +2 defense.", "good")

    elif reward == "potion":
        g["potions"] += 1
        add_log(g, "A healing potion was added to your bag.", "good")

    g["floor"] += 1
    g["message"] = f"You descend to floor {g['floor']}."

    if g["floor"] == 10:
        add_log(g, "FINAL FLOOR: The Hollow Dragon awaits!", "event")
    elif g["floor"] == 5:
        add_log(g, "BOSS FLOOR: Prepare for the Ashen Knight!", "event")

    spawn_enemy(g)


# --------------------------------------------------
# COMBAT
# --------------------------------------------------

def enemy_turn(g):
    intent = g["enemy_next"]

    if intent == "focus":
        g["enemy"]["attack"] += 3
        add_log(
            g,
            f"{g['enemy']['name']} gathers power for its next turn.",
            "bad",
        )
    else:
        if intent == "heavy":
            raw_damage = int(g["enemy"]["attack"] * 1.55)
            label = "heavy blow"
        else:
            raw_damage = g["enemy"]["attack"]
            label = "attack"

        damage = max(1, raw_damage - g["defense_bonus"])

        if g["guard"]:
            damage = max(1, damage // 2)

        g["hp"] = max(0, g["hp"] - damage)
        g["damage_taken"] += damage

        add_log(
            g,
            f"{g['enemy']['name']} uses a {label} for {damage} damage.",
            "bad",
        )

    g["guard"] = False

    if g["hp"] <= 0:
        g["state"] = "defeat"
        g["message"] = "You have fallen. The dungeon awaits another attempt."
        add_log(g, "Your adventure has ended.", "bad")
        return

    choose_intent(g)


def player_action(g, action):
    if g["state"] != "battle" or g["enemy_hp"] <= 0:
        return

    if action == "attack":
        damage = random.randint(11, 17) + g["attack_bonus"]
        g["enemy_hp"] = max(0, g["enemy_hp"] - damage)
        g["damage_dealt"] += damage
        add_log(g, f"You strike for {damage} damage.", "good")

    elif action == "heavy":
        if g["energy"] < 2:
            g["message"] = "Not enough energy for a Heavy Strike."
            return

        g["energy"] -= 2
        damage = random.randint(22, 29) + g["attack_bonus"] * 2
        g["enemy_hp"] = max(0, g["enemy_hp"] - damage)
        g["damage_dealt"] += damage
        add_log(g, f"Heavy Strike deals {damage} damage!", "good")

    elif action == "guard":
        g["guard"] = True
        add_log(g, "You raise your guard. Incoming damage is reduced.", "event")

    elif action == "heal":
        if g["potions"] <= 0:
            g["message"] = "You have no healing potions left."
            return

        if g["hp"] >= g["max_hp"]:
            g["message"] = "Your health is already full."
            return

        healed = min(30, g["max_hp"] - g["hp"])
        g["hp"] += healed
        g["potions"] -= 1
        g["potions_used"] += 1

        add_log(g, f"You use a potion and recover {healed} HP.", "good")

    else:
        return

    g["message"] = "Your turn is complete."

    if g["enemy_hp"] <= 0:
        enemy_defeated(g)
        return

    enemy_turn(g)


# --------------------------------------------------
# SAVE / LOAD
# --------------------------------------------------

def make_save(g):
    data = {
        field: copy.deepcopy(g[field])
        for field in SAVE_FIELDS
    }
    data["version"] = SAVE_VERSION
    return data


def validate_save(data):
    if not isinstance(data, dict):
        raise ValueError("The save must contain a JSON object.")

    version = data.get("version")

    if version not in (1, SAVE_VERSION):
        raise ValueError("Unsupported save version.")

    missing = BASE_SAVE_FIELDS - data.keys()
    if missing:
        raise ValueError(
            "Save is missing: " + ", ".join(sorted(missing))
        )

    # Version 1 saves are upgraded with default statistics.
    defaults = {
        "damage_dealt": 0,
        "damage_taken": 0,
        "potions_used": 0,
        "bosses_defeated": 0,
    }

    for field, default in defaults.items():
        if field not in data:
            data[field] = default

    for field in INTEGER_FIELDS:
        value = data.get(field)

        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Invalid number: {field}")

        if value < 0:
            raise ValueError(f"{field} cannot be negative.")

    if data["max_hp"] < 1 or data["hp"] > data["max_hp"]:
        raise ValueError("Invalid player health.")

    if data["max_energy"] < 1 or data["energy"] > data["max_energy"]:
        raise ValueError("Invalid energy.")

    if data["level"] < 1 or not 1 <= data["floor"] <= FINAL_FLOOR:
        raise ValueError("Invalid progression values.")

    if data["xp"] >= data["level"] * 35:
        raise ValueError("Invalid XP value.")

    if data["state"] not in STATES:
        raise ValueError("Invalid game state.")

    if data["enemy_next"] not in INTENTS:
        raise ValueError("Invalid enemy intent.")

    if not isinstance(data["enemy_intent"], str) or len(data["enemy_intent"]) > 300:
        raise ValueError("Invalid enemy intent text.")

    if not isinstance(data["message"], str) or len(data["message"]) > 500:
        raise ValueError("Invalid message.")

    if not isinstance(data["guard"], bool):
        raise ValueError("Invalid guard status.")

    enemy = data["enemy"]

    if not isinstance(enemy, dict):
        raise ValueError("Invalid enemy.")

    required_enemy_fields = {
        "name", "emoji", "hp", "attack", "xp", "gold"
    }

    if not required_enemy_fields.issubset(enemy):
        raise ValueError("Enemy data is incomplete.")

    if not isinstance(enemy["name"], str) or len(enemy["name"]) > 100:
        raise ValueError("Invalid enemy name.")

    if not isinstance(enemy["emoji"], str) or len(enemy["emoji"]) > 20:
        raise ValueError("Invalid enemy emoji.")

    for field in ("hp", "attack", "xp", "gold"):
        value = enemy[field]

        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Invalid enemy value: {field}")

    if enemy["hp"] < 1 or enemy["attack"] < 1:
        raise ValueError("Enemy must have positive health and attack.")

    if data["enemy_max_hp"] < 1:
        raise ValueError("Invalid enemy maximum health.")

    if data["enemy_hp"] > data["enemy_max_hp"]:
        raise ValueError("Invalid enemy health.")

    if data["state"] == "battle" and data["enemy_hp"] <= 0:
        raise ValueError("A battle save must have a living enemy.")

    if data["state"] == "reward" and data["enemy_hp"] != 0:
        raise ValueError("Invalid reward state.")

    if data["state"] == "defeat" and data["hp"] != 0:
        raise ValueError("Invalid defeat state.")

    if data["state"] == "victory" and data["floor"] != FINAL_FLOOR:
        raise ValueError("Victory must be on the final floor.")

    if not isinstance(data["log"], list):
        raise ValueError("Invalid journal.")

    if len(data["log"]) > 100:
        raise ValueError("Journal is too large.")

    clean_log = []

    for item in data["log"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid journal entry.")

        text = item.get("text")
        kind = item.get("kind", "normal")

        if not isinstance(text, str) or len(text) > 300:
            raise ValueError("Invalid journal text.")

        if kind not in {"event", "good", "bad", "normal"}:
            kind = "normal"

        clean_log.append({
            "kind": kind,
            "text": text,
        })

    # Build the replacement only after validation succeeds.
    restored = {}

    for field in SAVE_FIELDS:
        if field == "log":
            restored[field] = clean_log[-12:]
        else:
            restored[field] = copy.deepcopy(data[field])

    return restored


# --------------------------------------------------
# INTERFACE
# --------------------------------------------------

def health_bar(label, current, maximum):
    ratio = max(0.0, min(1.0, current / max(1, maximum)))
    st.markdown(f"**{label}: {current} / {maximum}**")
    st.progress(ratio, text=f"{int(ratio * 100)}%")


def show_journal(g):
    st.subheader("📜 Dungeon Journal")

    for entry in reversed(g["log"][-8:]):
        icon = {
            "event": "🟡",
            "good": "🟢",
            "bad": "🔴",
            "normal": "▫️",
        }.get(entry["kind"], "▫️")

        st.markdown(f"{icon} {entry['text']}")


def show_progress(g):
    st.subheader("🗺️ Dungeon Progress")

    floor = g["floor"]
    progress = floor / FINAL_FLOOR

    st.progress(
        progress,
        text=f"Floor {floor} of {FINAL_FLOOR}",
    )

    milestones = st.columns(3)

    milestones[0].metric(
        "First Boss",
        "Defeated" if g["bosses_defeated"] >= 1 else "Floor 5",
    )

    milestones[1].metric(
        "Final Boss",
        "Defeated" if g["state"] == "victory" else "Floor 10",
    )

    milestones[2].metric(
        "Bosses Defeated",
        f"{g['bosses_defeated']} / 2",
    )


def show_victory(g):
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #202d46, #49336b);
            border: 1px solid #b99aff;
            border-radius: 20px;
            padding: 35px 20px;
            text-align: center;
            margin: 15px 0 25px 0;
        ">
            <div style="font-size: 64px;">🏆</div>
            <h1 style="color: #ffffff; margin-bottom: 5px;">
                DUNGEON CONQUERED!
            </h1>
            <p style="color: #ded5ff; font-size: 18px;">
                The Hollow Dragon has fallen.
                Your legend will be remembered.
            </p>
            <div style="font-size: 35px;">⚔️ 🐉 ⚔️</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("📊 Your Adventure Results")

    a, b, c = st.columns(3)
    a.metric("Final Level", g["level"])
    b.metric("Enemies Defeated", g["wins"])
    c.metric("Gold Collected", f"🪙 {g['gold']}")

    a, b, c = st.columns(3)
    a.metric("Damage Dealt", g["damage_dealt"])
    b.metric("Damage Taken", g["damage_taken"])
    c.metric("Potions Used", g["potions_used"])

    st.success(
        f"You completed all {FINAL_FLOOR} floors "
        f"and defeated {g['bosses_defeated']} bosses!"
    )

    st.markdown("### Your Final Character")
    x, y, z = st.columns(3)
    x.metric("Maximum HP", g["max_hp"])
    y.metric("Attack Bonus", f"+{g['attack_bonus']}")
    z.metric("Defense Bonus", f"+{g['defense_bonus']}")

    st.divider()

    if st.button(
        "🔄 Begin a New Adventure",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.game = new_game()
        st.rerun()


def main():
    if "game" not in st.session_state:
        st.session_state.game = new_game()

    g = st.session_state.game

    st.markdown(
        """
        <style>
        .stApp {
            background: #0b0e17;
            color: #f3f4f8;
        }

        [data-testid="stMetric"] {
            background: #161c2b;
            border: 1px solid #364158;
            padding: 14px;
            border-radius: 12px;
        }

        div.stButton > button {
            min-height: 48px;
            border-radius: 10px;
            font-weight: 600;
            border: 1px solid #394760;
        }

        div.stButton > button:hover {
            border-color: #a78bfa;
            color: #c4b5fd;
        }

        .block-container {
            max-width: 1200px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("⚔️ DUNGEON ASCENSION")
    st.caption("TURN-BASED ROGUELIKE · DESCEND. ADAPT. ASCEND.")

    top1, top2, top3 = st.columns(3)
    top1.metric("🏰 FLOOR", f"{g['floor']} / {FINAL_FLOOR}")
    top2.metric("🏆 ENCOUNTERS WON", g["wins"])
    top3.metric("🪙 GOLD", g["gold"])

    st.divider()

    # Save and load
    with st.expander("💾 Save / Load Adventure"):
        save_bytes = json.dumps(
            make_save(g),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download Save File",
            data=save_bytes,
            file_name="dungeon_ascension_save.json",
            mime="application/json",
            use_container_width=True,
        )

        uploaded = st.file_uploader(
            "Select a previous save file",
            type=["json"],
            key="save_upload",
        )

        if st.button("📂 Load Adventure", use_container_width=True):
            if uploaded is None:
                st.warning("Choose a save file first.")
            elif uploaded.size > MAX_SAVE_SIZE:
                st.error("Save file is too large.")
            else:
                try:
                    parsed = json.loads(
                        uploaded.getvalue().decode("utf-8")
                    )

                    # Validate before replacing the current adventure.
                    restored = validate_save(parsed)

                    st.session_state.game = restored
                    st.success("Adventure loaded successfully!")
                    st.rerun()

                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    ValueError,
                    TypeError,
                    KeyError,
                ) as exc:
                    st.error(
                        "Could not load this save. "
                        "Your current adventure has been preserved. "
                        f"Details: {exc}"
                    )

    show_progress(g)

    st.divider()

    # Victory screen
    if g["state"] == "victory":
        show_victory(g)
        st.divider()
        show_journal(g)
        return

    # Player information
    st.subheader("🧙 The Wayfarer")

    a, b, c, d = st.columns(4)
    a.metric("❤️ Health", f"{g['hp']} / {g['max_hp']}")
    b.metric("✨ Level", g["level"])
    c.metric("🧪 Potions", g["potions"])
    d.metric("⚡ Energy", f"{g['energy']} / {g['max_energy']}")

    health_bar("Player HP", g["hp"], g["max_hp"])

    xp_needed = g["level"] * 35
    st.progress(
        min(1.0, g["xp"] / max(1, xp_needed)),
        text=f"XP: {g['xp']} / {xp_needed}",
    )

    x, y, z = st.columns(3)
    x.metric("Attack Bonus", f"+{g['attack_bonus']}")
    y.metric("Defense", f"+{g['defense_bonus']}")
    z.metric("Damage Dealt", g["damage_dealt"])

    st.divider()

    # Battlefield
    st.subheader("🏰 The Battlefield")

    enemy = g["enemy"]
    is_boss = g["floor"] % 5 == 0

    left, right = st.columns(2)

    with left:
        st.markdown("### 🧙 THE WAYFARER")
        st.write(f"Level {g['level']} adventurer")
        health_bar("Health", g["hp"], g["max_hp"])
        st.caption(
            f"Attack +{g['attack_bonus']} · "
            f"Defense +{g['defense_bonus']}"
        )

    with right:
        st.markdown(f"### {enemy['emoji']} {enemy['name']}")

        if is_boss:
            st.warning("⚠️ BOSS ENCOUNTER")

        health_bar(
            "Enemy HP",
            g["enemy_hp"],
            g["enemy_max_hp"],
        )
        st.caption(f"Enemy attack: {enemy['attack']}")

    # Battle actions
    if g["state"] == "battle":
        st.info(f"🔮 Enemy intent: **{g['enemy_intent']}**")
        st.markdown("### Your Turn")

        x1, x2 = st.columns(2)

        with x1:
            if st.button(
                "⚔️ Quick Attack",
                use_container_width=True,
            ):
                player_action(g, "attack")
                st.rerun()

            if st.button(
                "💥 Heavy Strike · 2 Energy",
                disabled=g["energy"] < 2,
                use_container_width=True,
            ):
                player_action(g, "heavy")
                st.rerun()

        with x2:
            if st.button(
                "🛡️ Defend",
                use_container_width=True,
            ):
                player_action(g, "guard")
                st.rerun()

            if st.button(
                "🧪 Use Potion · Restore up to 30 HP",
                disabled=(
                    g["potions"] <= 0
                    or g["hp"] >= g["max_hp"]
                ),
                use_container_width=True,
            ):
                player_action(g, "heal")
                st.rerun()

    # Rewards
    elif g["state"] == "reward":
        st.success("🏆 Victory! Choose your reward.")
        st.markdown("### 🎁 Choose One Reward")

        reward_cols = st.columns(2)

        for index, (key, (name, description)) in enumerate(
            REWARDS.items()
        ):
            with reward_cols[index % 2]:
                with st.container(border=True):
                    st.markdown(f"### {name}")
                    st.caption(description)

                    if st.button(
                        f"Choose {name}",
                        key=f"reward_{key}",
                        use_container_width=True,
                    ):
                        take_reward(g, key)
                        st.rerun()

    # Defeat
    elif g["state"] == "defeat":
        st.error("☠️ YOUR ADVENTURE HAS ENDED")

        st.markdown(
            f"""
            You reached **Floor {g['floor']}**.

            - Enemies defeated: **{g['wins']}**
            - Final level: **{g['level']}**
            - Gold collected: **{g['gold']}**
            - Bosses defeated: **{g['bosses_defeated']}**
            """
        )

        if st.button(
            "🔄 Start a New Run",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.game = new_game()
            st.rerun()

    st.divider()
    show_journal(g)

    st.caption(
        "Tip: Watch the enemy intent before choosing your move. "
        "Defending reduces the next incoming attack."
    )


if __name__ == "__main__":
    main()
