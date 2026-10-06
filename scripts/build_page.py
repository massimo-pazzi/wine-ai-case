"""Собирает страницу кейса index.html из report/case.md и расчётов scripts/model.py.

Места для инфографики отмечены в тексте комментариями <!-- fig:имя -->.
Запуск:  .venv/bin/python scripts/build_page.py
"""

import base64
import sys
from pathlib import Path

import json
import re
import markdown

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import model  # noqa: E402

MD = ROOT / "report" / "case.md"
OUT = ROOT / "index.html"
REPO = "https://github.com/massimo-pazzi/wine-ai-case"


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def num(x):
    return f"{x:,.0f}".replace(",", " ")


def figure(title, body, note=""):
    n = f'<p class="note">{note}</p>' if note else ""
    return f'<figure class="chart"><figcaption class="chart-title">{title}</figcaption>{body}{n}</figure>'


def table(head, rows, cls=""):
    return (f'<div class="table-wrap"><table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) +
            "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) +
            "</tbody></table></div>")


def link(text, url):
    return f'<a href="{url}" target="_blank" rel="noopener">{text}</a>'


# ---------------------------------------------------------------- инфографика

def mln(x, nd=1):
    return f"{x / 1e6:.{nd}f}".replace(".", ",")


def pct(x, nd=1):
    return f"{x * 100:.{nd}f}".replace(".", ",")


def fig_channels():
    steps = [("Торговый зал", "голосовой киоск у винной полки: спросить голосом, отсканировать бутылку"),
             ("Сайт и приложение", "текстовый чат: подбор к блюду, в подарок, по вкусу и бюджету"),
             ("Ассистент", "только вина из наличия конкретного магазина, цена и 1–3 причины, почему подходит"),
             ("Сеть", "данные о спросе и предпочтениях для закупок и ассортимента")]
    html = '<div class="flow">' + "".join(
        (f'<div class="arrow" aria-hidden="true">→</div>' if i else "") +
        f'<div class="flow-col{" core" if i == 2 else ""}"><div class="flow-h">{esc(h)}</div><p>{esc(t)}</p></div>'
        for i, (h, t) in enumerate(steps)) + "</div>"
    return figure("Что предлагалось: консультант по вину в зале, на сайте и в приложении", html)


def fig_category():
    lo, hi = model.category()
    cl, ch = model.CLIENT_ESTIMATE
    mx = 180e6
    X = lambda v: v / mx * 100
    bar = (f'<div class="est"><div class="est-axis"></div>'
           f'<div class="est-range" style="left:{X(lo):.1f}%; width:{X(hi) - X(lo):.1f}%"></div>'
           f'<div class="est-client" style="left:{X(cl):.1f}%; width:{X(ch) - X(cl):.1f}%"></div>'
           f'<span class="est-l" style="left:{X(lo):.1f}%">{mln(lo)}</span>'
           f'<span class="est-l" style="left:{X(hi):.1f}%">{mln(hi, 0)}</span>'
           f'<span class="est-c" style="left:{X((cl + ch) / 2):.1f}%">оценка заказчика: {mln(cl, 0)}–{mln(ch, 0)}</span></div>')
    rows = [("Выручка розничной компании сети, 2024", f"{model.RETAIL_REVENUE / 1e9:.2f} млрд ₽".replace(".", ","), "публичная отчётность"),
            ("Доля вина в выручке", f"{pct(model.WINE_SHARE[0], 0)}–{pct(model.WINE_SHARE[1])}%", "допущение с поправкой на регион"),
            ("<strong>Объём категории</strong>", f"<strong>{mln(lo)}–{mln(hi, 0)} млн ₽ в год</strong>", "расчёт"),
            ("Торговая наценка", "40–60% к себестоимости", "допущение проекта"),
            ("Валовая маржа категории", f"{pct(model.MARGIN[0])}–{pct(model.MARGIN[1])}% выручки",
             "наценка / (1 + наценка)")]
    return figure("Объём винной категории: расчёт и сверка с оценкой заказчика", bar + table(["", "Значение", "Откуда"], rows, "num txtlast"),
                  "Синий — расчётный диапазон, зелёный — объём, который назвал сам заказчик. Данные — scripts/model.py.")


MARKET = [
    ("Vivino", "Мир", "Приложение для покупателей: сканирование этикеток, рейтинги, 74+ млн пользователей", "данные компании",
     "https://www.vivino.com/en/wine-news/the-complete-guide-to-the-vivino-experience"),
    ("Preferabli", "Мир", "Рекомендательная система для ритейлеров: вкусовые профили, интеграция с кассами и сайтами", "данные компании",
     "https://www.digitalcommerce360.com/2024/12/16/albertsons-ai-preferabli-wine-selection/"),
    ("Sommelier.bot", "Мир", "Платформа для ритейла: виджет на сайте, QR-код в зале, API для приложений", "данные компании", "https://sommelier.bot/"),
    ("Pinpointed AI", "Мир", "Бот-сомелье для интернет-магазинов, привязка к складу; от $299 в месяц, голосовой тариф — $699", "прайс-лист",
     "https://pinpointed.dev/ai-sommelier-price/"),
    ("«Винтеллект», Vino.ru", "Россия, июнь 2024", "Telegram-бот на YandexGPT, обучен с участием сомелье; около 10% переходов на маркетплейс, рост "
     "продаж до 30%", "данные компании",
     "https://www.retail.ru/cases/tsifrovoy-somele-dlya-rosta-prodazh-kak-marketpleys-avtorskogo-vina-ispolzuet-iskusstvennyy-intellek/"),
    ("Бот «РБК Вино»", "Россия", "Распознаёт этикетку или штрих-код, база гида по российским винам — около 5000 позиций", "—",
     "https://www.rbc.ru/wine/news/67dbfb1b9a79479f59a6a538"),
    ("BorisBot", "Россия", "Конструктор ботов с шаблоном подбора вина по QR-коду в магазине, без языковой модели", "—",
     "https://borisbot.com/marketplace/rekomendatsiya-vina"),
    ("«Магнит»", "Россия, 2019", "Тест электронного сомелье в торговом зале", "—",
     "https://www.retail.ru/news/v-magnite-poyavilsya-elektronnyy-somele-20-noyabrya-2019-188357/"),
    ("«ВинЛаб»", "Россия, июнь 2026", "ИИ-сомелье во флагманском магазине — после подготовки концепции", "—",
     "https://retailer.ru/vinlab-otkryla-flagmanskij-magazin-s-ii-somele-v-moskve/"),
]


def fig_market():
    rows = [(f"<strong>{esc(n)}</strong>", esc(w), f"{esc(d)} {link('↗', u)}", esc(m)) for n, w, d, m, u in MARKET]
    return figure("ИИ-сомелье в мире и в России", table(["Решение", "Где и когда", "Что делает", "Кто измерял эффект"], rows))


SCENARIOS = [("Вино к блюду", "«Какое вино подойдёт к карбонаре?» — уточняет бюджет и предлагает 3–5 вариантов из наличия"),
             ("Привычного вина нет", "«Любил вальполичеллу, её больше нет» — подбирает похожий стиль в том же бюджете"),
             ("В подарок", "«Что-нибудь элегантное до 3000 ₽» — переводит неформальное описание во вкусовой профиль"),
             ("Не разбираюсь", "Два-три простых вопроса и понятные рекомендации без терминов"),
             ("Скан бутылки", "Карточка вина: вкус, к чему подходит, похожие вина и закуски"),
             ("Праздник", "«День рождения на 10 человек, бюджет 8000» — набор из 3–4 вин с расчётом бутылок")]


def fig_scenarios():
    html = '<div class="cards">' + "".join(
        f'<div class="card"><div class="flow-h">{esc(h)}</div><p>{esc(t)}</p></div>' for h, t in SCENARIOS) + "</div>"
    return figure("Сценарии ассистента", html)


def fig_level1():
    rows1, s_lo, s_hi = model.level1()
    rows = [(esc(n), f"{mln(a)}", f"{mln(b)}") for n, a, b in rows1]
    rows.append(("<strong>Итого дополнительной выручки в год</strong>", f"<strong>{mln(s_lo)}</strong>", f"<strong>{mln(s_hi)}</strong>"))
    return figure("Уровень 1: эффект в выручке, млн ₽ в год",
                  table(["Драйвер", "Нижняя граница", "Верхняя граница"], rows, "num"),
                  "Нижняя граница: +10% конверсии, +8% чека, +3% кросс-продаж к категории 92,6 млн ₽. "
                  "Верхняя: +15%, +12% и +5% к категории 162 млн ₽.")


def fig_level2():
    rows = []
    lo, _ = model.category()
    for c in model.COVERAGES:
        rev, mar = model.level2(lo, c)
        a, b = model.MVP_BUDGET[0] / mar, model.MVP_BUDGET[1] / mar
        pb = f"{a * 12:.0f}–{b * 12:.0f} мес." if a < 1 else f"{a:.1f}–{b:.1f} года".replace(".", ",")
        lab = f"{c * 100:.0f}%" + (" — как в уровне 1" if c == 1 else "")
        rows.append((lab, mln(rev), f"<strong>{mln(mar)}</strong>", pb))
    return figure("Уровень 2: эффект в деньгах при разном охвате покупателей вина",
                  table(["Охват", "Прирост выручки, млн ₽/год", "Эффект в марже, млн ₽/год", "Окупаемость MVP"], rows, "num"),
                  f"Категория — {mln(lo)} млн ₽, прирост у охваченного покупателя — +{pct(model.uplift(0), 0)}%, "
                  f"валовая маржа — {pct(model.MARGIN_MID, 0)}%. MVP — 2,4–3,6 млн ₽; затраты на эксплуатацию не учтены. "
                  "Расчёт — data/coverage.csv.")


def fig_threshold():
    rows = []
    for c in (0.10, 0.20, 0.50):
        a = model.threshold_base(c, sum(model.MVP_BUDGET) / 2)
        b = model.threshold_base(c, sum(model.PROJECT_BUDGET) / 2)
        rows.append((f"{c * 100:.0f}%", f"≈ {a / 1e6:,.0f}".replace(",", " "), f"≈ {b / 1e6:,.0f}".replace(",", " ")))
    lo, hi = model.category()
    return figure("Какую выручку сложных категорий должен охватывать ассистент, чтобы окупиться за год, млн ₽",
                  table(["Охват покупателей", "MVP (≈3 млн ₽)", "Весь проект (≈6,5 млн ₽)"], rows, "num"),
                  f"Для сравнения: винная категория — {mln(lo, 0)}–{mln(hi, 0)} млн ₽. Расчёт — data/threshold.csv.")


def fig_legal():
    rows = [("Голосовой киоск в зале", "Реклама алкоголя разрешена в магазинах, где он продаётся", "Предупреждение о вреде на 10% площади "
             "экрана; без изображений людей и животных — аватара не будет", "первым"),
            ("Ответ на вопрос на сайте сети", "Информация об ассортименте и ценах на сайте продавца — не реклама по позиции ФАС",
             "Нельзя выделять конкретный товар как рекламу; заказ и оплата вина недоступны", "первым"),
            ("Мобильное приложение", "Контент, подгружаемый из интернета, ФАС относит к интернету", "Риск признания рекламой", "после юриста"),
            ("Telegram-бот", "Сторонняя площадка, а не сайт продавца", "Позиция ФАС о сайте продавца сюда не распространяется", "после юриста"),
            ("Персональные рассылки и подсказки", "Проактивное предложение конкретного вина", "Самый высокий риск признания рекламой",
             "только после заключения юриста")]
    return figure("Каналы и правовые ограничения", table(["Канал", "Что говорит закон", "Риск и ограничения", "Очередь"], rows),
                  f'38-ФЗ «О рекламе», ст. 21 ({link("КонсультантПлюс", LAW_ADS)}); 171-ФЗ, ст. 16 — запрет дистанционной продажи '
                  f'({link("КонсультантПлюс", LAW_SALE)}); письма ФАС {link("АК/24981 от 03.08.2012", FAS_2012)} и '
                  f'{link("АК/83509/19 от 25.09.2019", FAS_2019)}. Это не юридическая оценка, а риски для продукта.')


HYPOTHESES = [("Покупатели готовы пользоваться ассистентом", "Уникальные диалоги в неделю; доля диалогов с рекомендацией",
               "≥ 50 диалогов в неделю через месяц; > 60% с рекомендацией"),
              ("Рекомендации воспринимаются как качественные", "Кнопка «полезно», отзывы, проверка штатным сомелье",
               "> 70% положительных; < 5% критических ошибок"),
              ("Ассистент влияет на продажи вина", "Магазин с ассистентом против контрольного или период до и после",
               "Прирост выручки категории > 5%"),
              ("Гибридная архитектура сдерживает выдумки модели", "Доля ответов с фактическими ошибками — по логам и ручной проверке",
               "< 20% в MVP"),
              ("Покупатели переходят в более дорогой сегмент", "Средний чек на вино с рекомендацией против общего", "+8% к среднему")]


def fig_hypotheses():
    rows = [(f"{i}", esc(h), esc(m), esc(t)) for i, (h, m, t) in enumerate(HYPOTHESES, 1)]
    return figure("Гипотезы, которые проверяет MVP", table(["", "Гипотеза", "Как проверяем", "Порог"], rows))


def fig_risks():
    rows = [("Выдумки языковой модели: неверные цены, регионы, вкусы", "Факты — только из каталога по жёстким правилам, модель лишь объясняет; "
             "проверка штатным сомелье на старте"),
            ("Бедная база знаний: во внутренней системе нет вкусовых профилей", "Обогащение из открытых источников и описаний, генерация профилей "
             "по сорту и региону, проверка сомелье"),
            ("Покупатели не подходят к киоску", "Заметное место, быстрые кнопки и свободный голос, A/B-тест размещения"),
            ("Задержки с данными и устройствами на стороне сети", "Старт с выгрузки каталога, переход на API позже; контрольные точки в договоре"),
            ("Правовой риск онлайн-каналов", "Порядок каналов от зала к онлайну, заключение юриста до разработки онлайн-сценариев"),
            ("Неуместные рекомендации и возраст", "Подтверждение 18+, контент-фильтры, аудит журналов диалогов")]
    return figure("Риски и что с ними делаем", table(["Риск", "Что делаем"], rows))


LAW_ADS = "https://www.consultant.ru/document/cons_doc_LAW_58968/e4311f6720a4a4457f53bce4382af75b7858054e/"
LAW_SALE = "https://www.consultant.ru/document/cons_doc_LAW_8368/d3618b9062472ca3182811e431fa7d71b532e447/"
FAS_2012 = "https://www.consultant.ru/document/cons_doc_LAW_134335/"
FAS_2019 = "https://www.consultant.ru/document/cons_doc_LAW_334032/"

REFS = [
    ("«Коммерсантъ»: рост акцизов на вино в 2026 году", "https://www.kommersant.ru/doc/8078635"),
    ("НК РФ, ст. 193: ставки акцизов", "https://www.consultant.ru/document/cons_doc_LAW_28165/22201a65e4f59a582714243c15b655989bd57066/"),
    ("РБК Вино: продажи и доля российских вин в 2025 году", "https://www.rbc.ru/wine/news/6985d0339a7947617c1064b7"),
    ("Forbes: доля российских вин растёт на фоне падения рынка, 20.02.2026",
     "https://www.forbes.ru/wines/555909-dola-rossijskih-vin-rastet-na-fone-obsego-padenia-rynka"),
    ("«Известия»: россияне стали активнее выбирать отечественное вино",
     "https://iz.ru/2120602/denis-kuznetcov/rossiyane-stali-aktivno-vybirat-otechestvennye-vino-i-pivo"),
    ("WineRetail: продажи вина в ритейле, ассортимент федеральных сетей, 29.09.2025",
     "https://wineretail.info/vinotorgovlya/prodazhi-vina-v-ritejle.-glavnyie-czifryi-i-kommentarii-2025-09-29.html"),
    ("38-ФЗ «О рекламе», ст. 21", LAW_ADS),
    ("171-ФЗ, ст. 16: запрет дистанционной продажи алкоголя", LAW_SALE),
    ("Письмо ФАС № АК/24981 от 03.08.2012", FAS_2012),
    ("Письмо ФАС № АК/83509/19 от 25.09.2019", FAS_2019),
] + [(f"{n}: {u.split('/')[2]}", u) for n, _, _, _, u in MARKET]


def fig_refs():
    return ('<ol class="sources">' + "".join(f"<li>{link(esc(t), u)}</li>" for t, u in REFS) + "</ol>"
            f'<p class="note">Расчёты и данные — {link("scripts/model.py", REPO + "/blob/main/scripts/model.py")} и '
            f'{link("data/", REPO + "/tree/main/data")}. Концепция и аналитический отчёт проекта не публикуются; заказчик не называется.</p>')


def author_block():
    img = base64.b64encode((ROOT / "assets/img/author.jpg").read_bytes()).decode()
    return (f'<div class="author"><a href="https://massimo-pazzi.github.io/" title="Все кейсы автора"><img src="data:image/jpeg;base64,{img}" alt="Максим Поципух" width="64" height="64"></a>'
            '<span class="author-txt"><a class="author-name" href="https://massimo-pazzi.github.io/" title="Все кейсы автора">Максим Поципух</a><span class="author-links">Maxim Potsipukh · '
            '<a href="https://t.me/maxim_potsipukh" target="_blank" rel="noopener">Telegram</a> · '
            '<a href="https://max.ru/u/f9LHodD0cOI-rqGbPaCc2EshAXaEgw4ABwO8e2-ng4zK-otGeBnO04IzH5g" target="_blank" rel="noopener">Max</a></span></span></div>')


FIGS = {"channels": fig_channels, "category": fig_category, "market": fig_market, "scenarios": fig_scenarios,
        "level1": fig_level1, "level2": fig_level2, "threshold": fig_threshold, "legal": fig_legal,
        "hypotheses": fig_hypotheses, "risks": fig_risks, "refs": fig_refs}

CSS = """
:root{
  --bg:#f5f6f7; --surface:#ffffff; --ink:#18202a; --ink-2:#4b5662; --muted:#6c7782;
  --rule:#d9dee3; --accent:#1f5fae; --accent-soft:#e6eef8; --neutral:#aab2bb;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#a07800; --ok:#1b8a5a; --warn:#a36b00; --no:#8a929b;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){ color-scheme:dark;
    --bg:#11161c; --surface:#171d24; --ink:#e7ebef; --ink-2:#b5bec7; --muted:#8c96a0;
    --rule:#2c343d; --accent:#79a9e8; --accent-soft:#1c2632; --neutral:#5d6670;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --ok:#3fbf86; --warn:#e0a640; --no:#7d8791; }
}
:root[data-theme="dark"]{ color-scheme:dark;
  --bg:#11161c; --surface:#171d24; --ink:#e7ebef; --ink-2:#b5bec7; --muted:#8c96a0;
  --rule:#2c343d; --accent:#79a9e8; --accent-soft:#1c2632; --neutral:#5d6670;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --ok:#3fbf86; --warn:#e0a640; --no:#7d8791; }
body{margin:0; background:var(--bg); color:var(--ink); font-family:"Golos Text",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:17px; line-height:1.62; padding-inline:16px; padding-block:40px 64px;}
.page{max-width:48rem; margin:0 auto;} a{color:var(--accent);}
.eyebrow{font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:12.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--accent); margin:0 0 14px;}
h1{font-size:clamp(1.7rem,4.2vw,2.3rem); line-height:1.18; font-weight:700; letter-spacing:-.01em; text-wrap:balance; margin:0 0 16px;}
h2{font-size:1.28rem; line-height:1.3; font-weight:650; text-wrap:balance; margin:46px 0 12px; padding-top:22px; border-top:1px solid var(--rule);}
.author{display:flex; align-items:center; gap:12px; margin:4px 0 16px; font-weight:600; font-size:15px;}
.author img{width:64px; height:64px; border-radius:50%; object-fit:cover; border:1px solid var(--rule);}
.author-txt{display:flex; flex-direction:column; gap:2px;} .author-name{color:inherit; text-decoration:none;} .author-name:hover{color:var(--accent); text-decoration:underline;} .author a img{display:block;} .author-links{font-weight:400; font-size:13.5px; color:var(--muted);} .author-links a{color:var(--accent);}
.author + p em{color:var(--ink-2); font-size:15px;}
p{margin:0 0 14px;} strong{font-weight:620;} hr{display:none;}
.chart{margin:16px 0 22px; background:var(--surface); border:1px solid var(--rule); border-radius:6px; padding:14px 16px 12px;}
.chart-title{font-weight:600; font-size:14.5px; margin-bottom:10px; line-height:1.4;}
.note{font-size:12.5px; color:var(--muted); margin:10px 0 0; line-height:1.5;}
.flow{display:grid; grid-template-columns:1fr auto 1fr auto 1fr auto 1fr; gap:8px; align-items:stretch;}
.flow-col{border:1px solid var(--rule); border-radius:6px; padding:10px 12px; font-size:13px; line-height:1.45;} .flow-col p{margin:0;}
.flow-h{font-weight:650; font-size:12.5px; text-transform:uppercase; letter-spacing:.04em; color:var(--ink-2); margin-bottom:6px;}
.flow-col.core{background:var(--accent-soft); border-color:var(--accent);} .flow-col.core .flow-h{color:var(--accent);}
.arrow{align-self:center; color:var(--muted); font-size:20px;}
@media (max-width:700px){ .flow{grid-template-columns:1fr;} .arrow{transform:rotate(90deg); justify-self:center;} }
.funnel{display:grid; gap:8px;}
.fn-row{display:grid; grid-template-columns:1fr 1fr; gap:12px; align-items:center;}
.fn-bar{box-sizing:border-box; max-width:100%; background:var(--s1); color:#fff; border-radius:4px; padding:7px 10px; font-weight:600; font-size:14px; min-width:9em; justify-self:end;}
.fn-row:last-child .fn-bar{background:var(--s2);}
.fn-l{font-size:13.5px; line-height:1.35;} .fn-l span{display:block; color:var(--muted); font-size:12.5px;}
.table-wrap{overflow-x:auto;}
table{border-collapse:collapse; width:100%; font-size:14px;}
th,td{text-align:left; padding:8px 10px 8px 0; border-bottom:1px solid var(--rule); vertical-align:top;}
th{font-weight:600; color:var(--ink-2); font-size:12.5px;}
.matrix td:first-child{font-weight:550; min-width:11em;} .matrix th:last-child,.matrix td:last-child{background:var(--accent-soft); padding-left:8px;}
.price td:last-child{text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap;}
.y{color:var(--ok); font-weight:600;} .p{color:var(--warn); font-weight:600;} .n{color:var(--no);}
.steps{margin:0; padding-left:1.4em; columns:2; column-gap:28px; font-size:14px;} .steps li{margin-bottom:6px; break-inside:avoid;}
@media (max-width:640px){ .steps{columns:1;} }
.pairs{display:grid; gap:12px;}
.pair{display:grid; grid-template-columns:minmax(9em,13em) 1fr; gap:12px; align-items:center; font-size:13.5px;}
.pr-l span{display:block; color:var(--muted); font-size:12px;}
.pr-bars{display:grid; gap:4px;}
.pb{display:flex; align-items:center; gap:8px; font-size:12.5px; font-variant-numeric:tabular-nums;} .pb span{white-space:nowrap;}
.bar{height:14px; border-radius:3px; min-width:3px;} .bar.s1{background:var(--s1);} .bar.s2{background:var(--s2);}
.legend{display:flex; flex-wrap:wrap; gap:6px 16px; font-size:12.5px; color:var(--ink-2); margin-top:12px;}
.legend span{display:inline-flex; align-items:center; gap:6px;} .sw{display:inline-block; width:11px; height:11px; border-radius:2px;}
.sw.s1{background:var(--s1);} .sw.s2{background:var(--s2);}
.chart-scroll{overflow-x:auto;} .chart svg{display:block; width:100%; min-width:560px; height:auto;}
.grid{stroke:var(--rule); stroke-width:1;} .tick{fill:var(--muted); font-size:11px; font-family:"IBM Plex Mono",ui-monospace,monospace;}
.target{stroke:var(--ink-2); stroke-width:1.2; stroke-dasharray:5 4;} .median{stroke:var(--muted); stroke-width:1; stroke-dasharray:2 3;}
.band-label{fill:var(--muted); font-size:11px;} .label{fill:var(--ink); font-size:12px;}
.line{fill:none; stroke-width:2.2;} .line.s1{stroke:var(--s1);} .line.s2{stroke:var(--s2);} .line.s3{stroke:var(--s3);} .line.s4{stroke:var(--s4);}
.dot{stroke:var(--surface); stroke-width:2;} .dot.s1{fill:var(--s1);} .dot.s2{fill:var(--s2);} .dot.s3{fill:var(--s3);} .dot.s4{fill:var(--s4);}
.kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-bottom:12px;}
.kpi{border:1px solid var(--rule); border-radius:6px; padding:12px 14px;}
.kpi-v{font-size:1.4rem; font-weight:700; font-variant-numeric:tabular-nums;} .kpi-l{font-size:13px; color:var(--ink-2); margin-top:4px; line-height:1.4;}
.gap{height:14px;}
.rel{margin-bottom:14px;} .rel-h{font-weight:620; font-size:13.5px; margin:4px 0 8px; color:var(--accent);} .rel0 .rel-h{color:var(--ink-2);}
.est{position:relative; height:64px; margin:6px 0 14px;}
.est-axis{position:absolute; left:0; right:0; top:22px; height:2px; background:var(--rule);}
.est-range{position:absolute; top:14px; height:18px; background:var(--s1); opacity:.35; border-radius:3px;}
.est-client{position:absolute; top:14px; height:18px; background:var(--s3); border-radius:3px;}
.est-l{position:absolute; top:38px; transform:translateX(-50%); font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums;}
.est-c{position:absolute; top:-4px; transform:translateX(-50%); font-size:12px; color:var(--ink-2); white-space:nowrap;}
.cards{display:grid; grid-template-columns:repeat(3,1fr); gap:10px;}
.card{border:1px solid var(--rule); border-radius:6px; padding:10px 12px; font-size:13px; line-height:1.45;} .card p{margin:0;}
@media (max-width:640px){ .cards{grid-template-columns:1fr;} }
.num td:not(:first-child),.num th:not(:first-child){text-align:right; font-variant-numeric:tabular-nums;}
.txtlast td:last-child,.txtlast th:last-child{text-align:left;}
.dl-link{margin:-12px 0 22px; font-size:13.5px;}
.chart.live iframe{display:block; width:100%; border:0; border-radius:4px; background:#fff;}
.sources{font-size:14.5px; line-height:1.55; padding-left:1.5em;}
@media (max-width:520px){ body{font-size:16px; padding-block:24px 48px;} .pair,.fn-row{grid-template-columns:1fr;} .fn-bar{justify-self:start;} }
.ranges{display:grid; gap:7px;}
.rg{display:grid; grid-template-columns:minmax(10em,16em) 1fr; gap:12px; align-items:center; font-size:13.5px;}
.rg-bar{display:flex; align-items:center; gap:0; font-size:12.5px; font-variant-numeric:tabular-nums;}
.rg-lo{height:14px; background:var(--s1); border-radius:3px 0 0 3px;} .rg-hi{height:14px; background:var(--s1); opacity:.35; border-radius:0 3px 3px 0;}
.rg-bar span{margin-left:8px; white-space:nowrap;} .sw.s1l{background:var(--s1); opacity:.35;}
.cols3{display:grid; grid-template-columns:repeat(3,1fr); gap:10px;}
.c3{border:1px solid var(--rule); border-radius:6px; padding:10px 12px; font-size:13.5px; line-height:1.45;}
.c3 ul{margin:0; padding-left:1.1em;} .c3 li{margin-bottom:4px;}
.c3.core{background:var(--accent-soft); border-color:var(--accent);} .c3.core .flow-h{color:var(--accent);}
.tiles{display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:10px;}
.tile{border:1px solid var(--rule); border-radius:6px; padding:10px 12px; font-size:13px; line-height:1.4;}
.tile-n{font-size:1.5rem; font-weight:700; color:var(--accent); font-variant-numeric:tabular-nums;}
.tile-h{font-weight:620; margin:2px 0;} .tile-s{color:var(--ink-2); font-size:12.5px;} .tile-e{color:var(--muted); font-size:12px; margin-top:4px;}
.num td:not(:first-child),.num th:not(:first-child){text-align:right; font-variant-numeric:tabular-nums;}
.txtlast td:last-child,.txtlast th:last-child{text-align:left;}
@media (max-width:640px){ .cols3{grid-template-columns:1fr;} .rg{grid-template-columns:1fr; gap:4px;} }
"""



# Блок «Другие кейсы автора» — одинаковый во всех кейсах портфолио, ставится над источниками.
OTHER_CASES = [
    ("hotel-market-case", "Анализ рынка", "Рост цен в отелях Петербурга перестал окупаться"),
    ("housing-digital-twin-case", "Новый продукт", "Цифровой двойник жилого фонда Москвы: от аварийного ремонта к прогнозу поломок"),
    ("b2b-value-case", "Обоснование проекта", "Как доказать окупаемость ИИ-проекта, не зная маржи заказчика"),
    ("fastfood-assistant-case", "Продукт с ИИ", "ИИ-ассистент для федеральной сети быстрого питания: как спроектировать продукт не имея данных заказчика"),
    ("rief-2026-talk", "Стратегия и аналитика рынка", "Интерфейс энергетики будущего: доклад на РМЭФ-2026"),
    ("wine-ai-case", "Категорийный маркетинг", "ИИ-сомелье для сети супермаркетов: при каких условиях он может окупиться"),
]


def other_cases(current):
    tiles = "".join(
        f'<a class="oc-tile" href="https://massimo-pazzi.github.io/{slug}/"><span class="oc-tag">{tag}</span>'
        f'<span class="oc-title">{title}</span><span class="oc-go">Открыть кейс →</span></a>'
        for slug, tag, title in OTHER_CASES if slug != current)
    style = ("<style>.oc-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:10px; margin:12px 0 8px;}"
             ".oc-tile{display:flex; flex-direction:column; gap:6px; padding:14px 16px; background:var(--surface); border:1px solid var(--rule);"
             " border-radius:6px; text-decoration:none; color:inherit;} .oc-tile:hover{border-color:var(--accent);}"
             ".oc-tag{font-size:12px; letter-spacing:.04em; text-transform:uppercase; color:var(--accent);}"
             ".oc-title{font-weight:600; font-size:15px; line-height:1.35;} .oc-go{margin-top:auto; font-size:13px; color:var(--accent);}</style>")
    return f'{style}<h2>Другие кейсы автора</h2><div class="oc-grid">{tiles}</div>\n'


# SEO: заголовок, описание, автор, canonical, Open Graph и JSON-LD — одинаково во всех кейсах портфолио.
AUTHOR = {"@type": "Person", "name": "Максим Поципух", "alternateName": "Maxim Potsipukh",
          "sameAs": ["https://t.me/maxim_potsipukh",
                     "https://max.ru/u/f9LHodD0cOI-rqGbPaCc2EshAXaEgw4ABwO8e2-ng4zK-otGeBnO04IzH5g",
                     "https://github.com/massimo-pazzi"]}
OG_IMAGE = "https://massimo-pazzi.github.io/rief-2026-talk/assets/img/og.jpg"
SEO = {
    "hotel-market-case": ("Гостиничный рынок Петербурга — Максим Поципух",
                          "Рост цен в отелях Петербурга перестал окупаться",
                          "Исследование Максима Поципуха по открытым данным: почему рост цен в отелях Петербурга "
                          "перестал окупаться — спрос и номерной фонд, сезонность, сегменты, города и прогноз."),
    "housing-digital-twin-case": ("Цифровой двойник ЖКХ — Максим Поципух",
                                  "Цифровой двойник жилого фонда Москвы: от аварийного ремонта к прогнозу поломок",
                                  "Продуктовый кейс Максима Поципуха: цифровой двойник жилого фонда Москвы и прогноз "
                                  "отказов инженерных систем домов — для кого продукт, метрики, прототип, этапы внедрения."),
    "b2b-value-case": ("Окупаемость без маржи — Максим Поципух",
                       "Как доказать окупаемость ИИ-проекта, не зная маржи заказчика",
                       "Кейс Максима Поципуха: обоснование ИИ-проекта для грузовой авиакомпании — цена бездействия, "
                       "две картины ценности и пороговая маржа, которую заказчик проверяет сам."),
    "fastfood-assistant-case": ("ИИ-ассистент без данных — Максим Поципух",
                                "ИИ-ассистент для федеральной сети быстрого питания: как спроектировать продукт не имея данных заказчика",
                                "Продуктовый кейс Максима Поципуха: ИИ-ассистент в приложении федеральной сети быстрого "
                                "питания — темы обращений, границы продукта, очерёдность релизов, нагрузка, экономика и риски."),
    "wine-ai-case": ("ИИ-сомелье для сети супермаркетов — Максим Поципух",
                     "ИИ-сомелье для сети супермаркетов: при каких условиях он может окупиться",
                     "Кейс Максима Поципуха по категорийному маркетингу: ИИ-консультант по вину для сети супермаркетов — "
                     "объём категории, эффект в выручке и в марже с учётом охвата, порог окупаемости, правовые ограничения и MVP."),
    "rief-2026-talk": ("Интерфейс энергетики будущего — Максим Поципух",
                       "Интерфейс энергетики будущего: доклад на РМЭФ-2026",
                       "Доклад Максима Поципуха на Российском международном энергетическом форуме 2026: как "
                       "искусственный интеллект меняет взаимодействие человека с энергетической инфраструктурой."),
}


def seo_head(slug):
    title, headline, desc = SEO[slug]
    url = f"https://massimo-pazzi.github.io/{slug}/"
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": headline, "description": desc,
          "inLanguage": "ru", "url": url, "mainEntityOfPage": url, "image": OG_IMAGE, "author": AUTHOR}
    q = lambda t: t.replace("&", "&amp;").replace('"', "&quot;")
    return (f'<title>{title}</title>\n'
            f'<meta name="description" content="{q(desc)}">\n'
            f'<meta name="author" content="Максим Поципух (Maxim Potsipukh)">\n'
            f'<link rel="canonical" href="{url}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:locale" content="ru_RU">\n'
            f'<meta property="og:site_name" content="Максим Поципух — портфолио">\n'
            f'<meta property="og:title" content="{q(title)}">\n'
            f'<meta property="og:description" content="{q(desc)}">\n'
            f'<meta property="og:url" content="{url}">\n'
            f'<meta property="og:image" content="{OG_IMAGE}">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n'
            f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>')


def apply_seo(page, slug):
    """Заменяет <title> и description страницы на SEO-блок."""
    page = re.sub(r'<meta name="description" content="[^"]*">\n?', "", page)
    return re.sub(r"<title>[^<]*</title>", lambda m: seo_head(slug), page, count=1)


def main():
    html = markdown.markdown(MD.read_text(encoding="utf-8"), extensions=["tables"])
    title, rest = html.split("</h1>", 1)
    html = title + "</h1>\n" + author_block() + rest
    for name, fn in FIGS.items():
        marker = f"<!-- fig:{name} -->"
        assert marker in html, f"нет места для блока {name}"
        html = html.replace(marker, fn())
    page = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>ИИ-ассистент без данных</title>
<meta name="description" content="Портфолио-кейс менеджера продукта с ИИ: как спроектировать ИИ-ассистента для приложения сети быстрого питания, когда заказчик не дал ни сценариев, ни статистики обращений">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
</head>
<body>
<main class="page">
<p class="eyebrow">Портфолио-кейс: категорийный маркетинг и продукт с ИИ · Максим Поципух · Март 2026</p>
{html}
</main>
</body>
</html>
"""
    page = page.replace("<h2>Источники</h2>", other_cases("wine-ai-case") + "<h2>Источники</h2>", 1)
    page = apply_seo(page, "wine-ai-case")
    OUT.write_text(page, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(page) // 1024} КБ, блоков: {len(FIGS)}")


if __name__ == "__main__":
    main()
