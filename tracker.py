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
            situps INTEGER,
            calories_burned REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def load_foods() -> Dict[str, Dict[str, float]]:
    """Загрузить базу калорийности"""
    with open(FOODS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_foods(foods: Dict[str, Dict[str, float]]):
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
        food_data = foods[product_key]
        calories_per_100g = food_data['calories']

        # Определяем вес в граммах
        if unit == 'шт' or unit is None:
            # Для штук и без единицы — используем grams_per_piece если есть
            if 'grams_per_piece' in food_data:
                weight_grams = value * food_data['grams_per_piece']
                actual_unit = 'шт'
            else:
                # Если нет коэффициента, считаем как 100г за штуку (старое поведение)
                weight_grams = value * 100
                actual_unit = 'шт'
        else:
            # Для г/мл — указанный вес
            weight_grams = value
            actual_unit = unit

        calories = (calories_per_100g / 100) * weight_grams
        entries.append((product_key, value, actual_unit, calories))

    return entries


def find_closest_food(product: str, available: List[str]) -> Optional[str]:
    """Найти ближайший продукт по названию"""
    product = product.lower().strip()

    # Специальные правила для популярных мн.ч. и синонимов
    special_rules = {
        'огурцов': 'огурец',
        'огурца': 'огурец',
        'огурцы': 'огурец',
        'капусты': 'капуста',
        'помидор': 'помидор',
        'помидоры': 'помидор',
        'помидора': 'помидор',
        'картофель': 'картофель',
        'картофеля': 'картофель',
        'картофелин': 'картофель',
        'яиц': 'яйцо вареное',
        'яйца': 'яйцо вареное',
        'яйцо': 'яйцо вареное',
        'яйца вареного': 'яйцо вареное',
        'морской капусты': 'морская капуста',
        'морская капуста': 'морская капуста',
        # Вареные продукты
        'вареного картофеля': 'картофель',
        'вареной картошки': 'картофель',
        'вареный картофель': 'картофель',
        'вареная картошка': 'картофель',
        'вареной курицы': 'куриная грудка',
        'вареная курица': 'куриная грудка',
        'куриное': 'куриная грудка',
        'куриное мясо': 'куриная грудка',
        'курицы': 'куриная грудка',
        # Множественное число
        'творога': 'творог',
        'гречи': 'греча',
        'риса': 'рис',
        'овсянки': 'овсянка',
        'банана': 'банан',
        'бананы': 'банан',
        'яблок': 'яблоко',
        'яблоки': 'яблоко',
        'молока': 'молоко',
        'кефира': 'кефир',
        'сыра': 'сыр',
        'хлеба': 'хлеб',
        'макарон': 'макароны',
        'макароны': 'макароны',
        'свина': 'свина',
        'свинина': 'свина',
        'масло': 'масло сливочное',
        'сливочное масло': 'масло сливочное',
        'масла': 'масло сливочное',
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
    situps = 0

    # Парсинг: "шагов 8500, подтягивания 10, отжимания 30, приседания 60, подъем корпуса на пресс 120"
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

    if 'пресс' in message or 'situp' in message.lower():
        m = re.search(r'пресс[\w]*\s*(\d+)', message, re.IGNORECASE)
        if m:
            situps = int(m.group(1))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO activity_log (date, steps, pullups, pushups, squats, situps)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (target_date.isoformat(), steps, pullups, pushups, squats, situps))

    conn.commit()
    conn.close()


def calculate_bmr(age: int = 46, height: int = 187, weight: int = 101) -> float:
    """BMR по формуле Миффлина-Сан-Жеора (мужчины)"""
    return 10 * weight + 6.25 * height - 5 * age + 5


def calculate_activity_calories(steps: int, pullups: int, pushups: int, squats: int, situps: int = None, weight: int = 101) -> float:
    """Расчет калорий на активность"""
    if situps is None:
        situps = 0

    # Шаги: 0.5 ккал на кг на 1000 шагов
    steps_cal = (steps / 1000) * 0.5 * weight

    # Подтягивания: ~3 ккал за повторение
    pullups_cal = pullups * 3

    # Отжимания: ~2 ккал за повторение
    pushups_cal = pushups * 2

    # Приседания: ~1.5 ккал за повторение
    squats_cal = squats * 1.5

    # Подъем корпуса на пресс: ~1 ккал за повторение
    situps_cal = situps * 1

    return steps_cal + pullups_cal + pushups_cal + squats_cal + situps_cal


def get_daily_summary(target_date: date) -> Dict:
    """Получить статистику за день"""
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
        SELECT steps, pullups, pushups, squats, situps
        FROM activity_log WHERE date = ?
    """, (target_date.isoformat(),))

    row = c.fetchone()

    if row:
        steps, pullups, pushups, squats, situps = row
    else:
        steps = pullups = pushups = squats = situps = 0

    conn.close()

    # Расчеты
    bmr = calculate_bmr()
    activity_cal = calculate_activity_calories(steps, pullups, pushups, squats, situps if situps else 0, weight=101)
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
            'squats': squats,
            'situps': situps
        }
    }


def generate_report(target_date: date) -> str:
    """Сгенерировать отчет"""
    summary = get_daily_summary(target_date)

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

    if summary['activity']['situps']:
        report += f"💪 Пресс: {summary['activity']['situps']}\n"

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
        print("  python tracker.py food '200 г творог, 3 персика' [--date YYYY-MM-DD]")
        print("  python tracker.py activity 'шагов 8500, подтягивания 10' [--date YYYY-MM-DD]")
        print("  python tracker.py report [--date YYYY-MM-DD]")
        print("  python tracker.py check --date YYYY-MM-DD")
        return

    cmd = sys.argv[1]
    target_date = None

    if '--date' in sys.argv:
        idx = sys.argv.index('--date')
        target_date = date.fromisoformat(sys.argv[idx + 1])

    if cmd == 'food':
        message = ' '.join(sys.argv[2:])
        if '--date' in message:
            message = message.split('--date')[0].strip()

        entries = log_food(message, target_date)
        print(f"✅ Добавлено: {len(entries)} записей")

        for product, weight, unit, calories in entries:
            print(f"   {product} ({weight}{unit}) - {int(calories)} ккал")

    elif cmd == 'activity':
        message = ' '.join(sys.argv[2:])
        if '--date' in message:
            message = message.split('--date')[0].strip()

        log_activity(message, target_date)
        print("✅ Активность записана")

    elif cmd == 'report':
        if not target_date:
            target_date = get_msk_date()

        report = generate_report(target_date)

        if report:
            print(report)
        else:
            print(f"⚠️ Нет данных за {target_date}")

    elif cmd == 'check':
        if not target_date:
            target_date = date.today() - timezone.timedelta(days=1)

        has_data = has_food_logs(target_date)
        print(f"Data for {target_date}: {has_data}")

    else:
        print("Неизвестная команда")


if __name__ == '__main__':
    main()