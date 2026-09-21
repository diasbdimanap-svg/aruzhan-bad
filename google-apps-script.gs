/**
 * FATTOFF — приём заявок с сайта в Google Sheets.
 * Установка: см. google-apps-script-instructions.md рядом с этим файлом.
 */

var SHEET_NAME = 'Заявки';

/* Порядок здесь = порядок колонок в таблице. Общий источник правды для шапки
   и для строки данных, чтобы правка одного списка не рассинхронизировала их. */
var FIELDS = [
  { header: 'Имя', key: 'name' },
  { header: 'Телефон', key: 'phone' },
  { header: 'Возраст', key: 'age' },
  { header: 'Рост, см', key: 'height' },
  { header: 'Вес, кг', key: 'weight' },
  { header: 'ИМТ', key: 'bmi' },
  { header: 'Степень', key: 'category' },
  { header: 'Город', key: 'city' },
  { header: 'Источник', key: 'source' },
  { header: 'Пол', key: 'gender' } /* добавлено для мини-лендинга (mini/index.html) — в форме основного сайта этого поля нет, придёт пустым */
];

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);
  } catch (lockErr) {
    /* Кто-то уже пишет строку — лучше явно сказать "занято", чем молча потерять заявку. */
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'busy, try again' }))
      .setMimeType(ContentService.MimeType.JSON);
  }
  try {
    var data = JSON.parse(e.postData.contents);

    /* ИМТ и степень считаем на сервере из роста/веса, а не берём готовыми от клиента:
       эндпоинт публичный и без авторизации, значит запрос может прийти не только с сайта. */
    var bmiValue = computeBmi_(data.height, data.weight);
    var computed = {
      bmi: bmiValue ? bmiValue.toFixed(1) : '',
      category: bmiValue ? bmiCategory_(bmiValue) : ''
    };

    var row = [new Date()].concat(FIELDS.map(function (f) {
      var v = (f.key === 'bmi' || f.key === 'category') ? computed[f.key] : data[f.key];
      return sanitize_(v);
    }));

    var sheet = getSheet_();
    var targetRow = sheet.getLastRow() + 1;
    var range = sheet.getRange(targetRow, 1, 1, row.length);
    /* Колонки, куда попадает необработанный ввод клиента (Имя..Вес, Город, Источник),
       форсируем как Plain text ДО записи значений. Иначе Sheets пытается трактовать
       строку вида "+7 701 123 45 67" как формулу: с пробелами — сразу #ERROR!,
       без пробелов ("+77011234567") — формула валидна и тихо съедает "+", превращая
       телефон в число. Формат нужно ставить именно до setValues — после того как
       ошибка уже произошла при записи, сменой формата её не вылечить.
       ИМТ и Степень не трогаем: это не ввод клиента, а то, что посчитал сервер. */
    sheet.getRange(targetRow, 2, 1, 5).setNumberFormat('@'); // B:F — Имя, Телефон, Возраст, Рост, Вес
    sheet.getRange(targetRow, 9, 1, 3).setNumberFormat('@'); // I:K — Город, Источник, Пол
    range.setValues([row]);

    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  return ContentService.createTextOutput('FATTOFF lead webhook OK');
}

/* Дублирует границы ВОЗ из bmiCategory() в index.html — при правке диапазонов
   в одном месте обязательно поправь и второе, иначе сайт и таблица разойдутся. */
function bmiCategory_(bmi) {
  if (bmi < 18.5) return 'Недостаточный вес';
  if (bmi < 25) return 'Норма';
  if (bmi < 30) return 'Избыточный вес';
  if (bmi < 35) return 'Ожирение I степени';
  if (bmi < 40) return 'Ожирение II степени';
  return 'Ожирение III степени';
}

function computeBmi_(heightCm, weightKg) {
  var h = Number(heightCm);
  var w = Number(weightKg);
  if (!h || !w || h <= 0 || w <= 0) return null;
  return w / Math.pow(h / 100, 2);
}

/* Защита от формул (эндпоинт публичный — Access: Anyone, и ничего кроме этой функции
   ввод не проверяет) теперь живёт в doPost как Plain text формат колонок, а не здесь.
   Раньше тут было экранирование ведущим апострофом ("'" + v), но для колонки с готовым
   text-форматом Sheets не снимает такой апостроф как маркер, а хранит его буквально —
   поэтому телефон отображался бы как '+7 701... с апострофом на виду. Тут просто привод к строке. */
function sanitize_(v) {
  return (v === undefined || v === null) ? '' : String(v);
}

function getSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(['Дата'].concat(FIELDS.map(function (f) { return f.header; })));
    sheet.setFrozenRows(1);
  }
  return sheet;
}
