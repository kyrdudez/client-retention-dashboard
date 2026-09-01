# -*- coding: utf-8 -*-
"""
Код проверки report.csv против сырых данных.
Запуск: python3 audit_check.py
Печатает диагностику по каждому найденному расхождению, использованную
как основание для report_fixed.csv и AUDIT.md.
"""
import pandas as pd

DATA = "/mnt/user-data/uploads/"

projects = pd.read_csv(DATA+"projects.csv", sep=';', encoding='utf-8-sig')
hist     = pd.read_csv(DATA+"projects_history.csv", sep=';', encoding='utf-8-sig')
report   = pd.read_csv(DATA+"report.csv", sep=';', encoding='utf-8-sig')
changes  = pd.read_csv(DATA+"service_changes.csv", sep=';', encoding='utf-8-sig')
terms    = pd.read_csv(DATA+"service_terms.csv", sep=';', encoding='utf-8-sig')
works    = pd.read_csv(DATA+"works.csv", sep=';', encoding='utf-8-sig')
works['month'] = pd.to_datetime(works['month'])

pd.set_option('display.width', 200)

print("="*80)
print("1. Уникальные клиенты: projects.csv vs projects_history.csv")
print("="*80)
print("Всего project_id в projects.csv:", projects['project_id'].nunique())
print("Строк переименования (=слияние в 1 клиента) в projects_history.csv:", len(hist))
print("=> Ожидаемое число уникальных клиентов:", projects['project_id'].nunique() - len(hist))
print("Уникальных client_id в report.csv:", report['client_id'].nunique())

print()
print("="*80)
print("2. Пропуски (разрывы) в помесячных отгрузках по project_id")
print("="*80)
for pid, g in works.groupby('project_id'):
    g = g.sort_values('month')
    months = g['month'].tolist()
    for i in range(len(months)-1):
        gap = (months[i+1].to_period('M') - months[i].to_period('M')).n
        if gap > 1:
            print(f"project_id={pid}: разрыв между {months[i].date()} и {months[i+1].date()} "
                  f"({gap-1} пропущенных месяцев)")

print()
print("="*80)
print("3. Метки label (стоп/энд) и что происходит с отгрузками ПОСЛЕ метки")
print("="*80)
labeled = works[works['label'].notna()]
for _, row in labeled.iterrows():
    pid, m = row['project_id'], row['month']
    after = works[(works.project_id == pid) & (works.month > m)]
    print(f"project_id={pid}, месяц={m.date()}, label='{row['label']}' -> "
          f"отгрузок ПОСЛЕ этой метки: {len(after)} "
          f"({'возобновились!' if len(after) else 'больше не было'})")

print()
print("="*80)
print("4. Проекты 320/321: одновременный биллинг во время переезда (rename)")
print("="*80)
r = hist[hist.project_id == 320].iloc[0]
overlap_320 = set(works[works.project_id == 320]['month'])
overlap_321 = set(works[works.project_id == 321]['month'])
print("Переименование 320->321 датировано:", r['month'])
print("Месяцы, где ОБА id одновременно получили отгрузку:",
      sorted(m.date() for m in (overlap_320 & overlap_321)))

print()
print("="*80)
print("5. service_changes: применялся ли report.csv к историческим флайтам?")
print("="*80)
print(changes.to_string(index=False))
print()
print("projects.csv хранит только ТЕКУЩИЙ (актуальный) service_type/term_months.")
print("report.csv, судя по всему, берёт service_type/term_months из projects.csv")
print("и подставляет их ВСЕМ историческим флайтам проекта, а не тому service_type,")
print("который реально действовал в конкретном периоде (по service_changes).")

print()
print("="*80)
print("6. Флайты, где last_active_month не совпадает с реальностью works.csv")
print("="*80)
for _, row in report.iterrows():
    pids = [int(x) for x in str(row['project_ids']).split('|')]
    w = works[works.project_id.isin(pids)]
    w_in_flight = w[(w.month >= row['flight_start']) & (w.month <= row['flight_end']) & (w.amount > 0)]
    real_last = w_in_flight['month'].max() if len(w_in_flight) else None
    reported_last = pd.to_datetime(row['last_active_month'])
    match = (real_last == reported_last) if real_last is not None else (pd.isna(reported_last))
    flag = "OK" if match else "!! РАСХОЖДЕНИЕ"
    print(f"client={row.client_id} flight_no={row.flight_no} "
          f"report.last_active={row.last_active_month} "
          f"факт.последняя_реальная_отгрузка={real_last.date() if real_last is not None else None} "
          f"[{flag}]")

print()
print("="*80)
print("7. Флайты, где отгрузки обрываются РАНЬШЕ планового flight_end (без метки)")
print("="*80)
for _, row in report.iterrows():
    pids = [int(x) for x in str(row['project_ids']).split('|')]
    w = works[works.project_id.isin(pids)]
    fe = pd.to_datetime(row['flight_end'])
    w_in_flight = w[(w.month >= row['flight_start']) & (w.month <= fe)]
    has_label = w_in_flight['label'].notna().any()
    last_real = w_in_flight[w_in_flight.amount > 0]['month'].max()
    if pd.notna(last_real) and last_real < fe and not has_label:
        months_short = (fe.to_period('M') - last_real.to_period('M')).n
        print(f"client={row.client_id} flight_no={row.flight_no}: последняя отгрузка "
              f"{last_real.date()}, план.конец {fe.date()} -> оборвался на {months_short} мес. "
              f"раньше, БЕЗ метки label. status в отчёте='{row.status}'")

print()
print("="*80)
print("8. Отчёт устарел? report_generated_at vs фактический диапазон works.csv")
print("="*80)
print("report_generated_at (все строки):", report['report_generated_at'].unique())
print("Максимальный месяц в works.csv:", works['month'].max().date())
stale = report[pd.to_datetime(report['report_generated_at']) < works['month'].max()]
print("Строк отчёта, где данные works.csv 'моложе' отчёта:", len(stale))
