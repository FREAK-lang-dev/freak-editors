const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { Registry, parseRawGrammar } = require('vscode-textmate');
const oniguruma = require('vscode-oniguruma');

(async () => {
  await oniguruma.loadWASM(fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm')).buffer);
  const file = path.join(__dirname, '../vscode/freak-lang/syntaxes/freak.tmLanguage.json');
  const registry = new Registry({
    onigLib: Promise.resolve({
      createOnigScanner: patterns => new oniguruma.OnigScanner(patterns),
      createOnigString: text => new oniguruma.OnigString(text),
    }),
    loadGrammar: async () => parseRawGrammar(fs.readFileSync(file, 'utf8'), file),
  });
  const grammar = await registry.loadGrammar('source.freak');
  const cases = [
    ['pilot answer: int = 42', 'pilot', 'keyword.declaration.freak'],
    ['pilot answer: int = 42', 'int', 'storage.type.primitive.freak'],
    ['pilot answer: int = 42', '42', 'constant.numeric.integer.freak'],
    ['task greet(name: word) -> void {', 'greet', 'entity.name.function.freak'],
    ['-- pilot answer = 42', 'pilot', 'comment.line.double-dash.freak'],
    ['say "Hello, {name}!"', 'Hello', 'string.quoted.double.freak'],
    ['say "Hello, {name}!"', 'name', 'meta.interpolation.freak'],
    ['pilot ready = hai', 'hai', 'constant.language.boolean.freak'],
    ['give back answer', 'give back', 'keyword.control.freak'],
    ['while n < 3 { n += 1 }', 'while', 'keyword.control.freak'],
    ['repeat while n < 6 { n += 1 }', 'repeat while', 'keyword.control.freak'],
    ['repeat until n > 6 { n += 1 }', 'repeat until', 'keyword.control.freak'],
    ['repeat 10 times with i { }', 'times with', 'keyword.control.freak'],
    ['for each i in 0..=10 step 2 { }', '..=', 'keyword.operator.range.freak'],
    ['for each i in 0..=10 step 2 { }', 'step', 'keyword.control.freak'],
    ['for each i in 0..=10 step 2 { }', '10', 'constant.numeric.integer.freak'],
    ['for (pilot i = 0; i < 10; i += 1) { }', ';', 'punctuation.terminator.statement.freak'],
    ['for (pilot i = 0; i < 10; i += 1) { }', 'for', 'keyword.control.freak'],
    ['grounded pilot x = 1', 'grounded pilot', 'keyword.declaration.freak'],
    ['pilot ready = TRUE', 'TRUE', 'constant.language.boolean.freak'],
    ['say "\\{literal\\}"', '\\{', 'constant.character.escape.freak'],
    ['say "\\q"', '\\q', 'invalid.illegal.unknown-escape.freak'],
    ['pilot step = 2', 'step', 'variable.other.freak'],
    ['@side_character', 'side_character', 'storage.type.annotation.freak'],
  ];
  for (const [line, text, scope] of cases) {
    const offset = line.indexOf(text);
    const token = grammar.tokenizeLine(line).tokens.find(t => t.startIndex <= offset && t.endIndex > offset);
    assert(token?.scopes.includes(scope), `${text}: expected ${scope}, got ${JSON.stringify(token)}`);
  }
  registry.dispose();
  console.log(`VS Code: ${cases.length} TextMate token checks passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
