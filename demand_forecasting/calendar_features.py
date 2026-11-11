"""Date features transcribed from the user-supplied 2025–26 DKU calendar.

Inclusive ranges. Unknown earlier dates are flagged; no library closures inferred.
Source pages 1–2, printed revision March 3, 2025. Ranges restricted to data era.
"""
import pandas as pd

EVENTS = {
    'no_classes': [('2025-10-01','2025-10-08'), ('2026-02-16','2026-02-23')],
    'ug_reading': [('2025-10-11','2025-10-12'), ('2025-12-05','2025-12-07'), ('2026-02-27','2026-03-01')],
    'ug_exam': [('2025-10-13','2025-10-16'), ('2025-12-08','2025-12-11'), ('2026-03-02','2026-03-05')],
    'graduate_reading': [('2025-11-21','2025-11-25')],
    'graduate_exam': [('2025-11-26','2025-11-28')],
    'ece_reading': [('2025-11-28','2025-12-02')],
    'ece_exam': [('2025-12-03','2025-12-05')],
    # Full dates between closure at Dec 12 13:00 and reopening Jan 3 09:00.
    'winter_halls_closed': [('2025-12-13','2026-01-02')],
    'mini_term': [('2026-03-09','2026-03-13')],
}
CALENDAR_COLUMNS = ['calendar_known', *EVENTS, 'session_week', 'session_active', 'schedule_day']


def add_calendar(panel):
    result = panel.copy()
    dates = result.date
    result['calendar_known'] = dates.between('2025-08-08', '2026-03-17').astype(int)
    for name, ranges in EVENTS.items():
        flag = pd.Series(False, index=result.index)
        for start, end in ranges:
            flag |= dates.between(start, end)
        result[name] = flag.astype(int)
    result['session_week'] = 0
    result['session_active'] = 0
    for start, end in [('2025-08-18','2025-10-10'), ('2025-10-20','2025-12-04'),
                       ('2026-01-05','2026-02-26'), ('2026-03-16','2026-03-17')]:
        active = dates.between(start, end) & result.no_classes.eq(0)
        result.loc[active, 'session_active'] = 1
        result.loc[active, 'session_week'] = (dates[active] - pd.Timestamp(start)).dt.days // 7 + 1
    result['schedule_day'] = dates.dt.dayofweek
    for date, day in [('2025-10-09',2), ('2025-10-10',3), ('2026-02-13',0)]:
        result.loc[dates.eq(date), 'schedule_day'] = day
    return result
