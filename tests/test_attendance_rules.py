from datetime import date, datetime, time

from alphax_hr.saudi import attendance as a


def dt(h, m=0, d=3):
    return datetime(2026, 11, d, h, m)


def test_shift_window_overnight():
    s, e = a.shift_window(date(2026, 11, 3), time(22), time(6))
    assert s == dt(22) and e == datetime(2026, 11, 4, 6)


def test_late_and_early_with_grace():
    assert a.late_minutes(dt(8), dt(8, 10), grace=15) == 0
    assert a.late_minutes(dt(8), dt(8, 20), grace=15) == 20
    assert a.late_minutes(dt(8), None) == 0
    assert a.early_minutes(dt(17), dt(16, 30), grace=10) == 30
    assert a.early_minutes(dt(17), dt(17, 5)) == 0


def test_pair_logs_double_taps_and_missing_punch():
    logs = a.pair_logs([(dt(8), "IN"), (dt(8, 1), "IN"), (dt(12), "OUT"), (dt(13), "IN"), (dt(17), "OUT"), (dt(17, 2), "OUT")])
    assert logs.first_in == dt(8) and logs.last_out == dt(17, 2)
    assert logs.hours == round(4 + (4 * 60 + 2) / 60, 2) and not logs.missing_punch
    lone = a.pair_logs([(dt(8), "IN")])
    assert lone.missing_punch and lone.hours == 0


def test_overtime_hours_and_art_107_pay():
    assert a.overtime_hours(8.4, 8) == 0.0           # 24 minutes: below threshold
    assert a.overtime_hours(10, 8) == 2.0
    # wage 9,000 (basic 6,000): hourly 37.5, half basic hourly 12.5 -> 50 per OT hour
    assert a.overtime_pay(2, 9000, 6000) == 100.0
    assert a.overtime_pay(2, 9000, 6000, daily_hours=6) == round(2 * (9000 / 180 + 0.5 * 6000 / 180), 2)  # Ramadan


def test_day_codes():
    today = date(2026, 11, 10)
    logs = a.pair_logs([(dt(8, d=9), "IN"), (dt(17, d=9), "OUT")])
    assert a.day_code(day=date(2026, 11, 9), today=today, holiday=False, attendance_status=None, on_leave=False, logs=logs) == "P"
    assert a.day_code(day=date(2026, 11, 8), today=today, holiday=False, attendance_status=None, on_leave=False, logs=None) == "A"
    assert a.day_code(day=date(2026, 11, 6), today=today, holiday=True, attendance_status=None, on_leave=False, logs=None) == "H"
    assert a.day_code(day=date(2026, 11, 8), today=today, holiday=False, attendance_status="On Leave", on_leave=False, logs=None) == "L"
    assert a.day_code(day=date(2026, 11, 12), today=today, holiday=False, attendance_status=None, on_leave=False, logs=None) == ""
    lone = a.pair_logs([(dt(8, d=9), "IN")])
    assert a.day_code(day=date(2026, 11, 9), today=today, holiday=False, attendance_status=None, on_leave=False, logs=lone) == "M"
