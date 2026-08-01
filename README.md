# Telegram Calorie Tracker

Автоматический трекер калорий и активности с анализом КБЖУ. Умеет парсить свободные сообщения, считать калорийность и отправлять отчеты в Telegram.

## Возможности

- Парсинг свободных сообщений о еде (например, "200 г творога, 3 персика")
- Учет активности (шаги, подтягивания, отжимания, приседания)
- Расчет BMR по формуле Миффлина-Сан-Жеора
- Ежедневные/недельные/месячные отчеты
- Автоматическая отправка напоминаний и отчетов по расписанию
- Часовой пояс МСК (UTC+3)

## Установка

```bash
git clone <repo-url>
cd calories-tracker
```

Зависимости: только Python 3.11+ и стандартная библиотека.

## Использование

### Добавление еды

```bash
python tracker.py food "200 г творога, 3 персика"
python tracker.py food "100 г гречки, 150 г куриной грудки"
```

### Добавление активности

```bash
python tracker.py activity "шагов 8500, подтягивания 10"
python tracker.py activity "шагов 10000, отжимания 30, приседания 60"
```

### Отчет за дату

```bash
python tracker.py report
# Или за конкретную дату
python tracker.py report --date 2025-01-30
```

### С настройкой параметров пользователя

```bash
python tracker.py report --bmr age=30 height=175 weight=75
```

## Настройка параметров пользователя

Для корректного расчета калорийности и BMR необходимо указать ваши параметры:

- `age` — возраст (лет)
- `height` — рост (см)
- `weight` — вес (кг)

Параметры можно передавать через флаг `--bmr`:

```bash
python tracker.py report --bmr age=30 height=175 weight=75
python daily_report.py --bmr age=30 height=175 weight=75
```

Также можно задать параметры в коде при использовании API:

```python
from periods import PeriodAnalyzer
bmr_params = {'age': 30, 'height': 175, 'weight': 75}
analyzer = PeriodAnalyzer(bmr_params)
```

## База продуктов

Файл `foods.json` содержит калорийность продуктов (ккал/100г). Формат:

```json
{
  "творог": 110,
  "греча": 150,
  "яйцо вареное": 155
}
```

## Расчеты

### BMR (Миффлин-Сан-Жеора, мужчины)

```
BMR = 10 × вес + 6.25 × рост - 5 × возраст + 5
```

### Расход на активность

- Шаги: 0.5 ккал/кг на 1000 шагов
- Подтягивания: ~3 ккал/повторение
- Отжимания: ~2 ккал/повторение
- Приседания: ~1.5 ккал/повторение

## API

### Работа с БД

```python
from tracker import init_db, log_food, log_activity, generate_report
from periods import PeriodAnalyzer, format_period_report

# Инициализация БД
init_db()

# Добавление еды
entries = log_food("200 г творога, 3 персика")

# Добавление активности
log_activity("шагов 8500, подтягивания 10")

# Отчет за дату
report = generate_report(date.today(), {'age': 30, 'height': 175, 'weight': 75})

# Недельная/месячная аналитика
bmr_params = {'age': 30, 'height': 175, 'weight': 75}
analyzer = PeriodAnalyzer(bmr_params)
stats = analyzer.get_period_stats(start_date, end_date)
print(format_period_report(stats, "Неделя"))
analyzer.close()
```

## Cron для автоматических отчетов

Для ежедневной отправки отчета в 7:00 МСК:

```cron
0 4 * * * cd /path/to/calories-tracker && python daily_report.py
```

## Структура проекта

```
calories-tracker/
├── tracker.py          # Основная логика (парсинг, БД, отчеты)
├── periods.py          # Недельная и месячная аналитика
├── daily_report.py     # Скрипт для cron
├── foods.json          # База калорийности продуктов
├── README.md           # Этот файл
└── calories.db         # SQLite БД (создается автоматически)
```

## Лицензия

MIT