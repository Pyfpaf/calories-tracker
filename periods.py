from datetime import date, datetime, timezone, timedelta
from typing import Dict
import calendar
from pathlib import Path
import sys
import sqlite3

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "calories.db"


class PeriodAnalyzer:
    """Анализатор периодов с настраиваемыми параметрами пользователя"""

    def __init__(self, bmr_params: Dict[str, int] = None):
        """
        Args:
            bmr_params: словарь с параметрами пользователя {'age': int, 'height': int, 'weight': int}
                        Если не передан, использует значения по умолчанию
        """
        self.conn = sqlite3.connect(DB_PATH)
        self.bmr_params = bmr_params or {
            'age': 30,
            'height': 175,
            'weight': 75
        }

    def get_week_range(self, target_date: date) -> tuple[date, date]:
        """Возвращает начало и конец недели (пн-вс) для даты"""
        monday = target_date - timedelta(days=target_date.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday

    def get_month_range(self, target_date: date) -> tuple[date, date]:
        """Возвращает начало и конец месяца для даты"""
        first_day = date(target_date.year, target_date.month, 1)
        last_day = date(target_date.year, target_date.month,
                        calendar.monthrange(target_date.year, target_date.month)[1])
        return first_day, last_day

    def get_period_stats(self, start_date: date, end_date: date) -> Dict:
        """Статистика за период"""
        cursor = self.conn.cursor()

        # Съеденные калории
        cursor.execute("""
            SELECT SUM(calories), COUNT(DISTINCT date)
            FROM food_log WHERE date >= ? AND date <= ?
        """, (start_date.isoformat(), end_date.isoformat()))

        row = cursor.fetchone()
        total_eaten = row[0] or 0
        days_with_food = row[1] or 0

        # Активность
        cursor.execute("""
            SELECT SUM(steps), SUM(pullups), SUM(pushups), SUM(squats)
            FROM activity_log WHERE date >= ? AND date <= ?
        """, (start_date.isoformat(), end_date.isoformat()))

        row = cursor.fetchone()
        total_steps = row[0] or 0
        total_pullups = row[1] or 0
        total_pushups = row[2] or 0
        total_squats = row[3] or 0

        # BMR * количество дней
        period_days = (end_date - start_date).days + 1
        bmr = self._calculate_bmr()
        total_bmr = bmr * period_days

        # Калории от активности
        activity_cal = self._calculate_activity_calories(
            total_steps or 0, total_pullups or 0, total_pushups or 0, total_squats or 0
        )

        total_burned = total_bmr + activity_cal
        balance = total_eaten - total_burned

        return {
            'total_eaten': round(total_eaten, 0),
            'days_with_food': days_with_food,
            'period_days': period_days,
            'total_bmr': round(total_bmr, 0),
            'activity_calories': round(activity_cal, 0),
            'total_burned': round(total_burned, 0),
            'balance': round(balance, 0),
            'avg_daily_eaten': round(total_eaten / days_with_food, 0) if days_with_food > 0 else 0,
            'activity': {
                'total_steps': total_steps,
                'total_pullups': total_pullups,
                'total_pushups': total_pushups,
                'total_squats': total_squats
            }
        }

    def _calculate_bmr(self) -> float:
        """BMR по формуле Миффлина-Сан-Жеора (мужчины)"""
        age = self.bmr_params.get('age', 30)
        height = self.bmr_params.get('height', 175)
        weight = self.bmr_params.get('weight', 75)
        return 10 * weight + 6.25 * height - 5 * age + 5

    def _calculate_activity_calories(self, steps: int, pullups: int, pushups: int, squats: int) -> float:
        """Расчет калорий на активность"""
        weight = self.bmr_params.get('weight', 75)
        # Шаги: 0.5 ккал на кг на 1000 шагов
        steps_cal = (steps / 1000) * 0.5 * weight

        # Подтягивания: ~3 ккал за повторение
        pullups_cal = pullups * 3

        # Отжимания: ~2 ккал за повторение
        pushups_cal = pushups * 2

        # Приседания: ~1.5 ккал за повторение
        squats_cal = squats * 1.5

        return steps_cal + pullups_cal + pushups_cal + squats_cal

    def close(self):
        self.conn.close()


def format_period_report(stats: Dict, period_name: str) -> str:
    """Форматирование отчета за период"""
    balance_sign = "+" if stats['balance'] >= 0 else ""
    status = "Профицит" if stats['balance'] >= 0 else "Дефицит"

    report = f"""
📊 {period_name}:
  🍽 Съедено: {int(stats['total_eaten'])} ккал (в среднем {int(stats['avg_daily_eaten'])} ккал/день)
  🏃 Потрачено: {int(stats['total_burned'])} ккал
  📉 {status}: {balance_sign}{int(stats['balance'])} ккал
  📅 Дней с записями: {stats['days_with_food']}/{stats['period_days']}
"""

    if stats['activity']['total_steps']:
        report += f"  🚶 Шагов: {stats['activity']['total_steps']}\n"

    if stats['activity']['total_pullups']:
        report += f"  💪 Подтягивания: {stats['activity']['total_pullups']}\n"

    if stats['activity']['total_pushups']:
        report += f"  🔥 Отжимания: {stats['activity']['total_pushups']}\n"

    if stats['activity']['total_squats']:
        report += f"  🦵 Приседания: {stats['activity']['total_squats']}\n"

    return report