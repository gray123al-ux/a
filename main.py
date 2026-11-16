import pygame
import sys
import copy
import json
import random

import streamlit as st

st.set_page_config(
    page_title="Dungeon Ascension",
    page_icon="⚔️",
    layout="wide",
)

SAVE_VERSION = 1

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
    "vitality": ("❤️ Vitality", "+15 maximum HP and restore 25 HP"),
    "edge": ("⚔️ Sharpened Edge", "+3 attack power"),
    "ward": ("🛡️ Guardian Ward", "+2 defense"),
    "potion": ("🧪 Healing Potion", "+1 potion"),
}

SAVE_FIELDS = {
    "max_hp", "hp", "max_energy", "energy", "potions", "level", "xp",
    "gold", "attack_bonus", "defense_bonus", "floor", "wins", "enemy",
    "enemy_hp", "enemy_max_hp", "enemy_intent", "enemy_next", "guard",
    "state", "message", "log",
}

INTENTS = {"attack", "heavy", "focus"}
STATES = {"battle", "reward", "defeat", "victory"}


def add_log(g, message, kind="normal"):
    g["log"].append({"kind": kind, "text": str(message)})
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
    is_boss = g["floor"] % 5 == 0
    template = random.choice(BOSSES if is_boss else ENEMIES)
    enemy = copy.deepcopy(template)

    hp_scale = 1 + (g["floor"] - 1) * (0.09 if is_boss else 0.11)
    attack_scale = 1 + (g["floor"] - 1) * 0.07

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
    add_log(g, f"Floor {g['floor']}: {label} — {enemy['name']} appears!", "event")


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
        "log": [
            {"kind": "event", "text": "You enter the forgotten dungeon."},
            {"kind": "normal", "text": "A new threat approaches..."},
        ],
    }
    spawn_enemy(g)
    return g


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

    add_log(
        g,
        f"{enemy_name} defeated! +{earned_xp} XP and +{earned_gold} gold.",
        "good",
    )

    if g["floor"] == 10:
        g["state"] = "victory"
        g["message"] = "You conquered the dungeon!"
        add_log(g, "The final boss has fallen. A legendary victory!", "event")
    else:
        g["state"] = "reward"
        g["message"] = "Victory! Choose one reward before descending."


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
        add_log(g, f"You strike for {damage} damage.", "good")

    elif action == "heavy":
        if g["energy"] < 2:
            g["message"] = "Not enough energy for a Heavy Strike."
            return

        g["energy"] -= 2
        damage = random.randint(22, 29) + g["attack_bonus"] * 2
        g["enemy_hp"] = max(0, g["enemy_hp"] - damage)
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
        add_log(g, f"You use a potion and recover {healed} HP.", "good")

    else:
        return

    g["message"] = "Your turn is complete."

    if g["enemy_hp"] <= 0:
        enemy_defeated(g)
        return

    enemy_turn(g)


def take_reward(g, reward):
    if g["state"] != "reward":
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
    spawn_enemy(g)


def make_save(g):
    data = {field: copy.deepcopy(g[field]) for field in SAVE_FIELDS}
    data["version"] = SAVE_VERSION
    return data


def validate_save(data):
    if not isinstance(data, dict):
        raise ValueError("The save must contain a JSON object.")

    if data.get("version") != SAVE_VERSION:
        raise ValueError("Unsupported save version.")

    missing = SAVE_FIELDS - data.keys()
    if missing:
        raise ValueError("Save is missing: " + ", ".join(sorted(missing)))

    integer_fields = [
        "max_hp", "hp", "max_energy", "energy", "potions", "level", "xp",
        "gold", "attack_bonus", "defense_bonus", "floor", "wins",
        "enemy_hp", "enemy_max_hp",
    ]

    for field in integer_fields:
        value = data[field]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Invalid number: {field}")

    if data["max_hp"] < 1 or not 0 <= data["hp"] <= data["max_hp"]:
        raise ValueError("Invalid player health.")
    if data["max_energy"] < 1 or not 0 <= data["energy"] <= data["max_energy"]:
        raise ValueError("Invalid energy.")
    if data["potions"] < 0 or data["level"] < 1 or data["floor"] < 1:
        raise ValueError("Invalid progression values.")
    if data["xp"] < 0 or data["gold"] < 0 or data["wins"] < 0:
        raise ValueError("XP, gold, and wins cannot be negative.")
    if data["attack_bonus"] < 0 or data["defense_bonus"] < 0:
        raise ValueError("Invalid character upgrades.")
    if data["state"] not in STATES:
        raise ValueError("Invalid game state.")
    if data["enemy_next"] not in INTENTS:
        raise ValueError("Invalid enemy intent.")
    if not isinstance(data["enemy_intent"], str):
        raise ValueError("Invalid enemy intent text.")
    if not isinstance(data["message"], str):
        raise ValueError("Invalid message.")
    if not isinstance(data["guard"], bool):
        raise ValueError("Invalid guard status.")

    enemy = data["enemy"]
    if not isinstance(enemy, dict):
        raise ValueError("Invalid enemy.")

    required_enemy_fields = {"name", "emoji", "hp", "attack", "xp", "gold"}
    if not required_enemy_fields.issubset(enemy):
        raise ValueError("Enemy data is incomplete.")

    for field in ("hp", "attack", "xp", "gold"):
        value = enemy[field]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Invalid enemy value: {field}")

    if not isinstance(enemy["name"], str) or not isinstance(enemy["emoji"], str):
        raise ValueError("Invalid enemy name.")

    if data["enemy_max_hp"] < 1:
        raise ValueError("Invalid enemy maximum health.")
    if not 0 <= data["enemy_hp"] <= data["enemy_max_hp"]:
        raise ValueError("Invalid enemy health.")
    if not isinstance(data["log"], list):
        raise ValueError("Invalid journal.")

    clean_log = []
    for item in data["log"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid journal entry.")
        if not isinstance(item.get("text"), str):
            raise ValueError("Invalid journal text.")
        kind = item.get("kind", "normal")
        if kind not in {"event", "good", "bad", "normal"}:
            kind = "normal"
        clean_log.append({"kind": kind, "text": item["text"]})

    if data["state"] == "battle" and data["enemy_hp"] <= 0:
        raise ValueError("A battle save must have a living enemy.")

    # Build a complete replacement only after every field has been checked.
    restored = {field: copy.deepcopy(data[field]) for field in SAVE_FIELDS}
    restored["log"] = clean_log[-12:]
    return restored


def health_bar(label, current, maximum, color):
    ratio = max(0.0, min(1.0, current / max(1, maximum)))
    st.markdown(f"**{label}: {current} / {maximum}**")
    st.progress(ratio, text=f"{int(ratio * 100)}%")


def show_journal(g):
    st.subheader("📜 Dungeon Journal")
    for entry in reversed(g["log"][-8:]):
        kind = entry["kind"]
        color = {
            "event": "🟡",
            "good": "🟢",
            "bad": "🔴",
            "normal": "▫️",
        }.get(kind, "▫️")
        st.markdown(f"{color} {entry['text']}")


def main():
    if "game" not in st.session_state:
        st.session_state.game = new_game()

    g = st.session_state.game

    st.markdown(
        """
        <style>
        .stApp {background: #0b0e17;}
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
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("⚔️ DUNGEON ASCENSION")
    st.caption("TURN-BASED ROGUELIKE · DESCEND. ADAPT. ASCEND.")

    top1, top2, top3 = st.columns([2, 2, 1])
    with top1:
        st.metric("FLOOR", g["floor"])
    with top2:
        st.metric("ENCOUNTERS WON", g["wins"])
    with top3:
        st.metric("GOLD", f"🪙 {g['gold']}")

    st.divider()

    # Save and load controls. A failed load never replaces the current game.
    with st.expander("💾 Save / Load Adventure", expanded=False):
        save_bytes = json.dumps(
            make_save(g), ensure_ascii=False, indent=2
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download save file",
            data=save_bytes,
            file_name="dungeon_ascension_save.json",
            mime="application/json",
            use_container_width=True,
        )

        uploaded = st.file_uploader(
            "Load a previous adventure (.json)",
            type=["json"],
            key="save_upload",
        )

        if st.button("Load uploaded adventure", use_container_width=True):
            if uploaded is None:
                st.warning("Choose a save file first.")
            else:
                try:
                    parsed = json.loads(uploaded.getvalue().decode("utf-8"))
                    restored = validate_save(parsed)
                    st.session_state.game = restored
                    st.success("Adventure loaded successfully.")
                    st.rerun()
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                    st.error(f"Could not load save. Your current run was kept. Details: {exc}")

    st.subheader("🧙 The Wayfarer")
    a, b, c, d = st.columns(4)
    a.metric("❤️ Health", f"{g['hp']} / {g['max_hp']}")
    b.metric("✨ Level", g["level"])
    c.metric("🧪 Potions", g["potions"])
    d.metric("⚡ Energy", f"{g['energy']} / {g['max_energy']}")

    health_bar("Player HP", g["hp"], g["max_hp"], "green")
    xp_needed = g["level"] * 35
    st.progress(
        min(1.0, g["xp"] / max(1, xp_needed)),
        text=f"XP: {g['xp']} / {xp_needed}",
    )

    s1, s2, s3 = st.columns(3)
    s1.metric("Attack bonus", f"+{g['attack_bonus']}")
    s2.metric("Defense", f"+{g['defense_bonus']}")
    s3.metric("Enemies defeated", g["wins"])

    st.divider()
    st.subheader("🏰 The Battlefield")

    enemy = g["enemy"]
    is_boss = g["floor"] % 5 == 0

    left, right = st.columns(2)
    with left:
        st.markdown("### 🧙 THE WAYFARER")
        st.write(f"Level {g['level']} adventurer")
        health_bar("Health", g["hp"], g["max_hp"], "green")
        st.caption(f"Attack +{g['attack_bonus']} · Defense +{g['defense_bonus']}")

    with right:
        st.markdown(f"### {enemy['emoji']} {enemy['name']}")
        if is_boss:
            st.warning("BOSS ENCOUNTER")
        health_bar("Enemy HP", g["enemy_hp"], g["enemy_max_hp"], "red")
        st.caption(f"Enemy attack: {enemy['attack']}")

    if g["state"] == "battle":
        st.info(f"🔮 Enemy intent: **{g['enemy_intent']}**")
        st.markdown("### Your Turn")

        x1, x2 = st.columns(2)
        with x1:
            if st.button("⚔️ Quick Attack", use_container_width=True):
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
            if st.button("🛡️ Defend", use_container_width=True):
                player_action(g, "guard")
                st.rerun()
            if st.button(
                "🧪 Use Potion · Restore up to 30 HP",
                disabled=(g["potions"] <= 0 or g["hp"] >= g["max_hp"]),
                use_container_width=True,
            ):
                player_action(g, "heal")
                st.rerun()

    elif g["state"] == "reward":
        st.success("🏆 Victory! Choose one reward before descending.")
        st.markdown("### Choose Your Reward")

        reward_cols = st.columns(2)
        for index, (key, (name, description)) in enumerate(REWARDS.items()):
            with reward_cols[index % 2]:
                st.markdown(f"**{name}**")
                st.caption(description)
                if st.button(
                    f"Choose {name}",
                    key=f"reward_{key}",
                    use_container_width=True,
                ):
                    take_reward(g, key)
                    st.rerun()

    elif g["state"] == "defeat":
        st.error("☠️ YOUR RUN HAS ENDED")
        st.write(
            f"Floors reached: {g['floor']} · "
            f"Enemies defeated: {g['wins']} · "
            f"Final level: {g['level']}"
        )
        if st.button("🔄 Start a New Run", use_container_width=True):
            st.session_state.game = new_game()
            st.rerun()

    elif g["state"] == "victory":
        st.success("🏆 DUNGEON CONQUERED!")
        st.write(
            f"You defeated the final boss! "
            f"Enemies defeated: {g['wins']} · "
            f"Final level: {g['level']} · Gold: {g['gold']}"
        )
        if st.button("🔄 Start a New Run", use_container_width=True):
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
