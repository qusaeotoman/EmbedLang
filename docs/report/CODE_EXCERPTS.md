# Избранные исходные фрагменты с русскими пояснениями

**AI-приложение к требованию стр. 15 лекции.** Это не личный текст студентов.
Фрагменты извлечены из текущих файлов проекта; русские поясняющие комментарии
добавлены только в Markdown-приложении. Исходники компилятора/расширения и
язык не изменены. Фрагменты не заявляются как самостоятельные сборочные единицы.
Полные тесты относятся к проекту, а не к отдельной компиляции этих выдержек.

## 1. Координаты исходного текста

Источник: [Ast.kt](../../compiler/src/main/kotlin/embedlang/ast/Ast.kt).
В CLI строки и колонки начинаются с единицы. Адаптер VS Code преобразует
колонки code points в UTF-16 и индексацию с нуля.

```kotlin
// Место ошибки относится к исходному EmbedLang-файлу, а не к generated Java.
data class SourceLocation(val file: String, val line: Int, val column: Int) {
    override fun toString() = "$file:$line:$column"
}
```

## 2. Понижение после успешной проверки типов

Источник: [IrLowerer.kt](../../compiler/src/main/kotlin/embedlang/ir/IrLowerer.kt).
Функция получает уже проверенное представление; IR lowering не должен
повторно угадывать типы или продолжать после семантической ошибки.

```kotlin
// Перед созданием IR требуется успешный результат семантического анализа.
    fun lower(analysis: TypedAnalysisResult): IrProgram {
        require(analysis.isSuccess) { "Cannot lower a program with semantic errors" }
        return Lowering(analysis).lower()
    }
```

## 3. Запуск готового CLI из редактора без shell

Источник: [compiler.js](../../extensions/vscode/src/compiler.js).
Аргументы передаются массивом: пробелы и shell-метасимволы в пути не становятся
командами. Ошибки запуска/timeout отделены от кодов CLI с source diagnostics.

```javascript
// Выполняется существующий Java CLI; расширение само не компилирует язык.
function runCompiler(spec, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    // No shell and no .bat interpolation: spaces and shell metacharacters stay arguments.
    execFile(spec.executable, spec.args, {
      cwd: spec.cwd, timeout: timeoutMs, maxBuffer: 4 * 1024 * 1024,
      windowsHide: true, encoding: 'utf8', shell: false
    }, (error, stdout, stderr) => {
      if (error && (typeof error.code !== 'number' || error.killed)) {
        reject(new Error(error.killed ? 'EmbedLang compiler timed out.' : `Cannot run EmbedLang: ${error.message}`));
      } else resolve({ code: error ? error.code : 0, stdout, stderr });
    });
  });
}
```

## 4. Прикладная программа для проверки ABI и арифметики

Источник: [diagnostic_probe.emb](../../examples/diagnostic_probe.emb).
Физическое возвращение 42 ранее подтверждено пользователем через cLAB;
новой аппаратной проверки в текущем документальном этапе не было. В том
диагностическом firmware C-wrapper вызывает diagnostic_probe(6, 7) и проверяет
возвращаемое значение; обычный main ниже — самостоятельный языковой пример.

```text
// Аргументы, умножение и возврат используют тип u32 и существующее ARM ABI.
// Pure arithmetic: validates arguments, return value and the C-to-EmbedLang ABI.
fn diagnostic_probe(a: u32, b: u32) -> u32 {
    let result: u32 = a * b
    return result
}

fn main() -> void {
    let answer: u32 = diagnostic_probe(6, 7)
}
```

Эти выдержки помогают проверять объяснение студентов, но не заменяют
обязательный личный раздел «Архитектура» и не описывают вымышленный ручной вклад.
