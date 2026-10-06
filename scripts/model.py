"""Экономика ИИ-консультанта по вину для сети супермаркетов: два уровня оценки.

Уровень 1 — эффект в выручке, как его обычно считают: прирост ко всей категории.
Уровень 2 — эффект в деньгах: только у покупателей, которые воспользовались ассистентом
(охват), драйверы перемножаются, а не складываются, и выручка переводится в валовую маржу.

Входные данные — публичная отчётность розничного юрлица сети и допущения проекта
(помечены). Бюджет проекта — как в концепции. Результат — CSV в data/.
Запуск:  python3 scripts/model.py
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# --- Категория -------------------------------------------------------------------------
RETAIL_REVENUE = 4_630_000_000          # выручка розничного юрлица сети за 2024 год, ₽
WINE_SHARE = (0.02, 0.035)              # доля вина в выручке — допущение с поправкой на регион
CLIENT_ESTIMATE = (110e6, 120e6)        # оценка объёма категории, которую дал сам заказчик
MARKUP = (0.40, 0.60)                   # торговая наценка на вино — к себестоимости

# --- Драйверы эффекта у покупателя, который воспользовался ассистентом ------------------
# (конверсия в покупку, средний чек, кросс-продажи) — допущения проекта, нижняя и верхняя граница
DRIVERS = {"Конверсия в покупку вина": (0.10, 0.15), "Средний чек": (0.08, 0.12),
           "Кросс-продажи: закуски к вину": (0.03, 0.05)}

# --- Бюджет (как в концепции) -----------------------------------------------------------
MVP_BUDGET = (2.4e6, 3.6e6)
PROJECT_BUDGET = (5e6, 8e6)

COVERAGES = [0.10, 0.20, 0.50, 1.00]    # доля покупателей вина, которые пользуются ассистентом


def category():
    return tuple(RETAIL_REVENUE * s for s in WINE_SHARE)


def margin_rate(markup):
    """Валовая маржа как доля выручки при наценке к себестоимости."""
    return markup / (1 + markup)


MARGIN = (margin_rate(MARKUP[0]), margin_rate(MARKUP[1]))
MARGIN_MID = sum(MARGIN) / 2


def level1():
    """Эффект в выручке по исходной логике: каждый драйвер — процент от всей категории, слагаемые суммируются."""
    lo_cat, hi_cat = category()
    rows = [(name, lo_cat * lo, hi_cat * hi) for name, (lo, hi) in DRIVERS.items()]
    return rows, sum(r[1] for r in rows), sum(r[2] for r in rows)


def uplift(i):
    """Совокупный прирост выручки у охваченного покупателя: драйверы перемножаются. i=0 — нижняя граница, 1 — верхняя."""
    k = 1.0
    for v in DRIVERS.values():
        k *= 1 + v[i]
    return k - 1


def level2(cat, coverage, up=None):
    up = uplift(0) if up is None else up
    revenue = cat * coverage * up
    return revenue, revenue * MARGIN_MID


def threshold_base(coverage, budget, months=12, up=None):
    """Какую выручку сложных категорий должен охватывать ассистент, чтобы бюджет окупился за months месяцев."""
    up = uplift(0) if up is None else up
    return budget * 12 / months / (coverage * up * MARGIN_MID)


def write(name, rows):
    DATA.mkdir(exist_ok=True)
    with open(DATA / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"data/{name}: {len(rows)} строк")


def main():
    lo_cat, hi_cat = category()
    rows1, s_lo, s_hi = level1()
    print(f"категория {lo_cat/1e6:.1f}–{hi_cat/1e6:.1f} млн; маржа {MARGIN[0]:.1%}–{MARGIN[1]:.1%}, середина {MARGIN_MID:.1%}")
    print(f"уровень 1: {s_lo/1e6:.1f}–{s_hi/1e6:.1f} млн выручки; в марже {s_lo*MARGIN_MID/1e6:.1f}–{s_hi*MARGIN_MID/1e6:.1f}")
    print(f"прирост у охваченного: {uplift(0):.1%}–{uplift(1):.1%}")
    t = []
    for c in COVERAGES:
        rev, mar = level2(lo_cat, c)
        t.append({"Охват покупателей вина, %": round(c * 100), "Прирост выручки, млн ₽/год": round(rev / 1e6, 1),
                  "Эффект в марже, млн ₽/год": round(mar / 1e6, 1),
                  "Окупаемость MVP, лет, от": round(MVP_BUDGET[0] / mar, 1),
                  "Окупаемость MVP, лет, до": round(MVP_BUDGET[1] / mar, 1)})
        print(t[-1])
    write("coverage.csv", t)
    th = []
    for c in (0.10, 0.20, 0.50):
        th.append({"Охват, %": round(c * 100),
                   "Порог для MVP за год, млн ₽ выручки категорий": round(threshold_base(c, sum(MVP_BUDGET) / 2) / 1e6),
                   "Порог для проекта за год, млн ₽": round(threshold_base(c, sum(PROJECT_BUDGET) / 2) / 1e6)})
        print(th[-1])
    write("threshold.csv", th)
    write("level1.csv", [{"Драйвер": n, "Нижняя граница, млн ₽": round(a / 1e6, 1), "Верхняя граница, млн ₽": round(b / 1e6, 1)}
                         for n, a, b in rows1])


if __name__ == "__main__":
    main()
