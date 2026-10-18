# Технические приложения к отчёту EmbedLang

**Техническая заготовка, подготовленная с помощью ИИ по исходникам и записям
проекта. Не авторский текст студентов.** Проверена привязка к доступным файлам;
задание Ключева А. О. теперь идентифицировано, см. [матрицу](ASSIGNMENT_MAPPING.md).
Студенты должны проверить и
отредактировать эти сведения, прежде чем включать их в сдаваемую работу.

Текущая сверка с исходным PDF, обязательные пробелы и checklist:
[FINAL_COMPLIANCE_AUDIT.md](FINAL_COMPLIANCE_AUDIT.md). Zed UI этап сохранён как
`854c413a1558a5d2168f3979637310aa78928e89`; старые строки хронологии описывают
состояние на момент записи, не текущее состояние реализации.

## A. Реализация компилятора: проверочная карта

```text
.emb → ANTLR lexer/parser → AST → semantic/type analysis → typed IR
                                                         ↓
                            GNU ARM Thumb-2 assembly → внешний firmware build
                                                         ↓
                                   startup + runtime + linker → ELF → BIN
```

| Компонент | Проверяемая реализация |
| --- | --- |
| Gradle/Kotlin/ANTLR | [compiler/build.gradle.kts](../../compiler/build.gradle.kts), Kotlin JVM/JDK 17, ANTLR4 4.13.2 |
| Грамматика | [EmbedLang.g4](../../compiler/src/main/antlr/EmbedLang.g4): приоритеты операторов, блоки, функции, разделители строк |
| Построение AST | [AstBuilder.kt](../../compiler/src/main/kotlin/embedlang/frontend/AstBuilder.kt), посетитель parse tree |
| Модель AST | [Ast.kt](../../compiler/src/main/kotlin/embedlang/ast/Ast.kt): sealed interfaces, data classes, SourceLocation |
| Фасад frontend | [Frontend.kt](../../compiler/src/main/kotlin/embedlang/frontend/Frontend.kt): parse/analyze/lower |
| Имена и типы | [SemanticAnalyzer.kt](../../compiler/src/main/kotlin/embedlang/semantic/SemanticAnalyzer.kt), области видимости, сигнатуры, return paths |
| Built-ins | [Builtins.kt](../../compiler/src/main/kotlin/embedlang/semantic/Builtins.kt): GPIO/time/OLED, типизированные сигнатуры |
| Типизированное IR | [Ir.kt](../../compiler/src/main/kotlin/embedlang/ir/Ir.kt), структурные if/while, связанные локальные переменные |
| AST → IR | [IrLowerer.kt](../../compiler/src/main/kotlin/embedlang/ir/IrLowerer.kt), использует результаты успешного анализа типов |
| ARM | [ArmBackend.kt](../../compiler/src/main/kotlin/embedlang/backend/arm/ArmBackend.kt): GNU Thumb-2, стековые локальные переменные, вызовы, метки |
| CLI | [Main.kt](../../compiler/src/main/kotlin/embedlang/Main.kt): валидация, `--emit-ir`, `--emit-asm` |
| Firmware | [build.py](../../firmware/build.py), [build_local.py](../../firmware/build_local.py): внешняя сборка ELF/BIN |

Поддерживаются `i32`, `u32`, `u8`, `bool`, `void`; переменные, присваивания,
арифметика/сравнения/логика, if/else, while, функции и return. Обязательна
`fn main() -> void`. Строки, float, указатели и динамическая память отсутствуют.
OLED получает печатные ASCII-коды `u32`; строковый тип для демонстрации не добавлен.

CLI читает один UTF-8-файл. Успех имеет код 0, ошибки frontend — 1,
ошибка использования/чтения файла — 2. Диагностика имеет вид
`file:line:column: semantic error [CODE]: message`, строки/колонки начинаются с 1.
ANTLR считает Unicode code points; редакторный адаптер преобразует их в UTF-16.
Ошибки синтаксиса и семантики не приводят к частичному IR/assembly-выводу.

Прошивка не создаётся самим CLI. Внешняя сборка переименовывает generated `main`
в `embed_program_main`, добавляет C-wrapper, HAL/runtime/startup и linker script.
Политика ABI и ограничения вычислений описаны в [ARM_BACKEND.md](../ARM_BACKEND.md).
Эта карта предназначена для проверки личного объяснения студентов, не заменяет его.

## B. Этапы и подтверждённое состояние

| Этап | Результат | Вид доказательства |
| --- | --- | --- |
| 1 | Kotlin/ANTLR frontend, AST, семантика, типы; первоначально 34 теста | Локальные тесты и документация REQUIREMENTS |
| 2 | Typed IR, lowering, `--emit-ir`; 57 тестов | Локальные тесты/снимки IR |
| 3 | GNU Thumb-2, `--emit-asm`; 76 JUnit + 15 ARM checks | Локальная сборка/эмуляция, не физический STM32 |
| 4A и диагностика | Runtime и cLAB SRAM-интеграция; ограниченное восстановление уже настроенного PLL | Локальные тесты, затем отдельные пользовательские аппаратные наблюдения |
| Local Blink F427 | Пять зелёных импульсов, затем OFF; `5a5fbd6` | Сообщение пользователя, ранее проверенные запись/чтение Flash |
| OLED | Чёткое THE BEST GROUP; `5f8a6b7`; 160 checks | Пользовательская аппаратная проверка + отдельная локальная регрессия |
| Публичный снимок | `feeb729`, новая история, 170 файлов после исключений лицензирования | Проверенная публикация GitHub; отличается от полной локальной истории |
| 6: VS Code | Локальный прототип: .emb, подсветка, CLI-команды, Problems, VSIX; 197 проверок | Unit/TextMate + CLI + реальный Host + прежняя регрессия; новой публикации нет |
| Zed, продолжение editor integration | Локальный Tree-sitter WASM, конфигурация и CLI tasks; общий итог 221 | 24 новые компонентные проверки; сам Zed UI не проверен, новой аппаратной проверки нет |
| 7: начало GDB/TCP-IP | ARM GDB → локальный RSP/Unicorn; breakpoint, stepi, register/memory reads, результат 42 | 8 новых проверок; не editor UI, не `.emb` source-level и не hardware |
| 7: исходные строки `.emb` | Optional `.file/.loc`, настоящий file:line breakpoint и `step` 2→3→4→5→6 | 12 новых проверок, общий итог 241; без typed locals, editor UI и hardware |
| VS Code source debug | Cortex-Debug/GDB/Unicorn, настоящий editor Host; `b4bd308` | 253 passed; `.emb` breakpoint, stepping, Pause/resume и 42, без hardware |
| Zed debugger, 2026-10-18 | Официальный Rust API 0.7.0, собранный WASM, standalone CDT/GDB/TCP | 263 passed; только build/API/protocol, **Zed UI не проверен**, новые изменения без коммита |
| Zed Windows UI, 2026-10-18 | После разрешённой установки 1.24.2: исправлен component target, реальные source-debug controls и 42 | 264 automated passed + отдельные UI-наблюдения; новые изменения без коммита, без hardware |

Числа ранних этапов относятся к их историческому состоянию; их нельзя суммировать
как число уникальных тестов текущего этапа. Хронология не присваивает неизвестным
действиям календарные даты. Для дальнейших этапов коммит указывается только после
его фактического создания.

## C. Методика тестирования и воспроизводимость

Подтверждённый baseline OLED: **160 проверок** = 82 JUnit + 15 ARM execution +
43 runtime/cLAB + 8 local F407 + 5 local F427 + 7 OLED integration.
Подробности текущих запусков и команды — в [VERIFICATION.md](VERIFICATION.md).

JUnit проверяет frontend/IR/ARM/CLI, включая ошибки, типы и примеры. Python/Unicorn
исполняет ARM-код с моделью/подменой отдельных периферийных операций. Проверка ELF
устанавливает адреса/символы/векторы/соответствие BIN, но сама по себе не доказывает
физическую работоспособность. Значения synthetic stack high-water не являются
верхней границей стека при всех аппаратных прерываниях.

Полная firmware-регрессия требует собранных локальных образов и сохранённых
эталонных fixtures. Они намеренно не включаются в Git. Публичный снимок также
исключает четыре OLED/font-файла и два reference-файла без подтверждённых условий
распространения. Поэтому свежий публичный clone не воспроизводит все 160 проверок
без дополнительных разрешённых компонентов и локальной подготовки.

## D. Физическая проверка: факты и границы

Источник: [HARDWARE_VALIDATION.md](../HARDWARE_VALIDATION.md), основанный на
реальных сообщениях пользователя и ранее сохранённых результатах OpenOCD.

| Проверка | Подтверждено | Не следует утверждать |
| --- | --- | --- |
| cLAB F407 probe | PLL_MATCH_RECOVERED, BEFORE_GENERATED, PROBE_RESULT=42, AFTER_GENERATED, TRACE_COMPLETE | Измеренная производительность всех программ |
| cLAB F407 Blink | Пять импульсов, десять переходов; trace timestamps 1.942 / 2511.801 / 2762.795 | Независимо измеренная длительность по шкале Web IDE |
| Local F427 Blink | SDK-1.1M, маркировка STM32F427VIT6, пять зелёных импульсов и OFF | Измеренный физический уровень BOOT0/положение XP3 |
| Local F427 OLED | Пользователь подтвердил чёткий THE BEST GROUP; сообщение записано 2026-10-17 | Не предоставленные фото, осциллограммы I2C или точное время наблюдения |

Программирование OLED завершено 2026-10-15 по отдельному разрешению пользователя;
дата последующего сообщения о дисплее — 2026-10-17. Образ: 13 576 байт,
SHA-256 `a76fd04e15b0d6e2e7d5726d93433f6a677501e8f198883f5c4b77564d5a0c8c`.
Запись только sector 0 по адресу 0x08000000, проверка остальных 2 080 768 байт
Flash и неизменности option bytes выполнены ранее, не в этапе VS Code.

На локальном F427 используются I2C1 PB8/PB9, AF4, адрес 0x3C (HAL 0x78),
официальная 7×10-гарнитура. Архитектура системы — Cortex-M4/ARMv7E-M/Thumb-2,
2 MiB Flash, 192 KiB main SRAM + 64 KiB CCM. cLAB использует другую, SRAM-загрузочную
конфигурацию F407; её нельзя смешивать с локальным Flash-образом.

Raw trace хранит микросекунды по формуле официального драйвера; миллисекунды
в отображении Web IDE являются обоснованной интерпретацией, а не независимо
проверенной шкалой интерфейса. В Milestone 6 платы нет и аппаратных тестов нет.

## E. Известные ограничения

- Нет классов, строк, float, модулей, указателей, heap, потоков и исключений.
- Нет Zed LSP/Problems. Базовая `.emb` GDB/source-step интеграция проверена в
  VS Code Host и реальном Zed 1.24.2 UI через localhost Unicorn. Typed locals,
  полный unwind и physical STM32 GDB-сеанс не подтверждены. Это шире раннего PoC,
  но не полная отладочная информация для всех программ.
- VS Code использует установленный CLI/JDK, не встраивает JVM-компилятор.
  CLI получает сохранённый локальный файл; untitled/виртуальные документы
  не поддерживаются. Подробное поведение save/validation описано в extension guide.
- Диагностика CLI даёт точку, а не диапазон токена. Редактор показывает один
  code point или позицию EOF; это не точный span AST.
- OLED API ограничен printable ASCII и фиксированным 7×10-шрифтом.
- Наблюдения hardware подтверждают конкретные демонстрации; электрические
  запасы, точность частоты, worst-case interrupt stack и все отказы не измерены.
- Лицензии сторонних компонентов различаются; нельзя объявлять весь проект
  MIT/Apache. Оригинальный код не получил новую blanket-license при публикации.
- Оригинал задания прочитан; личное ТЗ, объяснение архитектуры, реальные промпты
  и окончательная интерпретация требований требуют работы студентов.

## F. Источники для проверки

- [GitHub EmbedLang](https://github.com/qusaeotoman/EmbedLang), публичная новая история.
- [Архитектура](../ARCHITECTURE.md), [IR](../IR.md), [спецификация языка](../LANGUAGE_SPEC.md).
- [Local F427](../LOCAL_F427.md), [OLED](../LOCAL_OLED.md), [ITMO.cLAB](../ITMO_CLAB.md).
- [Third-party provenance](../../firmware/THIRD_PARTY.md), pinned revisions/hashes.
- [VS Code language extensions](https://code.visualstudio.com/api/language-extensions/overview).
- [VS Code diagnostics API](https://code.visualstudio.com/api/references/vscode-api).
- [VS Code extension tests](https://code.visualstudio.com/api/working-with-extensions/testing-extension).
- Ключев А. О., Университет ИТМО, 2026: **«Лекция 1: Введение и практическое
  задание»**, стр. 10–15; [описание источника и соответствие](ASSIGNMENT_MAPPING.md).
- [Фрагменты исходников с русскими пояснениями](CODE_EXCERPTS.md).

## G. Milestone 6: проверочная карта расширения

| Файл | Назначение |
| --- | --- |
| [package.json](../../extensions/vscode/package.json) | Регистрация языка, трёх команд, настроек и ограничений Workspace Trust |
| [TextMate grammar](../../extensions/vscode/syntaxes/embedlang.tmLanguage.json) | Комментарии, ключевые слова, типы, числовые литералы, built-ins и функции |
| [Language configuration](../../extensions/vscode/language-configuration.json) | Комментарии, скобки, autoclosing и отступы |
| [compiler.js](../../extensions/vscode/src/compiler.js) | Аргументы Java CLI, запуск без shell, разбор stderr и преобразование координат |
| [extension.js](../../extensions/vscode/src/extension.js) | VS Code DiagnosticCollection, сохранение, события, проверка версий и вывод preview |
| [Tests](../../extensions/vscode/test/) | Unit/TextMate, реальный CLI и настоящие Host-сценарии |

```text
VS Code command / save event
  → trusted workspace + saved local .emb
  → Java + installed lib/* + embedlang.MainKt + existing CLI mode
  → stderr → Problems (source locations)
  → successful stdout → untitled IR / ARM assembly preview
```

Runtime расширения использует только VS Code API и встроенные модули Node.js.
Тестовый TextMate-движок и vsce — dev dependencies, не содержимое VSIX runtime.
Результаты CLI с устаревшей версией документа не должны применяться к новому
тексту. Правка очищает старые Problems; закрытие документа удаляет его записи.
Этот материал служит технической опорой, а личное архитектурное объяснение
студентов по-прежнему остаётся в незаполненном разделе 4 REPORT.md.

## H. Zed: локальный прототип

**Проверено локально 2026-10-17.** Это техническое AI-приложение.

| Исходник | Назначение |
| --- | --- |
| [Editor grammar](../../extensions/zed/tree-sitter/grammar.js) | Tree-sitter, приоритеты выражений, tolerant parsing; не заменяет ANTLR |
| [config.toml](../../extensions/zed/languages/embedlang/config.toml) | `.emb`, комментарии, скобки, пробелы/отступы |
| [Запросы](../../extensions/zed/languages/embedlang/) | Реальные Tree-sitter highlights, brackets, indents, outline |
| [build.js](../../extensions/zed/build.js) | Генерация ABI 14 и сборка WASM side module без WASI main/startup |
| [tasks.json](../../.zed/tasks.json) | Zed task schema, сохранение буфера, build/validate/IR/ASM |
| [task.js](../../extensions/zed/task.js) | Повторное использование чистого Node CLI-адаптера; stdout/stderr/exit status |
| [Инструкция](../../extensions/zed/README.md) | Локальная установка, зависимости, диагностика и ограничения |

```text
Zed saved-file task → pure Node CLI adapter → existing Java compiler
  → stderr file:line:column → terminal navigation
  → successful IR / assembly → terminal + ignored build/zed
```

14 проверок настоящего WASM/Tree-sitter: формат модуля, пять примеров, четыре
query-файла, категории подсветки, приоритеты, неполный ввод и таблица built-ins.
10 task-проверок: реальный компилятор, координаты ошибок, IR/ASM, отказы,
небезопасные для shell имена, входные пути и структура задач. Прежние 197
проверок повторно пройдены. Подробности — в VERIFICATION.md.

Диагностика поддержана через терминал, **не через LSP/Problems**. Нет completion,
rename, formatter или GDB. Из-за отсутствия Zed не заявляются успешная установка,
отрисовка подсветки или проверенные клики по ссылкам. Unpacked package подготовлен
локально; dev builder потребует реальную Git-ревизию грамматики после разрешённого
коммита. Пустое поле `rev` намеренно не выдаётся за опубликованный source pin.

Официальные источники: [language extensions](https://zed.dev/docs/extensions/languages),
[tasks](https://zed.dev/docs/tasks), [terminal paths](https://zed.dev/docs/terminal#path-hyperlinks),
[dev builder](https://zed.dev/docs/extensions/developing-extensions).
Интерпретация этих возможностей проверена по source builder/runtime Zed;
ссылки находятся в инструкции расширения. Это не подтверждение полного выполнения
задания: editor UI-приёмка и GDB/TCP/IP stepping в обоих редакторах остаются.

## I. Начало GDB/TCP-IP: границы доказательства

Editor/report milestone сохранён локальным коммитом
`40fa24276761ee67af803e6741c483f7f6f89a93`, перед новым этапом checkout был чист.
Новый изолированный test tool не меняет compiler или firmware architecture:

| Файл | Назначение |
| --- | --- |
| [inspect_elf.py](../../tools/debug/inspect_elf.py) | Read-only symbols/DWARF source coverage |
| [unicorn_rsp.py](../../tools/debug/unicorn_rsp.py) | Ограниченный loopback RSP endpoint, настоящий Unicorn Cortex-M4 |
| [gdb_connection_checks.py](../../tests/gdb_connection_checks.py) | Сборка реального generated probe и 8 проверок, включая настоящий GDB/TCP |
| [GDB_DEBUGGING.md](../GDB_DEBUGGING.md) | Команды воспроизведения, аудит ELF, план DAP adapters и source mapping |

Наблюдались symbol breakpoint, аргументы 6/7, single instruction step, чтение
core registers и stack memory; выполнение дало r0=42 и восстановленный SP.
Ни одна проверенная DWARF line table не содержит `.emb`. Ассемблерные `.s` lines
и C/startup DWARF не подменяют исходную отладку EmbedLang. ARM GDB поддерживает
MI2, но его native DAP interpreter отсутствует. Поэтому Zed нельзя подключить
непосредственно к RSP как к DAP endpoint.

Пока отсутствуют editor debug adapters, `.emb` line/type/local metadata,
надёжно проверенный unwind и hardware debug session. RSP PoC ограничен pure
code, одним клиентом и budget; не моделирует STM32 peripherals/clock/interrupts.
Личные разделы архитектуры и реальная история AI-промптов остаются за студентами.

## J. Минимальная исходная отладка `.emb`

Предыдущий GDB/RSP этап сохранён коммитом
`848a38ecbd6ee445cdf12db95b97e3b47f0bcc4a`; checkout был чист перед новым этапом.
После заранее объяснённого предложения добавлен opt-in режим
`--emit-asm --debug-lines`. Он использует существующие IR SourceLocation,
не меняет AST/IR/семантику и не требует новых language constructs.

| Источник | Назначение |
| --- | --- |
| [ArmBackend](../../compiler/src/main/kotlin/embedlang/backend/arm/ArmBackend.kt) | `.file` с UTF-8 C-escapes; `.loc` original line/column и is_stmt |
| [CLI](../../compiler/src/main/kotlin/embedlang/Main.kt) | Optional flag, абсолютный source path от cwd компилятора |
| [Fixture](../../tests/fixtures/source_debug.emb) | 6×7, сохранение/присваивание, возврат результата |
| [Kotlin tests](../../tests/src/test/kotlin/embedlang/DebugLinesTest.kt) | Default equivalence, escaping, source positions, control-flow placement |
| [ELF/GDB tests](../../tests/source_debug_checks.py) | Настоящие line tables, byte comparison, TCP GDB source steps |
| [Guide](../SOURCE_DEBUGGING.md) | Сборка, команды, ограничения и доказательства |

GDB breakpoint задан **полным исходным `.emb` путём и строкой 2**, включая
пробелы в пути. Четыре команды `step` действительно остановились на строках
3, 4, 5, 6; каждый PC сопоставлен строке через GDB `info line *$pc`. В конце
r0=42 и SP=0x20010000. В DWARF нет подмены `.emb` строк строками generated `.s`.
Debug/plain `.text` совпадает побайтно для probe и большого ARM fixture.

Разделение границ: UTF-8 имя Ω подтверждено через compiler API и ELF, потому
что native Windows JDK/Cp1251 теряет часть Unicode argv ещё до загрузки файла.
Произвольные Unicode CLI/GDB paths не заявляются. Typed local-variable debugging,
полный unwind, `next` через calls и debug UI обоих редакторов не реализованы.
Новых аппаратных наблюдений нет; полная регрессия — 241 passed в VERIFICATION.md.

## K. VS Code: исходная отладка через TCP/IP

Source-line milestone сохранён как `87807cefcb7eb96445ab79cb8f5c162a53ef5681`.
Последующая редакторная интеграция оставлена незакоммиченной для review.

| Источник | Назначение |
| --- | --- |
| [debug-extension.js](../../extensions/vscode/src/debug-extension.js) | Команда, trust/source guards, создание DAP session и cleanup target |
| [local-debug.js](../../extensions/vscode/src/local-debug.js) | Реальная сборка CPU ELF, внешний Cortex-Debug attach, Python process |
| [unicorn_rsp.py](../../tools/debug/unicorn_rsp.py) | Опциональный Ctrl-C polling, ограниченное interactive execution |
| [debug Host](../../extensions/vscode/test/debug-host/index.js) | Восемь сценариев настоящего VS Code/Cortex-Debug/GDB |
| [unit checks](../../extensions/vscode/test/local-debug.test.js) | Loopback-only endpoints, безопасный attach и missing target |
| [Guide](../VSCODE_DEBUGGING.md) | Настройка, воспроизведение, первичные источники и ограничения |

Выбран поддерживаемый Cortex-Debug вместо написания собственного DAP adapter.
Приложение запускается в отдельном локальном Unicorn target; STM32 initialization
и peripherals не исполняются. В реальном VS Code 1.139.1/Cortex-Debug 1.12.1
подтверждены `.emb` breakpoint, editor source positions, Step Into, Continue,
Pause/resume, регистры, disassembly, текущий кадр и результат 42. Полная регрессия
— 253 passed. Это не typed locals, не полный unwind и не physical debug.
Прежний compiler/firmware pipeline сохранён, Zed debugging не начат.

## L. Zed: проверенные build/API/protocol, ожидается UI-приёмка

Запись раздела K описывает предыдущий этап. Теперь VS Code сохранён как
`b4bd308d56685035d35267241c5fbc2fb41aba33`, а отдельная Zed интеграция реализована
без изменения compiler/firmware. Она остаётся незакоммиченной для review.

| Источник | Назначение и граница доказательства |
| --- | --- |
| [Rust extension](../../extensions/zed/debugger/src/lib.rs) | Официальные `get_dap_binary`/`dap_request_kind`, stdio DAP process, API 0.7.0 |
| [Manifest/schema](../../extensions/zed/debugger/extension.toml) | Регистрация EmbedLang GDB, отдельный package без grammar fetch |
| [Preparation](../../extensions/zed/debug.js) | CPU ELF и ignored local debug.json, без overwrite существующих scenarios |
| [DAP tests](../../extensions/zed/test/debug.test.js) | Реальный Eclipse CDT 1.10.0/GDB/Unicorn; breakpoint, step, registers/disassembly, 42, Pause/resume и cleanup |
| [WASM check](../../extensions/zed/test/wasm.test.js) | Реальные exports и custom API version section, **не запуск Zed** |
| [Guide](../ZED_DEBUGGING.md) | Зависимости, сборка, локальная установка и точный manual checklist |

Release WASM собран Rust 1.90.0 GNU Windows / wasm32-wasip1; два Rust tests
passed. Вся повторная регрессия — 263 проверки. Zed отсутствует: UI loading,
gutter breakpoints, controls и panels не продемонстрированы. Полный unwind,
typed locals, hardware debugging и формальная приёмка задания не заявляются.
Личные архитектура/ТЗ/AI-промпты студентов сохранены незаполненными.

Финальная фиксация 2026-10-18: Zed milestone сохранён как
`cca8b36cf34ac0e334ec2a7d4300ca8328e0a629`. Повтор 10 Zed-specific checks прошёл.
Последующая read-only проверка Windows не нашла установленного/запущенного Zed
в проверенных местах; portable custom path не исключается. Установка ожидает
разрешения пользователя. Историческая граница **«реальный Zed UI не проверен»**
сохраняется; никаких UI-фактов не добавлено.

## M. Последующая настоящая приёмка Zed 1.24.2

Историческая граница раздела L сохранена: до установки editor UI не проверялся.
После разрешения пользователя установлен официальный stable Zed; оба локальных
unpacked extension загружены в отдельный ignored user-data profile. Выявлен и
исправлен packaging bug wasip1 core → **wasip2 component**, как в официальном
builder v1.24.2. API 0.7.0/Rust glue и compiler/firmware не изменены.

Наблюдались recognition/highlighting/matched braces, успешный Validate task,
F9 breakpoint `.emb:2`, source Step Into 3–6, Continue, два Pause/resume,
Register scope и полезные stack entries. После возврата Console показала
**42 / SP 0x20010000**; disassembly доступна через `>x/5i $pc`. Stop завершил
owned GDB/Unicorn, закрыл RSP port. Dedicated disassembly pane, typed locals,
полный unwind, автоматическая вставка скобок и произвольные source cases не
объявляются проверенными. Nonfatal completion/encoding warnings записаны.

Вся регрессия повторена: **264 automated passed**, включая новый core-WASM
rejection test; actual UI не включён в это число. Точная методика, команды и
ограничения — [VERIFICATION.md](VERIFICATION.md), [guide](../ZED_DEBUGGING.md).
Новые source/docs изменения оставлены без коммита; generated binaries, profiles,
installers и logs ignored. Личные тексты студентов сохранены, платы/Flash и
публикации не было.

Финальный review Zed UI от 2026-10-18: повторены 33 Node + 2 Rust проверки,
все **35 passed**; locked wasip2 release build и упаковка успешны. Это повтор
части 264, без новой UI/hardware проверки. По разрешению пользователя этот
Zed UI этап сохраняется локальным Git-коммитом; предыдущие фразы о незакоммиченных
изменениях описывают состояние на момент их записи. Следующий compliance audit
будет отдельным документальным результатом, без новых возможностей языка.

## N. Сохранение и итоговый compliance audit

Zed UI/package/tests/docs сохранены коммитом
**854c413a1558a5d2168f3979637310aa78928e89**; непосредственно после него дерево
чисто. Перед фиксацией 35 релевантных проверок passed, wasip2 build/package
успешны. Старые фразы «без коммита» — исторические. Полный записанный результат
264 не суммируется с повтором этих тестов.

Далее повторно прочитан оригинал PDF и визуально проверены слайды 10–15.
Создан [итоговый аудит](FINAL_COMPLIANCE_AUDIT.md) со всеми обязательными пунктами
и checklist. Главные незакрытые части — личные H1–H4, состав/понимание кода,
подтверждение CubeIDE либо instructor approval GNU workflow и доступная сдаваемая
Git-ревизия. Emulator debug явно отделён от physical execution и не выдаётся
за аппаратную source-debug демонстрацию. Optional locals/unwind/LSP/LLVM не
назначены обязательными без основания в PDF. Новые audit/docs изменения не
закоммичены; функций, hardware operations и публикации нет.

## O. Публичная source-редакция после отдельного разрешения

Export 854c413 и reviewed audit/docs подготовлен как продолжение чистой public
истории feeb729, без private Git ancestry. Existing 72 vendor entries, шесть
исключений и OLED guard сохранены. В public checkout проверены 253 applicable
checks с zero failures; один optional reference skipped, три historical checks
и семь OLED firmware checks недоступны без внешних разрешённых fixtures/sources.
Девять firmware builds/ELF/BIN verification и обе Zed WASM builds успешны.

Локальные 264 и новый public result различаются scope, не аппаратным результатом.
Student text не создан ИИ; notices и source-only ограничения описаны в
[PUBLICATION_NOTES.md](../../PUBLICATION_NOTES.md). Никаких новых board tests
или compiled-extension releases нет. Предыдущие «не опубликовано» — история до
этого разрешения; наличие source в GitHub не доказывает выполнение H1–H4/T5.
