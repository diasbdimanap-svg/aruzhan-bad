/**
 * Проверка границ классификации ИМТ.
 * Функция bmiCategory вынимается из index.html, а не копируется сюда,
 * чтобы тест падал при изменении реального кода страницы.
 *
 * Запуск:  node test-bmi.js
 */
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const match = html.match(/function bmiCategory\(bmi\)\{[\s\S]*?\n\}/);
if (!match) {
  console.error('FAIL: функция bmiCategory не найдена в index.html');
  process.exit(1);
}
const bmiCategory = new Function(match[0] + '; return bmiCategory;')();

const bmi = (kg, cm) => kg / (cm / 100) ** 2;

// [вес, рост, ожидаемая категория, комментарий]
const cases = [
  [50.0, 170, 'Недостаточный вес', 'ИМТ 17.3'],
  [53.4, 170, 'Недостаточный вес', 'ИМТ 18.478 — округление до 18.5 не должно давать «Норма»'],
  [53.5, 170, 'Норма', 'ИМТ 18.51 — первая точка нормы'],
  [72.1, 170, 'Норма', 'ИМТ 24.95'],
  [72.15, 170, 'Норма', 'ИМТ 24.965 — округление до 25.0 не должно давать «Избыточный вес»'],
  [72.3, 170, 'Избыточный вес', 'ИМТ 25.02'],
  [86.6, 170, 'Избыточный вес', 'ИМТ 29.97'],
  [86.8, 170, 'Ожирение I степени', 'ИМТ 30.03'],
  [101.1, 170, 'Ожирение I степени', 'ИМТ 34.98'],
  [101.2, 170, 'Ожирение II степени', 'ИМТ 35.02'],
  [115.5, 170, 'Ожирение II степени', 'ИМТ 39.97'],
  [115.7, 170, 'Ожирение III степени', 'ИМТ 40.03'],
];

let failed = 0;
for (const [kg, cm, expected, note] of cases) {
  const value = bmi(kg, cm);
  const actual = bmiCategory(value);
  const ok = actual === expected;
  if (!ok) failed++;
  console.log(
    `${ok ? 'ok  ' : 'FAIL'} ${kg} кг / ${cm} см -> ИМТ ${value.toFixed(3)} -> "${actual}"` +
    (ok ? '' : ` (ожидалось "${expected}")`) + `   [${note}]`
  );
}

// Показанное число и категория не должны противоречить друг другу.
// На странице число усекается до 0.1 (Math.floor), а не округляется —
// иначе 24.96 выводилось бы как «25.0» рядом с «Норма».
const shownValue = (v) => Math.floor(v * 10) / 10;
let mismatches = 0;
for (let v = 15; v <= 45; v += 0.007) {
  if (bmiCategory(shownValue(v)) !== bmiCategory(v)) {
    mismatches++;
    if (mismatches <= 3) console.log(`FAIL показ ${shownValue(v).toFixed(1)} vs точное ${v.toFixed(3)}: категории расходятся`);
  }
}
console.log(mismatches ? `FAIL расхождений показ/категория: ${mismatches}` : 'ok   показ (усечение до 0.1) всегда в той же категории, что и точное значение');
failed += mismatches ? 1 : 0;

console.log(`\n${cases.length + 1 - failed}/${cases.length + 1} пройдено`);
process.exit(failed ? 1 : 0);
