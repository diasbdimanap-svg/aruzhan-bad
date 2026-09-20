# -*- coding: utf-8 -*-
"""
Поведенческая проверка index.html в headless Chromium.

Установка (один раз):
    pip install playwright
    python -m playwright install chromium
Запуск из папки проекта:
    python test-page.py

Проверяет то, что не ловится статикой: модалку на узких экранах, валидацию
телефона, фокус, якоря под sticky-шапкой, перенос меню, калькулятор ИМТ.
"""
import pathlib, sys
from playwright.sync_api import sync_playwright

# консоль Windows по умолчанию cp1251 — иначе вывод с кириллицей падает с UnicodeEncodeError
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = pathlib.Path(__file__).with_name("index.html").as_uri()
results = []

def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))

def settle(page):
    prev, same = -1, 0
    for _ in range(60):
        y = page.evaluate("Math.round(window.scrollY)")
        same = same + 1 if y == prev else 0
        if same >= 3:
            return
        prev = y
        page.wait_for_timeout(100)

with sync_playwright() as pw:
    browser = pw.chromium.launch()

    # ---------- шапка на разных ширинах ----------
    for w in (320, 375, 768, 1030, 1059, 1060, 1440):
        p = browser.new_page(viewport={"width": w, "height": 800}); p.goto(URL); p.wait_for_timeout(250)
        r = p.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('nav.menu a')).filter(a => a.offsetParent !== null);
            const wrapped = links.filter(a => a.getBoundingClientRect().height > 30).length;
            const logo = document.querySelector('.logo').getBoundingClientRect().left;
            const h2 = document.querySelector('#product h2').getBoundingClientRect().left;
            return {wrapped, aligned: Math.abs(logo - h2) <= 1, sw: document.documentElement.scrollWidth};
        }""")
        check(f"[{w}] меню не переносится", r["wrapped"] == 0, f"перенесено={r['wrapped']}")
        check(f"[{w}] лого выровнено с контентом", r["aligned"])
        check(f"[{w}] нет горизонтальной прокрутки", r["sw"] <= w + 1, f"scrollWidth={r['sw']}")
        cta = p.evaluate("""() => { const f=document.querySelector('.nav-cta .cta-full'), s=document.querySelector('.nav-cta .cta-short');
            return {full: getComputedStyle(f).display, short: getComputedStyle(s).display}; }""")
        want_short = w <= 390
        cta_ok = (cta["short"] != "none") == want_short and (cta["full"] != "none") == (not want_short)
        check(f"[{w}] кнопка шапки — короткий текст только на узких экранах", cta_ok, cta)
        # ни одна картинка не искажена: соотношение бокса = соотношению файла (кроме обрезки object-fit:cover в .ph)
        dist = p.evaluate("""() => Array.from(document.images)
            .filter(i => i.naturalWidth && !i.closest('.ph'))
            .map(i => { const b = i.getBoundingClientRect();
                        return {src: i.getAttribute('src'), box: b.width / b.height, nat: i.naturalWidth / i.naturalHeight}; })
            .filter(x => Math.abs(x.box - x.nat) > 0.02)""")
        check(f"[{w}] картинки вне .ph не искажены", not dist, dist[:2])
        degree_count = p.evaluate("document.querySelectorAll('.degree-card').length")
        check(f"[{w}] блок «Ориентировочные изменения» — 3 карточки степеней", degree_count == 3, f"карточек={degree_count}")
        p.close()

    # ---------- якоря ----------
    for w, h in ((320, 640), (375, 667), (1440, 900)):
        p = browser.new_page(viewport={"width": w, "height": h}); p.goto(URL); p.wait_for_timeout(250)
        p.evaluate("document.documentElement.style.scrollBehavior='auto'")
        for a in ["product", "how", "weeks", "composition", "about", "founder", "reviews", "faq", "calc", "documents"]:
            p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(60)
            p.evaluate(f"location.hash='#{a}'"); settle(p)
            gap = p.evaluate(f"""() => {{
                const sec = document.getElementById('{a}');
                const head = sec.querySelector('h2') || sec;
                return Math.round(head.getBoundingClientRect().top - document.querySelector('header').getBoundingClientRect().bottom);
            }}""")
            check(f"[{w}] #{a} не под шапкой", gap >= 0, f"зазор={gap}px")
        p.close()

    # ---------- калькулятор + модалка ----------
    for w, h in ((360, 640), (375, 667), (1440, 900)):
        p = browser.new_page(viewport={"width": w, "height": h})
        errors = []
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.goto(URL); p.wait_for_timeout(250)
        tag = f"[{w}x{h}]"

        # 64/160 и 76.8/160 — ровно на границе ВОЗ; без округления шума float они уезжали в соседнюю категорию
        for kg, cm, num, cat in (("72.15", "170", "24.9", "Норма"), ("72.3", "170", "25.0", "Избыточный вес"),
                                 ("64", "160", "25.0", "Избыточный вес"), ("76.8", "160", "30.0", "Ожирение I степени"),
                                 ("53.4", "170", "18.4", "Недостаточный вес")):
            p.fill("#age", "34"); p.fill("#height", cm); p.fill("#weight", kg)
            p.click("#bmiForm button[type=submit]"); p.wait_for_timeout(150)
            shown = p.inner_text("#bmiVal"); shown_cat = p.inner_text("#bmiCategory"); ann = p.inner_text("#calcAnnounce")
            check(f"{tag} ИМТ {kg}/{cm} -> {num} / {cat}", shown.endswith(num) and cat in shown_cat and num in ann, f"{shown} | {shown_cat}")

        p.click("#calcResult button"); p.wait_for_timeout(300)
        red = p.evaluate("Array.from(document.querySelectorAll('#leadForm input')).filter(i=>getComputedStyle(i).borderColor.replace(/\\s/g,'')==='rgb(180,72,62)').length")
        check(f"{tag} поля не красные при открытии", red == 0, f"красных={red}")
        check(f"{tag} фокус внутри модалки", p.evaluate("document.getElementById('modalOverlay').contains(document.activeElement)"))
        pre = p.evaluate("[document.getElementById('lf-age').value, document.getElementById('lf-height').value, document.getElementById('lf-weight').value]")
        check(f"{tag} калькулятор -> форма перенесён", pre == ["34", "170", "53.4"], pre)
        p.evaluate("document.getElementById('modalOverlay').scrollTop=99999"); p.wait_for_timeout(120)
        reach = p.evaluate("(()=>{const b=document.querySelector('#leadForm button[type=submit]').getBoundingClientRect(); return b.bottom<=innerHeight+1 && b.top>=-1;})()")
        check(f"{tag} кнопка отправки достижима", reach)
        p.fill("#lf-phone", "abc")
        bad = p.evaluate("document.getElementById('lf-phone').validity.patternMismatch")
        p.fill("#lf-phone", "+7 701 123 45 67")
        good = p.evaluate("document.getElementById('lf-phone').validity.patternMismatch")
        check(f"{tag} pattern телефона работает", bad and not good)
        p.fill("#lf-name", "Тест"); p.fill("#lf-city", "Алматы")
        p.click("#leadForm button[type=submit]"); p.wait_for_timeout(200)
        check(f"{tag} фокус на подтверждении", p.evaluate("document.activeElement.id==='leadSuccessView'"))
        p.keyboard.press("Escape"); p.wait_for_timeout(150)
        check(f"{tag} Escape вернул фокус на триггер", p.evaluate("document.activeElement.textContent.includes('консультац')"))
        check(f"{tag} нет JS-ошибок", not errors, errors[:2])
        p.close()

    # ---------- мобильное меню ----------
    p = browser.new_page(viewport={"width": 360, "height": 640}); p.goto(URL); p.wait_for_timeout(250)
    p.click("#burgerBtn"); p.wait_for_timeout(80); p.mouse.click(180, 600); p.wait_for_timeout(80)
    check("меню закрывается кликом вне", p.evaluate("!document.getElementById('mainMenu').classList.contains('open')"))
    p.click("#burgerBtn"); p.wait_for_timeout(80); p.keyboard.press("Escape"); p.wait_for_timeout(80)
    check("меню закрывается по Escape", p.evaluate("!document.getElementById('mainMenu').classList.contains('open')"))
    p.close()

    # все пункты меню достижимы на коротких/альбомных экранах и не перекрыты нижней CTA-панелью
    for w, h in ((667, 375), (640, 360), (320, 568)):
        p = browser.new_page(viewport={"width": w, "height": h}); p.goto(URL); p.wait_for_timeout(250)
        p.click("#burgerBtn"); p.wait_for_timeout(120)
        r = p.evaluate("""() => {
            const menu = document.getElementById('mainMenu');
            const links = Array.from(menu.querySelectorAll('a'));
            let reachable = 0;
            for (const a of links) {
                a.scrollIntoView({block:'nearest'});
                const b = a.getBoundingClientRect();
                const cx = b.left + b.width/2, cy = b.top + b.height/2;
                const hit = document.elementFromPoint(cx, cy);
                if (cy >= 0 && cy <= innerHeight && hit && a.contains(hit)) reachable++;
            }
            return {reachable, total: links.length, scrollable: menu.scrollHeight > menu.clientHeight};
        }""")
        check(f"[{w}x{h}] все пункты меню кликабельны", r["reachable"] == r["total"], f"{r['reachable']}/{r['total']}, прокрутка={r['scrollable']}")
        p.close()

    # на альбомном телефоне слайд не выше 70% экрана (иначе стрелки за кадром, скриншот в три экрана)
    p = browser.new_page(viewport={"width": 667, "height": 375}); p.goto(URL); p.wait_for_timeout(250)
    sh = p.evaluate("Math.round(document.querySelector('#revTrack img').getBoundingClientRect().height)")
    check("[667x375] слайд карусели не выше 70vh", sh <= 0.7 * 375 + 1, f"высота={sh}px")
    p.close()

    # ---------- карусель ----------
    for w, h in ((1440, 900), (375, 667)):
        p = browser.new_page(viewport={"width": w, "height": h}); p.goto(URL)
        # место под ленивые картинки должно быть зарезервировано СРАЗУ, иначе контент прыгает при их загрузке
        early = p.evaluate("[document.getElementById('revTrack').getBoundingClientRect().height, document.getElementById('founderTrack').getBoundingClientRect().height]")
        check(f"[{w}] треки каруселей не схлопнуты до загрузки картинок", min(early) >= 300, f"высоты={[round(x) for x in early]}")
        p.wait_for_timeout(250)
        # контрол должен быть уже на экране (как у реального пользователя), иначе Playwright сам подкрутит страницу
        target = ".rev-next" if w > 640 else "#revDots"
        p.evaluate(f"document.documentElement.style.scrollBehavior='auto'; document.querySelector('{target}').scrollIntoView({{block:'center'}})")
        p.wait_for_timeout(200)
        y0 = p.evaluate("window.scrollY")
        if w > 640:
            p.click(".rev-next"); p.click(".rev-next")
        else:
            p.click("#revDots .rev-dot >> nth=2")
        p.wait_for_timeout(900)
        idx = p.evaluate("Math.round(document.getElementById('revTrack').scrollLeft/document.getElementById('revTrack').clientWidth)")
        dy = p.evaluate("window.scrollY") - y0
        check(f"[{w}] навигация карусели = слайд 2", idx == 2, f"индекс={idx}")
        check(f"[{w}] навигация карусели не прокручивает страницу", abs(dy) <= 1, f"смещение страницы={dy}px")
        check(f"[{w}] активная точка одна и помечена aria-current", p.evaluate("document.querySelectorAll('#revDots [aria-current=\"true\"]').length===1"))
        size = p.evaluate("(()=>{const b=document.querySelector('#revDots .rev-dot').getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)];})()")
        check(f"[{w}] точка карусели ≥24px для тача", min(size) >= 24, f"{size[0]}x{size[1]}")
        p.close()

    # ---------- контраст интерактивных элементов, футер, backdrop-filter ----------
    def rel_luminance(rgb):
        def lin(c):
            c = c / 255
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (lin(c) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast(c1, c2):
        l1, l2 = sorted([rel_luminance(c1), rel_luminance(c2)], reverse=True)
        return (l1 + 0.05) / (l2 + 0.05)

    def parse_rgba(css):
        nums = [float(x) for x in css.strip("rgba()").split(",")]
        while len(nums) < 4:
            nums.append(1.0)
        return tuple(nums[:3]), nums[3]

    def blend_over(fg_css, bg_rgb):
        (fr, fg, fb), a = parse_rgba(fg_css)
        br, bgc, bb = bg_rgb
        return (fr * a + br * (1 - a), fg * a + bgc * (1 - a), fb * a + bb * (1 - a))

    p = browser.new_page(viewport={"width": 1440, "height": 900}); p.goto(URL); p.wait_for_timeout(250)
    field_border = p.evaluate("getComputedStyle(document.querySelector('.field input')).borderTopColor")
    field_bg_css = p.evaluate("getComputedStyle(document.querySelector('.field input')).backgroundColor")
    field_bg, _ = parse_rgba(field_bg_css)
    border_blended = blend_over(field_border, field_bg)
    ratio = contrast(border_blended, field_bg)
    check("рамка поля формы контрастна фону (>=3:1)", ratio >= 3, f"{ratio:.2f}:1 ({field_border} на {field_bg_css})")

    p.evaluate("document.getElementById('reviews').scrollIntoView()"); p.wait_for_timeout(200)
    # первая точка активная (зелёная) — контраст важен именно у НЕактивных точек
    dot_color = p.evaluate("getComputedStyle(document.querySelector('#revDots .rev-dot:not(.active)'), '::before').backgroundColor")
    dot_blended = blend_over(dot_color, (255, 255, 255))
    ratio_dot = contrast(dot_blended, (255, 255, 255))
    check("неактивная точка карусели контрастна фону (>=3:1)", ratio_dot >= 3, f"{ratio_dot:.2f}:1 ({dot_color})")

    header_bd = p.evaluate("getComputedStyle(document.querySelector('header')).getPropertyValue('-webkit-backdrop-filter') || getComputedStyle(document.querySelector('header')).backdropFilter")
    check("шапка: backdrop-filter применяется", "blur" in header_bd, header_bd)

    wa = p.get_attribute("footer a[href*='wa.me']", "href")
    check("футер: WhatsApp — рабочая ссылка", wa == "https://wa.me/77066094641", wa)
    dead_social = p.evaluate("Array.from(document.querySelectorAll('footer a')).filter(a=>!a.getAttribute('href')).length")
    check("футер: нет ссылок-пустышек (Instagram/Telegram убраны)", dead_social == 0, f"пустышек={dead_social}")
    p.close()

    browser.close()

print(f"\n{sum(results)}/{len(results)} пройдено")
sys.exit(0 if all(results) else 1)
