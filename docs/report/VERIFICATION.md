# Журнал проверок отчёта

Отделять локальные тесты, эмуляцию, Extension Host, сборку и аппаратные наблюдения.
Сведения для текущего этапа обновляются только после завершения команд.

## Подтверждённый baseline до Milestone 6

OLED `5f8a6b7`: 160 проверок прошли; подробности в
[HARDWARE_VALIDATION.md](../HARDWARE_VALIDATION.md). Это исторический результат
этапа OLED, а не автоматически приписанный новый запуск расширения.
Пользователь отдельно подтвердил физический результат THE BEST GROUP 2026-10-17.

## Milestone 6 — выполнено локально, без платы

**Запись 2026-10-17, Europe/Moscow.** Все перечисленные ниже команды действительно
выполнены. Новых аппаратных результатов нет. Ни GitHub push, ни Marketplace
publish, ни установка расширения в обычный профиль пользователя не выполнялись.
Машинные пути JDK, ARM tools и Code.exe заменены переносимыми переменными;
локальные логи и временные профили не включаются в отчёт/Git.

| Область | Команда / способ запуска | Результат | Тип доказательства |
| --- | --- | --- | --- |
| Compiler | `gradlew.bat --no-daemon :compiler:test :compiler:installDist --rerun-tasks` | 82 JUnit, 0 failures/errors/skips; BUILD SUCCESSFUL | Локальная JVM |
| ARM execution | `python tests/arm_execution.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe"` | 15 passed | Cortex-M4/Unicorn |
| Firmware/runtime | `python tests/firmware_checks.py -v` | 13 passed | Эмуляция/ELF/BIN |
| Diagnostics | `python tests/clab_diagnostics.py -v` | 6 passed | Эмуляция |
| Init diagnostics | `python tests/clab_init_checks.py -v` | 6 passed | Эмуляция |
| PLL recovery | `python tests/clab_recovery_checks.py -v` | 12 passed | Эмуляция, положительные и отрицательные случаи |
| Recovered Blink | `python tests/clab_blink_checks.py -v` | 6 passed | Эмуляция/ELF/BIN |
| Local F407 | `python tests/local_firmware_checks.py -v` | 8 passed | Эмуляция |
| Local F427 | `python tests/local_f427_checks.py -v` | 5 passed | Эмуляция/сохранность образов |
| OLED | `python tests/local_oled_checks.py -v` | 7 passed | Эмуляция/точный framebuffer/ошибки I2C |
| Extension unit/TextMate | В `extensions/vscode`: `node --test test/unit.test.js` | 18 passed, 0 skipped | Node.js + настоящий TextMate/Oniguruma |
| Extension real CLI | В `extensions/vscode`: `node --test test/cli.test.js` | 6 passed | Реальный Java CLI, без мок-компилятора |
| Extension Host | `node test/run-host.js "$codeExe"` | 12 passed | Настоящий VS Code 1.139.1, изолированный профиль |
| Restricted Mode | `node test/run-host.js "$codeExe" --untrusted` | 1 сценарий passed, все 3 команды заблокированы | Настоящий VS Code 1.139.1 |

Итого **197 успешных автоматизированных проверок**: прежние 160 + 18 + 6 + 12 + 1.
Число сценариев не эквивалентно числу независимых аппаратных измерений;
подпроверки внутри тестов отдельно не суммировались.

### Дополнительные проверки артефакта

- `npm ci`/первичная установка: зависимости установлены локально с
  `--ignore-scripts`; lock-файл фиксирует версии. Реально первоначально выполнено
  `npm install --ignore-scripts --no-audit --no-fund --fetch-retries=0 --fetch-timeout=20000`.
- `npm run package:local`: локальная упаковка `@vscode/vsce` 4.0.0 успешна;
  создан `extensions/vscode/build/embedlang-0.1.0.vsix`. Это не релиз.
  Размер 9 721 байт, SHA-256
  `c6bb5a570b4d7edc3635a7d53cc8c6cb2badbc5e9dcaa5ff7e0ceb746637f95b`.
  ZIP-содержимое сверено с runtime-исходниками/грамматикой; tests, node_modules,
  firmware, секреты и логи в пакет не включены.
- Установка VSIX командой `code --user-data-dir "$isolatedProfile" --extensions-dir
  "$isolatedExtensions" --install-extension "$vsix" --force` завершилась с кодом 0.
  `--list-extensions --show-versions` показал `qusaeotoman.embedlang@0.1.0`.
  Обычный профиль/список расширений пользователя не изменялись.
- CLI установки редактора выдал предупреждение Node DEP0169 (`url.parse()`);
  установка завершилась успешно. Это предупреждение инфраструктуры Code CLI,
  не результат проверки или аппаратная ошибка EmbedLang.

Среда: JDK 17, Node.js 24.13.0, npm 11.6.2, установленный VS Code 1.139.1,
Unicorn 2.1.4; ARM GNU 13.3.Rel1 для ARM execution. Dev dependencies расширения:
`@vscode/vsce` 4.0.0, `vscode-textmate` 9.3.2, `vscode-oniguruma` 2.0.1.
Версия движка VS Code в manifest задаёт минимум 1.85, но фактический Host-тест
выполнен на 1.139.1; проверка на минимальной версии и на Linux/macOS не заявляется.

### Что проверено в расширении

Регистрация языка и команд, реальная CLI-диагностика с координатами, astral
Unicode → UTF-16, очистка ошибок после правки/закрытия, сохранение текущего текста,
вывод IR/assembly в отдельные документы, отсутствие частичного вывода при ошибке,
validation-on-save, отсутствие вымышленных source errors при недоступном
компиляторе, отказ для untitled и запрет исполнения в Restricted Mode.
Проверены пути с пробелами/метасимволами, timeout и коды CLI 0/1/2.

### Сохранность и недостающие сведения

Компилятор, AST, IR, ARM backend и firmware source не изменены. Повторная
firmware-регрессия проверяет прежние образы, включая hardware-tested Blink/OLED.
Сама прошивка заново в плату не записывалась. Коммиты `5f8a6b7` и публичный
`feeb729` не заменены текущими изменениями; нового milestone-коммита или
публикации не выполнялось. Личные разделы отчёта остаются незаполненными.
При первоначальном запуске оригинал задания не был найден. После уточнения
пользователем пути к PDF документ идентифицирован и проверен; см. запись ниже.


## Сверка с предоставленным PDF задания — 2026-10-17

Получен указанный пользователем PDF **«ПрВсС_2026_осень_Лекция_1_Практическое
задание.pdf»**: Ключев А. О., ИТМО, 2026, 56 страниц. SHA-256 и библиографические
данные записаны в [ASSIGNMENT_MAPPING.md](ASSIGNMENT_MAPPING.md); персональный
машинный путь в документацию не перенесён.

Проверка документа выполнена локально:

- `pypdf.PdfReader`: извлечён текст всех 56 страниц.
- `pypdfium2.PdfDocument`: страницы 1, 10, 11, 12, 13, 14, 15 и 20 отрендерены
  и визуально прочитаны; номера слайдов/страниц совпадают для используемых ссылок.
- Сопоставлены задания стр. 10, порядок/стек стр. 12–13 и состав отчёта стр. 14–15.
- Подтверждены личные разделы студентов, допустимые технические AI-приложения,
  Markdown/PDF и Git-ссылка. Добавлены выбранные исходные фрагменты с русскими
  пояснениями, не меняющие исходники проекта.
- Матрица отделяет готовое ядро/native firmware и базовый VS Code от ещё не
  выполненных Zed и GDB/gdb-stub/TCP-IP stepping в обоих редакторах. Отдельно
  обозначено отличие local F427 от описанной в лекции конфигурации F407.

Это документальная сверка, **не новый запуск 197 тестов** и не аппаратная проверка.
Число успешных программных проверок остаётся результатом предыдущего запуска
Milestone 6, приведённого выше. В этой сверке исходники компилятора/расширения и
прошивки не изменялись; выполнена проверка Markdown-ссылок, источников выдержек,
отсутствия личных машинных путей и сохранности файла PDF. PDF, извлечённый текст
и изображения страниц остаются вне Git; публикация и новые этапы не выполнялись.

Окончательная формулировка ТЗ, собственное объяснение архитектуры, реальные
AI-запросы, авторские данные и проверка допустимости выбранного инструментария
остаются задачами студентов. Новая матрица не означает полного выполнения
задания или его приёмки преподавателем.

## Zed: компонентная интеграция и повторная регрессия — 2026-10-17

Изменены только editor-adapter, task/configuration, gitignore и документация.
Compiler/frontend/ANTLR/AST/IR/ARM backend, firmware, examples и прежние тесты
не менялись. Работа выполнена без платы, Flash/OpenOCD и удалённой лаборатории.

### Реально выполненные проверки

| Проверка | Команда / способ | Успешно |
| --- | --- | ---: |
| Kotlin compiler | `:compiler:test :compiler:installDist --rerun-tasks` | 82 |
| ARM execution | `tests/arm_execution.py` с GNU assembler/linker и Unicorn | 15 |
| Firmware integration | `tests/firmware_checks.py -v` | 13 |
| cLAB diagnostics | `tests/clab_diagnostics.py -v` | 6 |
| cLAB init | `tests/clab_init_checks.py -v` | 6 |
| Guarded PLL recovery | `tests/clab_recovery_checks.py -v` | 12 |
| Recovered Blink | `tests/clab_blink_checks.py -v` | 6 |
| Local F407 | `tests/local_firmware_checks.py -v` | 8 |
| Local F427 | `tests/local_f427_checks.py -v` | 5 |
| OLED | `tests/local_oled_checks.py -v` | 7 |
| VS Code unit/TextMate | `node --test test/unit.test.js` в extensions/vscode | 18 |
| VS Code real CLI | `node --test test/cli.test.js` | 6 |
| Настоящий VS Code Host | `node test/run-host.js <Code executable>` | 12 |
| Настоящий Restricted Mode | тот же runner с `--untrusted` | 1 |
| Zed grammar/WASM/queries | `npm test` в extensions/zed, grammar.test.js | 14 |
| Zed task + real CLI | тот же запуск, tasks.test.js | 10 |
| **Итого** | **160 + 37 + 24; 0 финальных failures/skips** | **221** |

Дополнительно реальный `node extensions/zed/task.js build` успешно запустил
Gradle `:compiler:installDist` — проверен именно путь, используемый Zed task,
а не только похожая ручная команда. Это не дополнительный unit-тест в сумме.

В первом повторном VS Code Host запуске Java не была передана в environment;
CLI не смог выдать source diagnostics. После явного `JAVA_HOME` на JDK 17
оба изолированных Host запуска прошли. Изменять compiler/extension для этого
не потребовалось. Обычный профиль пользователя не изменялся.

### Сборка реального Zed-парсера

- Node.js 24.13.0; tree-sitter-cli **0.25.10**, web-tree-sitter **0.25.10**,
  lock-файл npm; parser сгенерирован для **ABI 14**.
- Официальные WASI SDK архивы не удалось загрузить полностью; их частичные
  файлы не используются и остаются в игнорируемых tools. Успех SDK-сборки не
  заявляется. Использован portable **Zig 0.13.0**, полученный из pinned
  `ziglang` wheel, SHA-256 проверен по PyPI metadata. Никаких глобальных
  установок/изменений PATH не выполнялось.
- `ZIG=<absolute zig executable>`, `ZIG_GLOBAL_CACHE_DIR=<ignored local cache>`,
  `npm run build`: реальный `zig cc -target wasm32-wasi`, `-fPIC -shared -Os`,
  `-nostdlib`, `--no-entry`, export `tree_sitter_embedlang`. Нужные заголовки
  берутся из portable Zig, C runtime/startup не линкуется.
- Создан ignored пакет `extensions/zed/build/embedlang/`; WASM **13 044 байт**,
  SHA-256 `c1f7ed45b2847f96741d7f811466d862d316f89d4b5b0f2aa27a4fe66de0faa8`.
  Модуль действительно загружен Tree-sitter: все пять `.emb` примеров без
  syntax ERROR; все четыре query-файла компилируются и дают captures.
- Проверены категории подсветки, все actual built-ins из Kotlin, expression
  precedence, восстановление неполного ввода, отсутствие поддержки строк.
- Проверены exports/imports WASM: нет `_start`, импорта `main` или WASI startup.
  При первоначальной сборке Zig добавлял startup; build flags исправлены,
  отдельный тест предотвращает повторение. Исправлен также editor-parser
  конфликт newline после `if` без `else`, обнаруженный на oled_group.emb.
- Linker предупреждает, что `-shared` для WASM пока нестабилен. Сборка успешна,
  компонентные тесты прошли; совместимость с конкретным Zed UI пока не доказана.

### Границы результата и ручная приёмка

Zed не установлен/не найден в этой среде. Не заявляются успешная установка
расширения, визуальная подсветка, работа меню задач, сохранение по `save: current`
или клики по диагностике **в самом Zed**. Проверены исходники, настоящий WASM,
query captures и task runner с реальным компилятором. TOML/JSON и путь загрузки
unpacked package сопоставлены с официальными docs/source Zed. Пошаговая ручная
проверка и локальная установка описаны в extensions/zed/README.md.

Диагностика — терминальная с исходными координатами, не LSP/Problems. Файловые
задачи требуют сохранённый `.emb` внутри worktree. Вывод IR/ASM — ignored build
directory; при ошибке старый успешный артефакт может сохраниться. Сам task
runner и CLI используют аргументы без shell-интерполяции имени source.

Обычный dev-extension builder требует Git-ревизию parser source. Сейчас она
намеренно не выдумана: uncommitted source компилируется в локальный unpacked
пакет, поле `rev` пусто. Gallery/dev-builder install не проверены и не заявляются.
Публикация или новый Git-коммит запрещены пользователем и не выполнялись.

Локальный OLED commit `5f8a6b7` сохранён. Предыдущие незакоммиченные изменения
сохранены. Новые бинарники, зависимости, логи и caches игнорируются; third-party
Tree-sitter notice включён в локальный пакет. GDB/gdb-stub/TCP-IP debugging,
DWARF/source stepping и editor debug adapters остаются отдельной будущей работой.

## Сохранение editor milestone перед Milestone 7 — 2026-10-17

По новому разрешению пользователя выполнен review VS Code/Zed, task runner,
README и русских приложений. Повторно запущены **48 component/CLI проверок**:
18 VS Code unit/TextMate + 6 VS Code CLI + 24 Zed; все прошли, без skips.
Это дополнительный повторный запуск части прежних 221, а не 48 новых тестов.
Прежний полный результат 221 описан выше; он не выдаётся за новый полный прогон.
Zed UI, Problems/LSP и debugging явно остаются незавершёнными.
Исходники компилятора и firmware не менялись. Перед локальным коммитом
проверяются список файлов, ignore rules и известные сигнатуры секретов;
генерированные артефакты и персональные пути не включаются.

## Milestone 7: ELF-аудит и локальный GDB/TCP proof — 2026-10-17

### Граница сохранённого этапа

После review создан локальный коммит
`40fa24276761ee67af803e6741c483f7f6f89a93` —
`Milestone 6: VS Code and Zed editor prototypes and project report`.
В нём 44 reviewed source/document paths; `git status --porcelain` сразу после
коммита пуст. Generated binaries, logs, caches, Flash backups и credentials не
включены; известные secret patterns/персональные Windows paths не обнаружены
в проверенном наборе. Это не абсолютное доказательство отсутствия всех секретов.
Публичный snapshot/remote не изменялся. Новое разрешение пользователя заменило
прежний запрет на этот локальный коммит; на публикацию разрешения нет.

Затем начат Milestone 7. Его новые tools/tests/docs **оставлены незакоммиченными**
для review. Поэтому чистота checkout подтверждена на границе Milestone 6,
а не после создания новых Milestone 7 файлов.

### Выполненные проверки

| Набор | Реальный повторный запуск | Результат |
| --- | --- | ---: |
| Kotlin compiler | `:compiler:test --rerun-tasks`, JDK 17 | 82 passed |
| ARM execution | `tests/arm_execution.py`, GNU as/ld + Unicorn | 15 passed |
| Firmware integration | `tests/firmware_checks.py -v` | 13 passed |
| cLAB diagnostics | `tests/clab_diagnostics.py -v` | 6 passed |
| cLAB init | `tests/clab_init_checks.py -v` | 6 passed |
| Guarded PLL recovery | `tests/clab_recovery_checks.py -v` | 12 passed |
| Recovered Blink | `tests/clab_blink_checks.py -v` | 6 passed |
| Local F407 | `tests/local_firmware_checks.py -v` | 8 passed |
| Local F427 | `tests/local_f427_checks.py -v` | 5 passed |
| OLED | `tests/local_oled_checks.py -v` | 7 passed |
| VS Code unit/TextMate + CLI | сохранение этапа: 18 + 6 | 24 passed |
| VS Code Host | отдельный временный профиль, VS Code 1.139.1 | 12 passed |
| VS Code Restricted Mode | отдельный временный профиль | 1 passed |
| Zed grammar/task | сохранение этапа: настоящий WASM/queries и CLI | 24 passed |
| Новые GDB/RSP | `tests/gdb_connection_checks.py --assembler <as> --linker <ld> --gdb <gdb>` | 8 passed |
| **Всего в текущем цикле** | **221 прежних + 8 новых; без финальных failures/skips** | **229 passed** |

Восемь новых проверок: настоящий ARM GDB/TCP breakpoint/step/register/memory/
result; ELF symbols и assembly-only lines; core target XML и Thumb status;
unmapped/oversize memory reads; отсутствие writes/Flash/monitor; loader entry/
arguments guards; checksum NACK с fragmented TCP request; budget для вечного
виртуального цикла. Подпроверки GDB-команд отдельно в сумму не добавляются.

### Аудит ELF и toolchain

Read-only `tools/debug/inspect_elf.py` выполнен для F427 Blink/OLED, recovered
cLAB Blink, прежнего ARM-execution ELF и нового `build/gdb-poc/probe.elf`.
Подтверждены ARM symbols и `.debug*` для firmware, но `.emb` line files — **0**.
F427 содержит `program.s`; ARM-execution fixture не содержит DWARF. Новый ELF
с `as -g` содержит только generated `probe.s` source. Типы/locals/строки `.emb`
не подменяются C/startup DWARF или именами функций в `.symtab`.

Реально запущен ARM GDB **14.2.90.20240526-git** (ARM GNU 13.3.Rel1);
`set architecture armv7e-m` успешен. `show configuration` сообщает сборку без
Python. Проверка native DAP возвращает **`Interpreter 'dap' unrecognized`**.
Отдельный MI2 процесс успешно обработал `1-gdb-version`, `2-gdb-exit`.
Отсутствие native DAP — конкретный blocker для прямого GDB-DAP варианта Zed;
MI/DAP bridge либо иной ARM GDB ещё предстоит выбрать и проверить.

### Доказательство исполнения

Compile: текущий Java CLI → diagnostic_probe.emb → Thumb assembly.
Build: GNU assembler `-mcpu=cortex-m4 -mthumb -g`, linker `-Ttext=0x10000`.
Target: Unicorn **2.1.4**, synthetic stack, один TCP client на **127.0.0.1**.
GDB достиг generated function breakpoint, наблюдал r0=6/r1=7, выполнил `stepi`,
читал core registers/disassembly/stack и дошёл до r0=42, SP=0x20010000.
Финальные маркеры: `BREAKPOINT_ARGUMENTS_OK`, `INSTRUCTION_STEP_OK`,
`RESULT=42`, `RETURN_AND_STACK_OK`. Инструкции исполняются реальным Unicorn CPU
engine; ответы не являются заранее подготовленным transcript.

GDB этой Windows-сборки выдаёт CP1252/UTF-32 warning; возможен warning о времени
generated assembly. Попытка принудительного UTF-8 не поддержана и удалена из
recipe; финальный запуск без неё проходит. Поддержка Unicode source paths не
подтверждена. Эти предупреждения и raw logs остаются в ignored build/tools.

### Что не выполнено

Не запускались плата, OpenOCD, QEMU или debug UI обоих редакторов. Нет `.emb`
source stepping, typed local inspection, проверенного полного unwind, FPB/
watchpoint/interrupt/peripheral simulation. Нет editor DAP registrations или
автоматической загрузки/сброса firmware. Порт RSP не является портом DAP.
Compiler/frontend/IR/ARM backend/firmware и runtime-функции не менялись.
План следующих проверок и ограничения PoC — в [GDB_DEBUGGING.md](../GDB_DEBUGGING.md).
При review инструкции Zed уточнено: одного `rev` недостаточно для dev builder —
в pinned revision должны быть generated parser C/headers, сейчас игнорируемые.
Текущий прототип использует unpacked package; оба UI-пути не проверены в Zed.

## Milestone 7: минимальная `.emb` source-line отладка — 2026-10-17

### Сохранение предыдущего PoC

Перед изменением компилятора повторно запущены 8 GDB/RSP проверок, все прошли.
После review 11 source/document files, проверки ignore rules, известных secret
signatures/персональных путей и `git diff --check` создан локальный коммит
**`848a38ecbd6ee445cdf12db95b97e3b47f0bcc4a`**, сообщение
`Milestone 7: local GDB TCP RSP proof of concept`. Сразу после него
`git status --porcelain` пуст. История `40fa242` и аппаратных milestone сохранена;
публикации нет. Новая source-line работа ниже пока не закоммичена.

### Изменение и проверенная граница

До реализации объяснён opt-in `--emit-asm --debug-lines` и параметр
`ArmBackend.emit(program, debugLines = true)`. Переиспользованы существующие
IR SourceLocation, parser/AST/IR не менялись. Добавлены `.file` с безопасными
C/UTF-8 octal escapes и `.loc` original line/column. Function setup/teardown и
generated branches помечаются `is_stmt 0` на реальных function/control lines;
выражения остаются в пределах statement mapping. Runtime/firmware и frame ABI
не менялись, typed locals/parameters/CFI не добавлены.

### Реально выполненная регрессия

| Проверка | Команда / среда | Passed |
| --- | --- | ---: |
| Kotlin + CLI, включая 7 новых | Gradle `:compiler:test :compiler:installDist`, JDK 17 | 89 |
| ARM execution | tests/arm_execution.py, GNU as/ld + Unicorn | 15 |
| Firmware integration | tests/firmware_checks.py -v | 13 |
| cLAB diagnostics | tests/clab_diagnostics.py -v | 6 |
| cLAB initialization | tests/clab_init_checks.py -v | 6 |
| Guarded PLL recovery | tests/clab_recovery_checks.py -v | 12 |
| Recovered Blink | tests/clab_blink_checks.py -v | 6 |
| Local F407 | tests/local_firmware_checks.py -v | 8 |
| Local F427 | tests/local_f427_checks.py -v | 5 |
| OLED | tests/local_oled_checks.py -v | 7 |
| VS Code unit/TextMate | node --test extensions/vscode/test/unit.test.js | 18 |
| VS Code real CLI | node --test extensions/vscode/test/cli.test.js | 6 |
| Zed parser/queries/tasks | node --test extensions/zed/test/*.test.js | 24 |
| Настоящий VS Code Host | isolated profile, test/run-host.js, 1.139.1 | 12 |
| Restricted Mode | отдельный isolated profile, --untrusted | 1 |
| Прежний GDB/RSP | tests/gdb_connection_checks.py с реальным ARM GDB | 8 |
| Новые ELF/source GDB | tests/source_debug_checks.py с GNU as/ld/GDB | 5 |
| **Итого** | **229 прежних + 7 Kotlin/CLI + 5 ELF/GDB; финальных failures/skips нет** | **241** |

Первый Gradle прогон выполнен с `--rerun-tasks`; после исправления mapping и
UTF-8 escaping полный Kotlin test task выполнен снова, 89 tests подтверждены
JUnit XML. Остальные наборы запущены после установки финального компилятора.
Среда: ARM GNU 13.3.Rel1 / GDB 14.2.90, Unicorn 2.1.4, pyelftools 0.33,
Node.js 24.13.0. Старые firmware образы не перезаписывались и проверены
существующими сохранностными/эмуляционными тестами. Ни один тест не обращается к плате.

### Доказательство source-level результата

Фактический input — копия tests/fixtures/source_debug.emb в пути с пробелами и
`&`, переданном CLI относительно repository cwd. GNU assembler выполняется
из другого cwd, с `-g --gdwarf-4`; получен `build/source-debug/mapped.elf`.
Pyelftools подтверждает original absolute `.emb` path и statement rows
**2, 3, 4, 5, 6, 10**, column 5; function rows 1 и 9 — non-statement.
Mapped/plain `.text` побайтно совпадают для этого probe и большого ARM fixture
с arithmetic, comparisons, loops, calls и short-circuit операциями.

Настоящий ARM GDB подключается к существующему Unicorn RSP на 127.0.0.1;
breakpoint задан полным **source_debug.emb:2**. Затем четыре команды **`step`**
дают строки **3 → 4 → 5 → 6**. После каждого PC выполнен и проверен GDB
`info line *$pc`. Начала этих line ranges: 0x1000c, 0x10012, 0x10018, 0x10030,
0x10046. После continue достигнут **SOURCE_RESULT=42 SP=0x20010000**.
Это source-line proof в локальной CPU эмуляции, не аппаратное наблюдение и не
результат debug UI редактора.

### Обнаруженные и явно оставленные ограничения

- Первоначальные `.loc` с line 0 GNU assembler не сохранял в line table; это
  обнаружил ELF-тест. Исправлено: реальные function/control lines + is_stmt 0.
- Native/file encoding доступного JDK — **Cp1251**. Некоторые Unicode argv
  filenames (Ω, é) превращаются в `?` ещё до source loading. Системные настройки
  не менялись. Отдельный Java API test bridge получает base64 ASCII path,
  читает реальный source_Ω.emb и подтверждает UTF-8 filename в ELF. Это **не**
  доказательство произвольных Unicode CLI/GDB путей. Direct API/UTF-8 metadata
  и обычный CLI file:line workflow проверены раздельно.
- Нет typed local-variable debugging, полноценного unwind, `next`/`finish`
  через calls, всех source control-flow сценариев или editor DAP integration.
  Native DAP в доступном ARM GDB по-прежнему отсутствует. Возможен прежний
  Windows GDB warning о времени generated source; финальные assertions проходят.
- Ранее построенные hardware ELF сохраняют прежнюю debug metadata; их не
  пересобирали в opt-in режиме. Нового hardware execution/flash не было.

Generated ELF/objects/assembly/logs/GDB scripts и result JSON остаются ignored
в build/source-debug и .tools. Подробности и команды —
[SOURCE_DEBUGGING.md](../SOURCE_DEBUGGING.md). Личные разделы студентов сохранены.

## VS Code DAP/MI2: реальный editor Host, 2026-10-17

По запросу пользователя проверен diff source-line milestone, повторены 5 ELF/GDB
проверок, выполнены review состава файлов и проверка секретов/артефактов.
Создан коммит **87807cefcb7eb96445ab79cb8f5c162a53ef5681**; checkout сразу после
него чист. Новая VS Code интеграция далее остаётся **незакоммиченной** для review.

### Финальная регрессия

| Набор | Успешно |
| --- | ---: |
| Kotlin/CLI, Gradle :compiler:test --rerun-tasks, JDK 17 | 89 |
| ARM execution, GNU as/ld + Unicorn | 15 |
| Firmware integration | 13 |
| cLAB diagnostics / initialization / PLL recovery / Blink | 6 + 6 + 12 + 6 |
| Local F407 / F427 / OLED | 8 + 5 + 7 |
| VS Code unit/TextMate + новые debug unit | 18 + 3 |
| VS Code настоящий compiler CLI | 6 |
| Zed parser/query/task component tests | 24 |
| VS Code основной Host / Restricted Mode | 12 + 1 |
| GDB/RSP, включая новый interrupt test | 9 |
| ELF/source GDB | 5 |
| Новый настоящий VS Code debug Host | 8 |
| **Всего; failures/skips нет** | **253** |

Gradle завершился BUILD SUCCESSFUL; 89 tests подтверждены JUnit XML. Все Python
наборы завершились OK, ARM execution — 15 passed. Node aggregate дал 51 passed;
два прежних Host дали 12 и 1; новый debug Host — 8. Компилятор/AST/IR/backend и
firmware исходники в этом цикле не менялись. Hardware preservation/integration
tests являются локальными проверками и эмуляцией, не новым испытанием на плате.

### Что выполнено в настоящем редакторе

Среда: VS Code **1.139.1**, установленный **marus25.cortex-debug 1.12.1**,
ARM GNU 13.3.Rel1 / GDB 14.2.90, Unicorn 2.1.4. Adapter установлен отдельно в
ignored `.tools/cortex-debug/extensions`; тесты используют временный профиль и
workspace. Обычные пользовательские настройки VS Code не менялись.

1. Активирован реальный поддерживаемый adapter; EmbedLang command построила ELF
   и создала DAP/MI2 session с TCP target на 127.0.0.1.
2. Настоящий `setBreakpoints` подтвердил source breakpoint `.emb:2`; достигнуты
   правильные DAP source path/line и выделенная строка исходника в editor API.
3. Проверены текущий stack frame/instruction pointer, `read-registers` с r0 и
   DAP `disassemble` с настоящими ARM instructions.
4. **Workbench Step Into** четыре раза остановился на `.emb` строках 3, 4, 5, 6;
   проверены DAP frame и фактическое положение source editor после каждого шага.
5. **Workbench Continue** завершил fixture: `$r0=42`, `$sp=0x20010000`.
6. Stop завершил сессию; порт owned target перестал принимать соединения.
7. Второй generated loop fixture проверил **Workbench Continue/Pause/resume/Pause**.
   Это отдельная программа, потому что арифметический fixture завершается слишком
   быстро для надёжного интерактивного Pause.

Первый пробный запуск выявил отсутствующее `servertype: external`; конфигурация
исправлена, финальные прогоны прошли. Существующие Windows GDB encoding/mtime и
Code Node deprecation warnings не выдаются за ошибки или hardware evidence.
Нет typed locals, надёжного полного unwind, Step Over/Out через calls или Zed
debugging. Нет личной визуальной приёмки; подтверждены реальные editor API,
workbench controls и DAP/GDB results, а не только JSON-конфигурация.

Репродукция: [guide](../VSCODE_DEBUGGING.md). `.tools` install/logs, build ELF,
VSIX и временные profiles исключены из Git. Плата/OpenOCD не использовались;
публикации и загрузки firmware не выполнялись. Личные разделы отчёта сохранены.

Локальная упаковка `npm run package:local` также успешна: VSIX содержит 10 файлов,
включая три runtime JS-модуля расширения и compiler adapter. Тесты, node_modules,
установленный Cortex-Debug, firmware, ELF и machine-specific configs в пакет не
включены. VSIX остаётся ignored локальным артефактом, не опубликованным release.
После обновления npm test entry повторены 21 unit/TextMate/debug unit: все passed;
это повтор уже учтённых проверок, а не увеличение итога 253.

## Zed debugger: возобновление, API/WASM и DAP, 2026-10-18

Сохранённый VS Code этап — **b4bd308d56685035d35267241c5fbc2fb41aba33**.
При возобновлении проверены существующие `.gitignore`, debug.js, Rust extension,
schema и DAP tests; они сохранены, успешная реализация не заменялась. Новая Zed
работа остаётся **незакоммиченной и не опубликована**. Личные разделы сохранены.

### Rust download и настоящий build

Перед прерыванием stable toolchain downloads задержались. Лог pinned установки
подтвердил завершение **Rust 1.90.0 (1159e78c4 2025-09-14), Windows GNU host**;
блокера download больше нет. Система PATH не менялась: RUSTUP_HOME/CARGO_HOME и
PATH задавались только локальному процессу в ignored `.tools/zed-debug`.

Выполнены команды (из root; для обычного native host суффикс GNU не нужен):

```text
cargo +1.90.0-x86_64-pc-windows-gnu build --manifest-path extensions/zed/debugger/Cargo.toml --target wasm32-wasip1 --release
cargo +1.90.0-x86_64-pc-windows-gnu test --locked --manifest-path extensions/zed/debugger/Cargo.toml
node extensions/zed/debugger/package.js
```

Release build завершён успешно, без compile errors; использована настоящая
published crate **zed_extension_api 0.7.0**, закреплённая в Cargo.toml/Cargo.lock.
Rust tests: **2 passed**, без failures/ignored. Модуль
`extensions/zed/debugger/target/wasm32-wasip1/release/embedlang_debugger.wasm`:
**183 541 байт**, SHA-256
`6ff06318fccad65c26d4a825bcece44554f80e694e152ef4c2b5f88b3f55e641`.
Node WebAssembly parser подтвердил реальные exports `init-extension`,
`get-dap-binary`, `dap-request-kind` и custom section `zed:api-version`
с байтами **00 00 00 07 00 00**. Это проверка build/API metadata, **не загрузка
модуля в Zed runtime**. Упакован локальный ignored каталог
`extensions/zed/build/embedlang-debugger` с WASM, manifest, schema и attribution.

### DAP startup, paths, execution и cleanup

Adapter закреплён в npm lockfile: **cdt-gdb-adapter 1.10.0**. Его standalone
`dist/debugTargetAdapter.js`, а не VS Code extension, реально запущен тестами.
При локальной установке отключены install scripts; native GDB console не нужна.
Старый `npm test` Zed оставлен для прежних parser/task тестов, новый suite —
`npm run test:debug`, проверка модуля — `npm run test:wasm`.

```text
node --test extensions/zed/test/debug.test.js extensions/zed/test/wasm.test.js
node extensions/zed/debug.js tests/fixtures/source_debug.emb
```

Для этих команд заданы абсолютные локальные `EMBEDLANG_ARM_BIN`,
`EMBEDLANG_PYTHON`, `EMBEDLANG_CDT_ADAPTER`; optional Python modules —
`EMBEDLANG_PYTHON_MODULES`. Пути не записаны в отчёт/Git; полная инструкция в guide.

Итог Node suite — **8 passed**: 4 configuration/manifest checks, 3 реальных
CDT/GDB/TCP сценария и 1 compiled-WASM check. В этих сценариях подтверждены:

- Старт Node/CDT → ARM GDB/MI → Python/Unicorn, ephemeral **127.0.0.1** RSP port.
  DAP использует stdio; RSP не подменяется Zed TCP DAP transport.
- Verified `.emb:2` breakpoint с **абсолютным source path, пробелами и `&`**;
  реальные `stepIn` с granularity line дают строки **3, 4, 5, 6**.
- Полезный текущий frame/source/PC, стандартный DAP Register scope/variables и
  `disassemble`; после continue **$r0=42**, **$sp=0x20010000**. Evaluate использует
  frameId, требуемый CDT. Typed locals этим не доказываются.
- Отдельный generated loop дважды проходит Continue/Pause/resume/Pause и
  останавливается в нужном `.emb` файле.
- Disconnect/terminated закрывает порт owned Unicorn target. Failed Python
  startup возвращает launch error; тест не считает его успешной сессией.
- `run: preserve` сохраняет initial stop; config не содержит load/monitor/reset
  scripts. Helper сохраняет чужой debug.json, отклоняет относительные machine paths.

Preparation действительно построила ELF и создала ignored `.zed/debug.json`;
проверены local launch, наличие ELF и machine paths. Генерация не запускала Zed
или target. Никакой source/firmware файл не перезаписан. Пакет и license notices
локальные; публичный binary release потребует полного transitive license bundle.

### Полная регрессия после возобновления

| Набор | Успешно |
| --- | ---: |
| Kotlin/CLI, Gradle :compiler:test --rerun-tasks, JDK 17 | 89 |
| ARM execution | 15 |
| Firmware integration | 13 |
| cLAB diagnostics / initialization / guarded PLL / Blink | 6 + 6 + 12 + 6 |
| Local F407 / F427 / OLED | 8 + 5 + 7 |
| VS Code unit/TextMate/local-debug unit | 18 + 3 |
| VS Code compiler CLI | 6 |
| Zed parser/query/task component tests | 24 |
| Настоящий VS Code Host / Restricted Mode | 12 + 1 |
| Прежний GDB/RSP / ELF source GDB | 9 + 5 |
| Настоящий VS Code Cortex-Debug Host | 8 |
| Новые Zed DAP/configuration | 7 |
| Compiled WASM exports/API metadata | 1 |
| Rust API glue unit tests | 2 |
| **Итого; failures/skips нет** | **263** |

Gradle BUILD SUCCESSFUL, 89 tests подтверждены JUnit XML; Python-наборы OK,
ARM execution 15 passed. Node editor aggregate 51 passed. Основной реальный
VS Code Host — 12, Restricted Mode — 1, Cortex-Debug Host — 8 на версии 1.139.1.
Старые firmware/OLED сохранены локальными preservation/emulation tests; это не
повтор аппаратных наблюдений. Компилятор, firmware и VS Code sources не изменены.

### Что НЕ проверено

**Zed не установлен и не запускался**. Нет доказательства extension loading,
gutter breakpoints, source navigation, кнопок, стека/Register/disassembly UI или
их удобства. WASM/API compile и DAP tests не выдаются за in-editor acceptance.
Typed locals/parameters, полный unwind, arbitrary control-flow mapping и Step
Over/Out через calls остаются неполными. Unicode CLI path limitation Cp1251
сохранена. Никаких STM32/Flash/OpenOCD/remote lab действий не было.

Ручная установка и точный checklist — [ZED_DEBUGGING.md](../ZED_DEBUGGING.md).
Generated WASM/ELF/JSON/logs, profiles, toolchains и node_modules остаются ignored.
Новый коммит и публикация не выполнялись; исходники готовы для review, UI-приёмка
остаётся отдельной обязательной проверкой.

## Финальный review, Git и проверка наличия Zed, 2026-10-18

1. Проверены исходники/manifest/schema/lockfiles и состав diff. `git diff --check`
   чист; известные secret signatures и персональные абсолютные пути не найдены.
   WASM/ELF/logs/node_modules/.zed/debug.json остаются ignored; в staged files
   отсутствуют бинарники, backups, credentials и machine configuration.
2. Повторены **8 Node DAP/configuration/WASM + 2 Rust tests**, все passed, без
   failures/skips. Это повтор части ранее подтверждённых **263 checks**, а не
   новый полный прогон и не увеличение числа уникальных тестов.
3. Создан локальный commit **cca8b36cf34ac0e334ec2a7d4300ca8328e0a629**,
   `Milestone 7: Zed DAP debugging integration`. Сразу после него porcelain status
   пуст. Compiler/firmware/VS Code sources не менялись.
4. **После коммита** read-only проверены `Get-Command zed,zed.exe`, стандартные
   executable locations LocalAppData/Program Files/WinGet links, HKCU/HKLM
   uninstall records (включая WOW6432Node), `Get-Process -Name zed`. Совпадений
   нет. Это не исключает portable binary в неизвестном пользовательском каталоге.
   Winget найден. Списки прочих приложений/персональные machine paths не сохранены
   в отчёт и Git.
5. Installer и Zed **не запускались**, дополнительных пакетов не установлено.
   UI acceptance не выполнялась; разрешение на установку запрашивается отдельно,
   как прямо требует пользователь. Официальная Windows команда и точные ручные
   проверки добавлены в [ZED_DEBUGGING.md](../ZED_DEBUGGING.md).

Новых UI/hardware результатов нет. Последующие docs-изменения фиксируются отдельно,
чтобы итоговый working tree остался чистым; публикация/GitHub push не выполняется.

## Реальная приёмка Zed Windows и исправление WASM, 2026-10-18

Эта запись продолжает историю выше, а не заменяет старые результаты. **На момент
коммита cca8b36 настоящий Zed UI не проверялся.** После отдельного разрешения
пользователя выполнена установка официального stable-пакета:

```powershell
winget install -e --id ZedIndustries.Zed --accept-source-agreements --accept-package-agreements
```

Предварительная попытка `--scope user` вернула `No applicable installer found`.
Официальный manifest декларировал machine scope; пользователь отдельно разрешил
его и возможный UAC. Winget проверил installer hash и завершил установку.
Версия CLI — **Zed 1.24.2**, commit
`fb69067729cb16a7f6135e2c1600c26a28c59659`. Пакеты EmbedLang установлены только
в отдельный ignored профиль `--user-data-dir`; обычный профиль не перезаписан.
Project trust подтвердил пользователь, только для EmbedLang.

### Найденный дефект и проверенная сборка

Первый реальный запуск отклонил прежний core WASM:
`attempted to parse a wasm module with a component parser`. Старый тест exports/API
и успешная компиляция wasip1 не доказывали runtime-совместимость. Исследован
официальный `crates/extension/src/extension_builder.rs` тега **v1.24.2**: он
использует **wasm32-wasip2**. Изменены только target, упаковка и её тесты;
язык/compiler/AST/IR/ARM/backend/firmware не менялись.

В существующий приватный Rust 1.90.0 GNU toolchain установлен нужный std target.
Из-за медленного загрузчика архив получен с официального static.rust-lang.org
частями и проверен по checksum Rustup; сторонние системные инструменты не ставились.

```powershell
cargo +1.90.0-x86_64-pc-windows-gnu build --locked --manifest-path extensions/zed/debugger/Cargo.toml --target wasm32-wasip2 --release
node extensions/zed/debugger/package.js
cargo +1.90.0-x86_64-pc-windows-gnu test --locked --manifest-path extensions/zed/debugger/Cargo.toml
node --test extensions/zed/test/debug.test.js extensions/zed/test/wasm.test.js
```

Release build успешен. Component — **206 091 байт**, SHA-256
`d3a3b865c1370027c37ae9345d83f829fa2bbd43fca14550dad7c30509117a43`.
Сверены component header, вложенные debugger exports и API 0.7.0. Новый regression
test отвергает core module. Исправленный пакет действительно загрузился в Zed
и запустил CDT/GDB; это отдельное доказательство от статической проверки WASM.

### Наблюдения в настоящем редакторе

| Проверка | Фактический результат |
| --- | --- |
| Два отдельных unpacked extension | Editing определяет EmbedLang, debugger регистрирует/запускает сценарий; оба работают в одном изолированном профиле |
| Подсветка и скобки | Видны разные цвета keywords/types/numbers, выделяется пара `{`/`}` функции; автоматическая вставка не установлена UI helper |
| Tasks | Picker показывает Build/Validate/IR/ASM; Validate действительно выполнен: `2 functions checked`, finished successfully. Остальные task-команды отдельно в UI не запускались |
| Source breakpoint | F9 на строке 2 даёт красный gutter marker; Continue останавливается на `source_debug.emb:2`. Mouse gutter-click отдельно не подтверждён |
| Source stepping | Четыре Step Into последовательно выделяют строки **3, 4, 5, 6** |
| Stack/registers | Видны source-probe/main frames и Register scope; `r0=0x2a`. Это не доказательство полного unwind или typed locals |
| Disassembly | Console `>x/5i $pc` показывает ARM instructions; отдельная disassembly-панель не найдена |
| Return | Continue достигает synthetic sentinel `0x90000`/SIGTRAP; после выбора верхнего `??` frame Console показывает **$r0=42**, **$sp=0x20010000** |
| Pause/resume | Отдельный generated loop: Continue → Pause → Continue → Pause; обе остановки на `pause.emb:3`, сигнал SIGINT |
| Cleanup | Stop: `gdb exited`, `gdbserver exited with code 0`, `gdbserver stopped`; owned PID исчезли. Зафиксированный RSP port после Stop вернул ECONNREFUSED |

Unmapped sentinel иногда оставляет предыдущую source line выбранной; для
evaluation нужен текущий top frame. Обнаружены нефатальные CDT/Zed completion
ошибки (`null` вместо CompletionsResponse) и Windows GDB character-set warning
при неполном console input; явные выражения и команды отработали. Это ограничения,
а не скрытые успешные проверки. Restart, Step Over/Out через calls, автозакрытие,
outline и clickable terminal diagnostics не объявляются проверенными в UI.

### Повтор всей автоматизированной регрессии

Команды выполнены из корня; JDK 17, ARM GNU 13.3.Rel1, Python/Unicorn 2.1.4,
Node 24.13.0, private Rust 1.90.0. Персональные абсолютные пути задавались только
локальными environment variables. Использованы существующие сохранённые firmware
fixtures; тесты не обращаются к плате.

| Набор | Passed |
| --- | ---: |
| `:compiler:test --rerun-tasks`, JUnit XML | 89 |
| `tests/arm_execution.py --assembler … --linker …` | 15 |
| `source_debug_checks.py` / `gdb_connection_checks.py`, flags `--assembler --linker --gdb` | 5 + 9 |
| `firmware_checks.py` | 13 |
| `clab_diagnostics.py` / `clab_init_checks.py` / `clab_recovery_checks.py` / `clab_blink_checks.py` | 6 + 6 + 12 + 6 |
| `local_firmware_checks.py` / `local_f427_checks.py` / `local_oled_checks.py` | 8 + 5 + 7 |
| Node aggregate: VS Code unit/local-debug/CLI, Zed grammar/tasks/DAP/component | 60 |
| Actual VS Code Host / Restricted / Cortex-Debug Host | 12 + 1 + 8 |
| Rust API unit tests | 2 |
| **Всего, failures/skips нет** | **264** |

Node aggregate запускал `node --test` для `extensions/vscode/test/{unit,local-debug,cli}.test.js`
и `extensions/zed/test/{grammar,tasks,debug,wasm}.test.js`. Host-команды:
`run-host.js <Code.exe>`, затем `--untrusted`, `run-debug-host.js <Code.exe> <isolated-adapters>`.
Gradle сначала не смог использовать default cache, затем sandbox запретил чтение
существующего dependency JAR; вне sandbox с приватным GRADLE_USER_HOME — BUILD
SUCCESSFUL, 89 tests. Аналогично sandbox не дал Electron стартовать; повтор
изолированных Host tests вне sandbox завершился успешно. Исходники для обхода
этих ограничений не менялись. UI-наблюдения не добавлены к числу unit tests.

Предыдущие 263 checks сохранены как исторический результат; **264 = 263 + новый
core-WASM rejection test**. Не заявляется новая аппаратная проверка. Нет Flash,
OpenOCD, remote lab, driver changes или публикации. Новые source/docs изменения
намеренно **не закоммичены**; generated installers/WASM/ELF/logs/profiles остаются ignored.

## Финальный review перед сохранением Zed UI, 2026-10-18

По новому разрешению пользователя проверены изменения упаковки/target, component
inspector, regression tests, English guides и русские приложения. Повторены
**33 Node tests** (`debug`, `wasm`, `grammar`, `tasks`) и **2 Rust unit tests**:
**35 passed**, failures/skips нет. Locked release build `wasm32-wasip2` и повторная
упаковка успешны. Проверены сохранённые component SHA-256 и API 0.7.0. Это повтор
релевантной части прежних 264, а не новый полный прогон и не 35 новых тестов.
UI и аппаратные испытания повторно не запускались. Компилятор/firmware не менялись.

`git diff --check`, состав staged files и secret signatures проверяются перед
локальной фиксацией. В коммит входят только source/tests/docs: без generated
WASM/ELF/BIN, logs, backup, installers, user profiles и machine config. Записи выше
«без коммита» относятся к моменту UI review; этот этап теперь сохраняется отдельным
разрешённым локальным коммитом. Публикация и доступ к оборудованию не выполняются.

## Сохранение Zed UI и итоговый документальный аудит, 2026-10-18

1. Staged 12 source/tests/docs файлов. `git diff --cached --check` прошёл;
   secret/private-key/token и personal absolute-path signatures не обнаружены.
   Generated artifacts/backup/logs/installers/profiles не staged.
2. Создан **854c413a1558a5d2168f3979637310aa78928e89**,
   `Milestone 7: verified Zed UI and WASI component packaging`.
   Непосредственно после коммита `git status --porcelain` пуст. Нового push нет.
3. Повторно проверен исходный PDF: 56 страниц, 16 091 739 байт, SHA-256 совпадает
   с прежней идентификацией. Pypdf извлёк все страницы, визуально сверены 10–15.
   Исходник, локальные рендеры и text extraction не включены в Git.
4. Подготовлен [FINAL_COMPLIANCE_AUDIT.md](FINAL_COMPLIANCE_AUDIT.md): отдельные
   функциональные/технологические/авторские/AI-documentation пункты, optional
   improvements, CubeIDE ambiguity и P0/P1/P2 checklist. Это не новая формальная
   приёмка преподавателем. Личные разделы и реальные промпты не заполнялись.
5. Сверены существующие hardware report/source excerpts и текущие limitations.
   Исправлены stale AI-summary абзацы REPORT §8/APPENDICES E; исторические записи
   о раннем отсутствии Zed сохранены и явно обозначены как история.
6. Существующая публичная source-копия имеет initial commit `feeb72965b136fdd7a9cc3f4f310719aaecc47cd`.
   Попытка read-only web-проверки GitHub получила fetch/cache error, поэтому
   remote HEAD и доступность не заявляются проверенными заново. Перед сдачей
   требуется согласовать доступную ревизию; никаких публикаций не выполнено.
7. Все **114** локальных Markdown link targets отчётного каталога существуют;
   `git diff --check` чист. Read-only проверка **78 vendor hashes** прошла после
   задания существующих local Python dependency paths (первый import без них
   сообщил отсутствующий elftools; новые пакеты не устанавливались). CPU ELF
   восстановлен для `tests/fixtures/source_debug.emb`, чтобы конфигурация после
   DAP loop tests снова соответствовала arithmetic fixture. Это не firmware build
   или аппаратное действие. Эти проверки не добавлены к числу unit tests.

В этом цикле повторены только **35 релевантных checks**, успешные build/package;
предшествующая полная регрессия остаётся **264**. Новых аппаратных/UI-запусков
не было. Audit/docs изменения после 854c413 оставлены **без коммита** для review.

## Разрешённое обновление public source edition, 2026-10-18

После отдельного запроса пользователя подготовлен export проверенной 854c413 и
последующих reviewed audit/docs изменений в отдельный public checkout. Приватная
Git-история не переносится; parent — существующий public main feeb729.
Все шесть лицензируемых исключений и 72-file vendor manifest сохранены.

Против экспортированных public sources реально повторены **253 passed**, zero
failures: compiler 89; ARM 15; GDB/RSP/source 9+5; Node editors/DAP/WASM 60;
настоящий VS Code Host/Restricted/debug 12+1+8; Rust 2; firmware 52. В firmware
53 executed, 1 optional official-reference comparison skipped. Три проверки
старых private manifests/точных hardware BIN исключены явным public runner;
семь OLED firmware checks не запускались без исключённых OLED/font sources.
Это не 264 на public clone и не новые аппаратные наблюдения.

Собраны оба Zed WASM-пакета и девять firmware profiles; ELF/BIN verification
успешны. Проверено ожидаемое отклонение OLED build без драйвера. Fresh diagnostic
BIN имеет иной hash из-за build-location `__FILE__`; исходные hardware hashes
и assertions не изменены. Подробные команды/границы —
[PUBLICATION_NOTES.md](../../PUBLICATION_NOTES.md). Existing cached tools/modules
переиспользованы только в ignored directories; системные tools не устанавливались.

Первые попытки Rust linker/VS Code harness потребовали обычного доступа вне
sandbox и подготовки ignored directories; повторные команды завершились успешно.
Для grammar использован проверенный Zig, а не неполная локальная wasi-sdk копия.
Реальный Zed UI повторно не запускался, старый UI result обозначен отдельно.
Student-authored sections не заполнены; board/Flash/driver operations отсутствуют.
