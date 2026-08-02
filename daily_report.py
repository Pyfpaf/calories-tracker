#!/usr/bin/env python3
"""
Генератор ежедневных отчетов.
Запускается по cron в 7:00 МСК (4:00 UTC).
"""

import sys
import calendar
from datetime import date, timezone, timedelta, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tracker import generate_report, has_food_logs
from periods import PeriodAnalyzer, format_period_report


def send_reminder(target_date: date) -> str:
    return f"⚠️ Напомни, пожалуйста, что ты ел вчера? Скинь мне список продуктов, и я сразу посчитаю калорийность за прошедший день ({target_date.strftime('%d %B')}).\n"


def get_week_report(yesterday: date) -> str:
    """Недельный отчет за неделю, которая заканчивается вчера"""
    analyzer = PeriodAnalyzer()
    start, end = analyzer.get_week_range(yesterday)
    stats = analyzer.get_period_stats(start, end)
    report = format_period_report(stats, f"Неделя {start.strftime('%d.%m')} - {end.strftime('%d.%m')}")
    analyzer.close()
    return report


def get_month_report(yesterday: date) -> str:
    """Месячный отчет за месяц, который заканчивается вчера"""
    analyzer = PeriodAnalyzer()
    start, end = analyzer.get_month_range(yesterday)
    stats = analyzer.get_period_stats(start, end)
    month_name = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }[start.month]
    report = format_period_report(stats, month_name)
    analyzer.close()
    return report


def main():
    # Вчерашняя дата по МСК
    msk = timezone(timedelta(hours=3))
    today_msk = datetime.now(msk).date()
    yesterday = today_msk - timedelta(days=1)

    # Проверка наличия данных
    has_data = has_food_logs(yesterday)

    if has_data:
        report = generate_report(yesterday)
        if report:
            print(report)
    else:
        print(send_reminder(yesterday))

    # Недельный отчет (воскресенье)
    if yesterday.weekday() == 6:
        print(get_week_report(yesterday))

    # Месячный отчет (последний день месяца)
    last_day_of_month = calendar.monthrange(yesterday.year, yesterday.month)[1]
    if yesterday.day == last_day_of_month:
        print(get_month_report(yesterday))


if __name__ == '__main__':
    main()