# Медиа Telegraph-лейна @lordchrist

- `lordchrist-telegraph-charnock-NN-cover.jpg` и
  `lordchrist-telegraph-charnock-history-NN-cover.jpg` — утверждённые
  оператором обложки выпусков (16:9). Имя файла обязано совпадать с полем
  `cover.path` соответствующей позиции `../article-queue.json`.
- `_ref-*` — подлинные референсы для генерации обложек по историческим
  личностям (см. §9 `../../TELEGRAPH_ARTICLE_STANDARD.md`).
- `_battle-*` — кадр-победитель баттла обложек, из которого скопирована
  финальная обложка; сохраняется для провенанса выбора.

## Провенанс референсов Чарнока (history-01)

- `_ref-charnock-portrait-1.jpg` — гравюра «Stephen Charnock B.D.»,
  прямоугольный портрет с рукописью (Wikimedia Commons, Национальная
  библиотека Уэльса).
- `_ref-charnock-portrait-2.jpg` — овальная гравюра «STEPHANUS CHARNOCK
  B.D.» (Wikimedia Commons).
- `_ref-charnock-portrait-3.png` — та же овальная гравюра
  (reasonabletheology.org).
- Обложка history-01 (`_battle-history-h.jpg` → `…-history-01-cover.jpg`)
  сгенерирована от этих референсов: Чарнок с рукописью на фоне Великого
  пожара Лондона 1666 года (его библиотека действительно погибла в пожаре;
  сама сцена — художественная драматизация, купол St Paul's на кадре —
  послепожарный, что оговорено в подвале статьи).

## Inline-фотографии статьи о Реформации

- `lordchrist-reformation-1517-inline-01-wittenberg-door.jpg`
- `lordchrist-reformation-1517-inline-02-worms-monument.jpg`
- `lordchrist-reformation-1517-inline-03-zwingli-monument.jpg`
- `lordchrist-reformation-1517-inline-04-geneva-wall.jpg`

Файлы скопированы из пользовательских вложений (соответствие исходникам, размеры,
подписи и проверяемые исторические сведения записаны в
`../history/lordchrist-reformation-1517-01-проверка.md`). Источники фотографий и
лицензии в приложениях не указаны. По прямому указанию пользователя снимки
используются как есть, без дополнительной проверки лицензий; эта заметка не
приписывает им конкретную лицензию. Это четыре inline-фото статьи, не обложка.
Они внесены в rich-article JSON и ручную запись очереди; Telegraph publisher
преобразует их в отдельные фото-блоки с подписями. Встроенные JPEG-данные в
локальном HTML-preview позволяют просмотреть их без внешней сети. Проверка
лицензий остаётся за пределами этой редакционной заметки.


## Обложка к отдельной статье о Реформации

- `lordchrist-reformation-1517-cover.jpg` — выбранный пользователем реалистический вариант обложки; точный размер 2720×1530 (16:9).
- AI-иллюстрация создана по мотивам портрета Лукаса Кранаха Старшего; использованный визуальный ориентир: [Wikimedia Commons, «Lucas Cranach — Portrait of Martin Luther, circa 1530»](https://commons.wikimedia.org/wiki/File:Lucas_Cranach_-_Portrait_of_Martin_Luther,_circa_1530.jpg). Ориентир не вставлен в публикацию как фотография.
- Интерьер с печатным станком — художественная реконструкция, а не документальный снимок; подпись об этом включена и в локальный preview, и в Telegraph-обложку.
- Отдельный HTML-предпросмотр `../history/lordchrist-reformation-1517-01-telegraph-preview.html` включает обложку и четыре inline-фото встраиванием JPEG-данных.
