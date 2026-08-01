#!/usr/bin/env python3
"""
Дневник питания и КБЖУ
- Парсинг сообщений о еде
- Подсчет калорий
- Учет активности
- Ежедневные отчеты
"""

import sqlite3
import json
import re
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "calories.db"
FOODS_PATH = BASE_DIR / "foods.json"


def init_db():
    """Создать базу данных"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS food_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            product TEXT NOT NULL,
            weight REAL,
            unit TEXT,
            calories REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            steps INTEGER,
            pullups INTEGER,
            pushups INTEGER,
            squats INTEGER,
            calories_burned REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def load_foods() -> Dict[str, float]:
    """Загрузить базу калорийности"""
    with open(FOODS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_foods(foods: Dict[str, float]):
    """Сохранить базу калорийности"""
    with open(FOODS_PATH, 'w', encoding='utf-8') as f:
        json.dump(foods, f, ensure_ascii=False, indent=2)


def parse_food_message(message: str) -> List[Tuple[str, float, str, float]]:
    """
    Парсинг сообщения о еде.
    Возвращает: [(product, weight, unit, calories), ...]
    """
    foods = load_foods()

    # Паттерн: 200 г творог, 3 шт персик
    pattern = r'(\d+(?:\.\d+)?)\s*(г|шт|мл)?\s*([а-яё\s]+?)(?:,|$)'
    matches = re.finditer(pattern, message, re.IGNORECASE)

    entries = []

    for match in matches:
        value = float(match.group(1))
        unit = match.group(2)
        product = match.group(3).strip().lower()

        # Нормализация продукта
        product_key = find_closest_food(product, foods.keys())

        if not product_key:
            continue

        # Расчет калорий
        calories_per_100g = foods[product_key]

        # Определяем единицу измерения
        if unit == 'шт' or unit is None:
            # Для штук и без единицы — как порция 100 г
            actual_unit = 'шт'
            calories = (calories_per_100g / 100) * (value * 100)
        else:
            # Для г/мл
            actual_unit = unit
            calories = (calories_per_100g / 100) * value

        entries.append((product_key, value, actual_unit, calories))

    return entries


def find_closest_food(product: str, available: List[str]) -> Optional[str]:
    """Найти ближайший продукт по названию"""
    product = product.lower().strip()

    # Специальные правила для популярных мн.ч.
    special_rules = {
        'огурцов': 'огурец',
        'капусты': 'капуста',
        'помидор': 'помидор',
        'картофель': 'картофель',
        'яиц': 'яйцо вареное',
        'яйца': 'яйцо вареное',
        'морской капусты': 'морская капуста',
    }

    if product in special_rules:
        normalized = special_rules[product]
        if normalized in available:
            return normalized

    # Точное совпадение
    if product in available:
        return product

    # Удаляем популярные окончания для мн.ч.
    endings = ['ов', 'ев', 'ей', 'ый', 'ая', 'ее', 'ье', 'овей', 'оев']

    for ending in endings:
        if product.endswith(ending):
            base = product[:-len(ending)]

            # Частичное совпадение по базе
            for food in available:
                if base in food or food in base:
                    return food
            break

    # Частичное совпадение
    for food in available:
        if product in food or food in product:
            return food

    return None


def get_msk_date() -> date:
    """Получить текущую дату по МСК (UTC+3)"""
    msk = timezone(timedelta(hours=3))
    return datetime.now(msk).date()


def log_food(message: str, target_date: Optional[date] = None) -> List[Tuple[str, float, str, float]]:
    """Занести продукты в базу"""
    if not target_date:
        target_date = get_msk_date()

    entries = parse_food_message(message)

    if not entries:
        return []

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for product, weight, unit, calories in entries:
        c.execute("""
            INSERT INTO food_log (date, product, weight, unit, calories)
            VALUES (?, ?, ?, ?, ?)
        """, (target_date.isoformat(), product, weight, unit, calories))

    conn.commit()
    conn.close()

    return entries


def log_activity(message: str, target_date: Optional[date] = None):
    """Занести активность в базу"""
    if not target_date:
        target_date = get_msk_date()

    steps = 0
    pullups = 0
    pushups = 0
    squats = 0

    # Парсинг: "шагов 8500, подтягивания 10, отжимания 30, приседания 60"
    if 'шаг' in message:
        m = re.search(r'шаг[\w]*\s*(\d+)', message, re.IGNORECASE)
        if m:
            steps = int(m.group(1))

    if 'подтягив' in message:
        m = re.search(r'подтягив[\w]*\s*(\d+)', message, re.IGNORECASE)
        if m:
            pullups = int(m.group(1))

    if 'отжим' in message:
        m = re.search(r'отжим[\w]*\s*(\d+)', message, re.IGNORECASE)
        if m:
            pushups = int(m.group(1))

    if 'присед' in message:
        m = re.search(r'присед[\w]*\s*(\d+)', message, re.IGNORECASE)
        if m:
            squats = int(m.group(1))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO activity_log (date, steps, pullups, pushups, squats)
        VALUES (?, ?, ?, ?, ?)
    """, (target_date.isoformat(), steps, pullups, pushups, squats))

    conn.commit()
    conn.close()


def calculate_bmr(age: int, height: int, weight: int) -> float:
    """BMR по формуле Миффлина-Сан-Жеора (мужчины)"""
    return 10 * weight + 6.25 * height - 5 * age + 5


def calculate_activity_calories(steps: int, pullups: int, pushups: int, squats: int, weight: int) -> float:
    """Расчет калорий на активность"""
    # Шаги: 0.5 ккал на кг на 1000 шагов
    steps_cal = (steps / 1000) * 0.5 * weight

    # Подтягивания: ~3 ккал за повторение
    pullups_cal = pullups * 3

    # Отжимания: ~2 ккал за повторение
    pushups_cal = pushups * 2

    # Приседания: ~1.5 ккал за повторение
    squats_cal = squats * 1.5

    return steps_cal + pullups_cal + pushups_cal + squats_cal


def get_daily_summary(target_date: date, bmr_params: Dict[str, int]) -> Dict:
    """Получить статистику за день

    Args:
        target_date: дата отчета
        bmr_params: словарь с параметрами пользователя {'age': int, 'height': int, 'weight': int}

    Returns:
        словарь со статистикой
    """
    age = bmr_params.get('age', 30)
    height = bmr_params.get('height', 175)
    weight = bmr_params.get('weight', 75)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Съедено
    c.execute("""
        SELECT SUM(calories), GROUP_CONCAT(
            product || '(' ||
            CASE WHEN weight = CAST(weight AS INTEGER) THEN CAST(weight AS INTEGER)
            ELSE weight END || COALESCE(unit, 'г') || ')', ', '
        )
        FROM food_log WHERE date = ?
    """, (target_date.isoformat(),))

    row = c.fetchone()
    eaten_cal = row[0] or 0
    eaten_details = row[1] or ""

    # Активность
    c.execute("""
        SELECT steps, pullups, pushups, squats
        FROM activity_log WHERE date = ?
    """, (target_date.isoformat(),))

    row = c.fetchone()

    if row:
        steps, pullups, pushups, squats = row
    else:
        steps = pullups = pushups = squats = 0

    conn.close()

    # Расчеты
    bmr = calculate_bmr(age, height, weight)
    activity_cal = calculate_activity_calories(steps, pullups, pushups, squats, weight)
    total_burned = bmr + activity_cal
    balance = eaten_cal - total_burned

    return {
        'eaten_calories': round(eaten_cal, 0),
        'bmr': round(bmr, 0),
        'activity_calories': round(activity_cal, 0),
        'total_burned': round(total_burned, 0),
        'balance': round(balance, 0),
        'eaten_details': eaten_details,
        'activity': {
            'steps': steps,
            'pullups': pullups,
            'pushups': pushups,
            'squats': squats
        }
    }


def generate_report(target_date: date, bmr_params: Dict[str, int]) -> str:
    """Сгенерировать отчет"""
    summary = get_daily_summary(target_date, bmr_params)

    if not summary['eaten_details']:
        return None

    balance_sign = "+" if summary['balance'] >= 0 else ""
    status = "Профицит" if summary['balance'] >= 0 else "Дефицит"

    report = f"""📊 Отчет за {target_date.strftime('%d %B %Y')}:
🍽 Съедено: {int(summary['eaten_calories'])} ккал.
🏃 Потрачено (база + активность): {int(summary['total_burned'])} ккал.
📉 {status}: {balance_sign}{int(summary['balance'])} ккал.

📝 Детали: {summary['eaten_details']}
"""

    if summary['activity']['steps']:
        report += f"🚶 Шаги: {summary['activity']['steps']}\n"

    if summary['activity']['pullups']:
        report += f"💪 Подтягивания: {summary['activity']['pullups']}\n"

    if summary['activity']['pushups']:
        report += f"🔥 Отжимания: {summary['activity']['pushups']}\n"

    if summary['activity']['squats']:
        report += f"🦵 Приседания: {summary['activity']['squats']}\n"

    return report


def has_food_logs(target_date: date) -> bool:
    """Проверить, есть ли записи о еде за день"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM food_log WHERE date = ?", (target_date.isoformat(),))
    count = c.fetchone()[0]
    conn.close()
    return count > 0


def main():
    import sys

    init_db()

    if len(sys.argv) < 2:
        print("Использование:")
        print("  python tracker.py food '200 г творог, 3 персика' [--date YYYY-MM-DD] [--bmr age=XX height=XX weight=XX]")
        print("  python tracker.py activity 'шагов 8500, подтягивания 10' [--date YYYY-MM-DD]")
        print("  python tracker.py report [--date YYYY-MM-DD] [--bmr age=XX height=XX weight=XX]")
        return

    cmd = sys.argv[1]
    target_date = None
    bmr_params = {}

    # Парсинг аргументов
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--date' and i + 1 < len(sys.argv):
            target_date = date.fromisoformat(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--bmr' and i + 1 < len(sys.argv):
            # Парсинг age=XX height=XX weight=XX
            for param in sys.argv[i + 1].split():
                key, value = param.split('=')
                bmr_params[key] = int(value)
            i += 2
        else:
            i += 1

    if cmd == 'food':
        message = ' '.join(sys.argv[2:])
        # Убираем флаги из сообщения
        for flag in ['--date', '--bmr']:
            if flag in message:
                message = message.split(flag)[0].strip()

        entries = log_food(message, target_date)
        print(f"✅ Добавлено: {len(entries)} записей")

        for product, weight, unit, calories in entries:
            print(f"   {product} ({weight}{unit}) - {int(calories)} ккал")

    elif cmd == 'activity':
        message = ' '.join(sys.argv[2:])
        # Убираем флаги из сообщения
        for flag in ['--date', '--bmr']:
            if flag in message:
                message = message.split(flag)[0].strip()

        log_activity(message, target_date)
        print("✅ Активность записана")

    elif cmd == 'report':
        if not target_date:
            target_date = date.today()

        report = generate_report(target_date, bmr_params)

        if report:
            print(report)
        else:
            print(f"⚠️ Нет данных за {target_date}")

    else:
        print("Неизвестная команда")


if __name__ == '__main__':
    main()