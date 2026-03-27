"""
FREAK Language Server — autocomplete, hover, diagnostics, document symbols.

Usage:
    pip install pygls lsprotocol
    python freak_lsp.py [--stdio | --tcp --port 2087]

Wire into VS Code via the freak-lang extension's settings, or use with any
LSP-compatible editor (Zed, Neovim, Helix, etc.).
"""

import re
import sys
import logging
from typing import Optional

from pygls.server import LanguageServer
from lsprotocol import types as lsp

# ============================================================
#  FREAK language knowledge
# ============================================================

KEYWORDS = [
    # Declarations
    ("pilot", "Variable declaration", "keyword"),
    ("fixed pilot", "Immutable variable declaration", "keyword"),
    ("task", "Function declaration", "keyword"),
    ("shape", "Struct/record declaration", "keyword"),
    ("doctrine", "Trait/interface declaration", "keyword"),
    ("impl", "Implementation block", "keyword"),
    ("route", "Tagged union / enum declaration", "keyword"),
    ("launch", "Mark a task as public/exported", "keyword"),
    ("extern", "External function declaration", "keyword"),
    ("use", "Import module", "keyword"),
    # Control flow
    ("if", "Conditional branch", "keyword"),
    ("else", "Else branch", "keyword"),
    ("when", "Pattern matching (match/switch)", "keyword"),
    ("repeat", "Loop (repeat N times / repeat until)", "keyword"),
    ("training arc", "Bounded loop (compiler-verified termination)", "keyword"),
    ("for each", "Iterator loop", "keyword"),
    ("give back", "Return value from task", "keyword"),
    ("break", "Exit loop", "keyword"),
    ("continue", "Skip to next iteration", "keyword"),
    # Special
    ("say", "Print to stdout (always available)", "function"),
    ("eventually", "Deferred execution block", "keyword"),
    ("trust-me", "Unsafe block", "keyword"),
    ("isekai", "Isolated fresh scope", "keyword"),
    ("bringing back", "Export from isekai scope", "keyword"),
    ("deus_ex_machina", "Dramatic escape hatch (monologue required)", "keyword"),
    ("foreshadow", "Narrative debt variable", "keyword"),
    ("payoff", "Resolve a foreshadowed variable", "keyword"),
    ("done", "Synonym for }", "keyword"),
    # Expressions
    ("some", "Wrap value in maybe (some(x))", "function"),
    ("nobody", "Empty maybe value", "constant"),
    ("ok", "Success result (ok(x))", "function"),
    ("err", "Error result (err(msg))", "function"),
    ("or else", "Default for maybe/result", "keyword"),
    ("copy", "Copy capture for closures", "keyword"),
    ("lend", "Borrow parameter", "keyword"),
    ("lend mut", "Mutable borrow parameter", "keyword"),
    # Testing
    ("test", "Test block", "keyword"),
    ("expect", "Test assertion", "keyword"),
    ("to be", "Test equality check", "keyword"),
]

TYPES = [
    ("int", "64-bit signed integer"),
    ("uint", "64-bit unsigned integer"),
    ("num", "64-bit float (default numeric)"),
    ("tiny", "8-bit unsigned (byte)"),
    ("bool", "Boolean (true/false/yes/no/hai/iie)"),
    ("word", "UTF-8 string (fat pointer: data + byte_len + char_count)"),
    ("char", "Unicode scalar value (32-bit)"),
    ("void", "Unit type"),
    ("float", "64-bit IEEE 754"),
    ("float32", "32-bit IEEE 754"),
    ("big", "Arbitrary precision integer"),
    ("maybe", "Optional type: some(T) | nobody"),
    ("result", "Success/failure: ok(T) | err(E)"),
    ("List", "Dynamic array"),
    ("Map", "Hash map"),
    ("Set", "Unique collection"),
    ("Lineup", "FIFO queue"),
    ("mood", ".chill | .focused | .hype | .mono_no_aware | .muv_luv"),
    ("prob", "Value constrained to probability range"),
    ("power", "Number guaranteed >= N at compile time"),
    ("route", "Tagged union / enum with data"),
]

ANNOTATIONS = [
    ("@protagonist", "Main character (one per program)"),
    ("@nakige", "Acknowledged sad content"),
    ("@experiment", "Scientific context"),
    ("@season_finale", "One allowed per program"),
    ("@deprecated", "Do not use"),
    ("@test", "Test annotation"),
    ("@inline", "Inline hint"),
    ("@cold", "Rarely called"),
    ("@hot", "Frequently called"),
]

BUILTINS = [
    ("say", "Print to stdout", "task say(value: word) -> void"),
    ("len", "Length of collection/string", "task len(self) -> int"),
    ("push", "Append to list", "task push(self, item: T) -> void"),
    ("pop", "Remove last from list", "task pop(self) -> maybe<T>"),
    ("contains", "Check if collection contains", "task contains(self, item: T) -> bool"),
    ("to_word", "Convert to string", "task to_word(self) -> word"),
    ("to_num", "Parse string to number", "task to_num(self) -> maybe<num>"),
    ("substring", "Extract substring", "task substring(self, start: int, end: int) -> word"),
    ("trim", "Trim whitespace", "task trim(self) -> word"),
    ("split", "Split string", "task split(self, sep: word) -> List<word>"),
    ("join", "Join list of strings", "task join(self, sep: word) -> word"),
    ("map", "Transform each element", "task map(self, f: task(T) -> U) -> List<U>"),
    ("filter", "Keep matching elements", "task filter(self, f: task(T) -> bool) -> List<T>"),
]

STD_MODULES = [
    ("std::math", "abs, min, max, clamp, pow, sqrt, gcd, lcm, factorial, fibonacci"),
    ("std::string", "starts_with, ends_with, contains, trim, replace, substring"),
    ("std::convert", "int_to_hex/bin/oct, char_to_digit, bool_to_word"),
    ("std::algorithm", "sort, binary_search, find, reverse, unique, sum"),
    ("std::json", "Parse and serialize JSON"),
    ("std::http", "HTTP/1.1 client (GET/POST/PUT/DELETE)"),
    ("std::fs", "File I/O (read, write, exists, mkdir)"),
    ("std::process", "Spawn processes, env, CLI args"),
    ("std::time", "Timestamps, durations, sleep"),
    ("std::bytes", "ByteBuffer for binary I/O"),
    ("std::net", "TCP, UDP sockets"),
    ("std::ui", "Native window, events, canvas"),
]

SNIPPETS = {
    "task": ("task ${1:name}(${2:params}) -> ${3:void} {\n\t$0\n}", "Define a task (function)"),
    "shape": ("shape ${1:Name} {\n\t${2:field}: ${3:type}\n}", "Define a shape (struct)"),
    "impl": ("impl ${1:Type} {\n\ttask ${2:method}(self${3:, params}) -> ${4:void} {\n\t\t$0\n\t}\n}", "Implementation block"),
    "if": ("if ${1:condition} {\n\t$0\n}", "If statement"),
    "ifelse": ("if ${1:condition} {\n\t$2\n} else {\n\t$0\n}", "If/else statement"),
    "when": ("when ${1:value} {\n\t${2:pattern} -> ${3:body}\n\t_ -> ${0:body}\n}", "Pattern matching"),
    "repeat": ("repeat ${1:n} times {\n\t$0\n}", "Counted loop"),
    "foreach": ("for each ${1:item} in ${2:collection} {\n\t$0\n}", "Iterator loop"),
    "pilot": ("pilot ${1:name} = ${0:value}", "Variable declaration"),
    "fixed": ("fixed pilot ${1:name} = ${0:value}", "Immutable variable"),
    "eventually": ("eventually {\n\t$0\n}", "Deferred execution"),
    "test": ("test \"${1:description}\" {\n\texpect ${2:actual} to be ${0:expected}\n}", "Test block"),
    "say": ("say \"${1:message}\"", "Print statement"),
    "main": ("@protagonist\ntask main() {\n\t$0\n}", "Main entry point"),
    "route": ("route ${1:Name} {\n\t${2:Variant1},\n\t${0:Variant2}\n}", "Tagged union"),
    "doctrine": ("doctrine ${1:Name} {\n\ttask ${2:method}(self${3:, params}) -> ${0:type}\n}", "Trait declaration"),
    "trustme": ("trust-me \"${1:reason}\" {\n\t$0\n}", "Unsafe block"),
    "use": ("use ${1:std}::${0:module}", "Import module"),
    "check_maybe": ("check ${1:value} {\n\tgot ${2:x} -> ${3:body}\n\tnobody -> ${0:body}\n}", "Check maybe value"),
    "check_result": ("check ${1:value} {\n\tok(${2:x}) -> ${3:body}\n\terr(${4:e}) -> ${0:body}\n}", "Check result value"),
    "lambda": ("|| {\n\t$0\n}", "Lambda/closure"),
    "training": ("training arc ${1:name} from ${2:0} to ${3:n} {\n\t$0\n}", "Training arc loop"),
}

# ============================================================
#  Document analysis — scan file for symbols
# ============================================================

RE_TASK = re.compile(r'\btask\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?')
RE_SHAPE = re.compile(r'\bshape\s+([A-Z]\w*)')
RE_DOCTRINE = re.compile(r'\bdoctrine\s+([A-Z]\w*)')
RE_IMPL = re.compile(r'\bimpl\s+([A-Z]\w*)')
RE_ROUTE = re.compile(r'\broute\s+([A-Z]\w*)')
RE_PILOT = re.compile(r'\bpilot\s+([a-zA-Z_]\w*)\s*(?::\s*(\S+))?\s*=')
RE_FIXED = re.compile(r'\bfixed\s+pilot\s+([a-zA-Z_]\w*)\s*(?::\s*(\S+))?\s*=')
RE_FIELD = re.compile(r'^\s+([a-zA-Z_]\w*)\s*:\s*(\S+)')
RE_USE = re.compile(r'\buse\s+([\w:]+)')
RE_ANNOTATION = re.compile(r'@(\w+)')


class DocumentSymbols:
    """Scanned symbols from a single .fk file."""
    def __init__(self):
        self.tasks = []       # (name, params_str, return_type, line)
        self.shapes = []      # (name, line, fields)
        self.doctrines = []   # (name, line)
        self.impls = []       # (name, line)
        self.routes = []      # (name, line)
        self.pilots = []      # (name, type_hint, line)
        self.fixed = []       # (name, type_hint, line)
        self.imports = []     # (module_path, line)


def scan_document(text: str) -> DocumentSymbols:
    """Extract symbols from FREAK source text."""
    syms = DocumentSymbols()
    lines = text.split('\n')
    current_shape = None
    current_fields = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('--'):
            continue

        m = RE_TASK.search(line)
        if m:
            syms.tasks.append((m.group(1), m.group(2).strip(), m.group(3) or 'void', i))

        m = RE_SHAPE.search(line)
        if m:
            if current_shape and current_fields:
                for s in syms.shapes:
                    if s[0] == current_shape:
                        s[2].extend(current_fields)
            current_shape = m.group(1)
            current_fields = []
            syms.shapes.append([m.group(1), i, []])

        m = RE_FIELD.match(line)
        if m and current_shape:
            current_fields.append((m.group(1), m.group(2)))

        if stripped in ('}', 'done') and current_shape:
            if current_fields and syms.shapes:
                syms.shapes[-1][2] = current_fields
            current_shape = None
            current_fields = []

        m = RE_DOCTRINE.search(line)
        if m:
            syms.doctrines.append((m.group(1), i))

        m = RE_IMPL.search(line)
        if m:
            syms.impls.append((m.group(1), i))

        m = RE_ROUTE.search(line)
        if m:
            syms.routes.append((m.group(1), i))

        m = RE_FIXED.search(line)
        if m:
            syms.fixed.append((m.group(1), m.group(2), i))
            continue

        m = RE_PILOT.search(line)
        if m:
            syms.pilots.append((m.group(1), m.group(2), i))

        m = RE_USE.search(line)
        if m:
            syms.imports.append((m.group(1), i))

    return syms


# ============================================================
#  Language Server
# ============================================================

server = LanguageServer("freak-lsp", "v0.1.0")
documents: dict[str, str] = {}
doc_symbols: dict[str, DocumentSymbols] = {}


@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams):
    uri = params.text_document.uri
    text = params.text_document.text
    documents[uri] = text
    doc_symbols[uri] = scan_document(text)
    _publish_diagnostics(uri, text)


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(params: lsp.DidChangeTextDocumentParams):
    uri = params.text_document.uri
    for change in params.content_changes:
        if isinstance(change, lsp.TextDocumentContentChangeEvent_Type1):
            documents[uri] = change.text
        else:
            documents[uri] = change.text
    doc_symbols[uri] = scan_document(documents[uri])
    _publish_diagnostics(uri, documents[uri])


@server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams):
    uri = params.text_document.uri
    documents.pop(uri, None)
    doc_symbols.pop(uri, None)


# ---- Completion ----

@server.feature(
    lsp.TEXT_DOCUMENT_COMPLETION,
    lsp.CompletionOptions(trigger_characters=[".", ":", "@", '"']),
)
def completion(params: lsp.CompletionParams) -> lsp.CompletionList:
    uri = params.text_document.uri
    text = documents.get(uri, "")
    lines = text.split('\n')
    line_idx = params.position.line
    col = params.position.character

    if line_idx >= len(lines):
        return lsp.CompletionList(is_incomplete=False, items=[])

    line = lines[line_idx]
    prefix = line[:col]

    items = []

    # After @, suggest annotations
    if '@' in prefix and not prefix.strip().startswith('--'):
        for ann, desc in ANNOTATIONS:
            items.append(lsp.CompletionItem(
                label=ann,
                kind=lsp.CompletionItemKind.Keyword,
                detail=desc,
                insert_text=ann[1:],  # skip the @ since it's already typed
            ))
        return lsp.CompletionList(is_incomplete=False, items=items)

    # After "use ", suggest std modules
    if re.search(r'\buse\s+$', prefix):
        for mod, desc in STD_MODULES:
            items.append(lsp.CompletionItem(
                label=mod,
                kind=lsp.CompletionItemKind.Module,
                detail=desc,
                insert_text=mod,
            ))
        return lsp.CompletionList(is_incomplete=False, items=items)

    # After "::", suggest module members or type methods
    if prefix.rstrip().endswith('::'):
        return lsp.CompletionList(is_incomplete=False, items=_scope_completions(prefix, uri))

    # After ".", suggest fields/methods
    if '.' in prefix:
        last_dot = prefix.rfind('.')
        before_dot = prefix[:last_dot].strip().split()
        if before_dot:
            obj = before_dot[-1]
            items.extend(_field_completions(obj, uri))
            # Also suggest mood literals
            for mood in ['chill', 'focused', 'hype', 'mono_no_aware', 'muv_luv']:
                items.append(lsp.CompletionItem(
                    label=f".{mood}",
                    kind=lsp.CompletionItemKind.EnumMember,
                    detail=f"mood.{mood}",
                    insert_text=mood,
                ))

    # Snippets
    for name, (body, desc) in SNIPPETS.items():
        items.append(lsp.CompletionItem(
            label=name,
            kind=lsp.CompletionItemKind.Snippet,
            detail=desc,
            insert_text=body,
            insert_text_format=lsp.InsertTextFormat.Snippet,
        ))

    # Keywords
    for kw, desc, kind in KEYWORDS:
        ck = lsp.CompletionItemKind.Keyword
        if kind == "function":
            ck = lsp.CompletionItemKind.Function
        elif kind == "constant":
            ck = lsp.CompletionItemKind.Constant
        items.append(lsp.CompletionItem(
            label=kw, kind=ck, detail=desc, insert_text=kw,
        ))

    # Types
    for ty, desc in TYPES:
        items.append(lsp.CompletionItem(
            label=ty,
            kind=lsp.CompletionItemKind.TypeParameter,
            detail=desc,
        ))

    # Built-in functions
    for name, desc, sig in BUILTINS:
        items.append(lsp.CompletionItem(
            label=name,
            kind=lsp.CompletionItemKind.Function,
            detail=sig,
            documentation=desc,
        ))

    # Symbols from current document
    syms = doc_symbols.get(uri)
    if syms:
        for name, params, ret, line in syms.tasks:
            items.append(lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.Function,
                detail=f"task {name}({params}) -> {ret}",
                documentation=f"Defined at line {line + 1}",
            ))
        for name, line, fields in syms.shapes:
            items.append(lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.Struct,
                detail=f"shape {name}",
                documentation=f"Defined at line {line + 1}",
            ))
        for name, line in syms.routes:
            items.append(lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.Enum,
                detail=f"route {name}",
            ))
        for name, ty, line in syms.pilots + syms.fixed:
            items.append(lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.Variable,
                detail=f"pilot {name}" + (f": {ty}" if ty else ""),
            ))

    return lsp.CompletionList(is_incomplete=False, items=items)


def _scope_completions(prefix: str, uri: str) -> list[lsp.CompletionItem]:
    """Completions after :: (e.g., Color::, std::math::)."""
    items = []
    stripped = prefix.rstrip().rstrip(':').rstrip(':')
    scope = stripped.split()[-1] if stripped.split() else ""

    syms = doc_symbols.get(uri)
    if syms:
        # If scope matches a shape name, suggest its constructor / static methods
        for name, line, fields in syms.shapes:
            if name == scope:
                items.append(lsp.CompletionItem(
                    label="new",
                    kind=lsp.CompletionItemKind.Constructor,
                    detail=f"{name}::new()",
                ))
                # Suggest field names for struct literal
                for fname, ftype in fields:
                    items.append(lsp.CompletionItem(
                        label=fname,
                        kind=lsp.CompletionItemKind.Field,
                        detail=f"{fname}: {ftype}",
                    ))
        # Static methods from impl blocks
        for tname, params, ret, line in syms.tasks:
            # Heuristic: if task doesn't take self, it might be a static method
            if not params.startswith('self'):
                items.append(lsp.CompletionItem(
                    label=tname,
                    kind=lsp.CompletionItemKind.Method,
                    detail=f"{scope}::{tname}({params}) -> {ret}",
                ))

    # Named color constructors
    if scope == "Color":
        for color in ["rgb", "rgba", "red", "green", "blue", "white", "black", "transparent"]:
            items.append(lsp.CompletionItem(
                label=color,
                kind=lsp.CompletionItemKind.Function,
                detail=f"Color::{color}()",
            ))

    return items


def _field_completions(obj_name: str, uri: str) -> list[lsp.CompletionItem]:
    """Completions after . (field access / method call)."""
    items = []
    syms = doc_symbols.get(uri)
    if not syms:
        return items

    # Find the type of the variable
    var_type = None
    for name, ty, _ in syms.pilots + syms.fixed:
        if name == obj_name and ty:
            var_type = ty
            break

    # If we know the type, suggest its fields
    if var_type:
        for sname, _, fields in syms.shapes:
            if sname == var_type:
                for fname, ftype in fields:
                    items.append(lsp.CompletionItem(
                        label=fname,
                        kind=lsp.CompletionItemKind.Field,
                        detail=f"{ftype}",
                    ))

    # Common methods on built-in types
    for bname, bdesc, bsig in BUILTINS:
        items.append(lsp.CompletionItem(
            label=bname,
            kind=lsp.CompletionItemKind.Method,
            detail=bsig,
            documentation=bdesc,
        ))

    return items


# ---- Hover ----

@server.feature(lsp.TEXT_DOCUMENT_HOVER)
def hover(params: lsp.HoverParams) -> Optional[lsp.Hover]:
    uri = params.text_document.uri
    text = documents.get(uri, "")
    lines = text.split('\n')
    line_idx = params.position.line
    col = params.position.character

    if line_idx >= len(lines):
        return None

    line = lines[line_idx]
    word = _word_at(line, col)
    if not word:
        return None

    # Check keywords
    for kw, desc, _ in KEYWORDS:
        if word == kw:
            return lsp.Hover(contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"**{kw}** — {desc}",
            ))

    # Check types
    for ty, desc in TYPES:
        if word == ty:
            return lsp.Hover(contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"**{ty}** — {desc}",
            ))

    # Check document symbols
    syms = doc_symbols.get(uri)
    if syms:
        for name, params, ret, ln in syms.tasks:
            if word == name:
                return lsp.Hover(contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=f"```freak\ntask {name}({params}) -> {ret}\n```\nDefined at line {ln + 1}",
                ))
        for name, ln, fields in syms.shapes:
            if word == name:
                field_strs = "\n".join(f"    {f}: {t}" for f, t in fields)
                return lsp.Hover(contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=f"```freak\nshape {name} {{\n{field_strs}\n}}\n```",
                ))
        for name, ln in syms.routes:
            if word == name:
                return lsp.Hover(contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=f"**route** {name}\nDefined at line {ln + 1}",
                ))

    # Check builtins
    for bname, bdesc, bsig in BUILTINS:
        if word == bname:
            return lsp.Hover(contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"```freak\n{bsig}\n```\n{bdesc}",
            ))

    return None


def _word_at(line: str, col: int) -> str:
    """Extract the word at column position."""
    if col >= len(line):
        col = len(line) - 1
    if col < 0:
        return ""
    # Find word boundaries
    start = col
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] == '_'):
        start -= 1
    end = col
    while end < len(line) and (line[end].isalnum() or line[end] == '_'):
        end += 1
    return line[start:end]


# ---- Document Symbols ----

@server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
def document_symbol(params: lsp.DocumentSymbolParams) -> list[lsp.DocumentSymbol]:
    uri = params.text_document.uri
    syms = doc_symbols.get(uri)
    if not syms:
        return []

    result = []

    for name, params_str, ret, line in syms.tasks:
        result.append(lsp.DocumentSymbol(
            name=name,
            detail=f"({params_str}) -> {ret}",
            kind=lsp.SymbolKind.Function,
            range=_line_range(line),
            selection_range=_line_range(line),
        ))

    for name, line, fields in syms.shapes:
        children = []
        for fname, ftype in fields:
            children.append(lsp.DocumentSymbol(
                name=fname,
                detail=ftype,
                kind=lsp.SymbolKind.Field,
                range=_line_range(line + 1),
                selection_range=_line_range(line + 1),
            ))
        result.append(lsp.DocumentSymbol(
            name=name,
            kind=lsp.SymbolKind.Struct,
            range=_line_range(line),
            selection_range=_line_range(line),
            children=children if children else None,
        ))

    for name, line in syms.doctrines:
        result.append(lsp.DocumentSymbol(
            name=name,
            kind=lsp.SymbolKind.Interface,
            range=_line_range(line),
            selection_range=_line_range(line),
        ))

    for name, line in syms.routes:
        result.append(lsp.DocumentSymbol(
            name=name,
            kind=lsp.SymbolKind.Enum,
            range=_line_range(line),
            selection_range=_line_range(line),
        ))

    for name, ty, line in syms.fixed:
        result.append(lsp.DocumentSymbol(
            name=name,
            detail=f"fixed pilot" + (f": {ty}" if ty else ""),
            kind=lsp.SymbolKind.Constant,
            range=_line_range(line),
            selection_range=_line_range(line),
        ))

    return result


def _line_range(line: int) -> lsp.Range:
    return lsp.Range(
        start=lsp.Position(line=line, character=0),
        end=lsp.Position(line=line, character=999),
    )


# ---- Diagnostics ----

def _publish_diagnostics(uri: str, text: str):
    """Basic diagnostics: unmatched braces, missing give back, etc."""
    diagnostics = []
    lines = text.split('\n')
    brace_stack = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('--'):
            continue

        # Track braces
        for j, ch in enumerate(line):
            if ch == '{':
                brace_stack.append((i, j))
            elif ch == '}':
                if brace_stack:
                    brace_stack.pop()
                else:
                    diagnostics.append(lsp.Diagnostic(
                        range=lsp.Range(
                            start=lsp.Position(line=i, character=j),
                            end=lsp.Position(line=i, character=j + 1),
                        ),
                        severity=lsp.DiagnosticSeverity.Error,
                        source="freak-lsp",
                        message="Unmatched closing brace",
                    ))

        # Check for done keyword closing a block
        if stripped == 'done':
            if brace_stack:
                brace_stack.pop()

        # Warn about empty task bodies
        if RE_TASK.search(stripped) and stripped.endswith('{}'):
            diagnostics.append(lsp.Diagnostic(
                range=_line_range(i),
                severity=lsp.DiagnosticSeverity.Warning,
                source="freak-lsp",
                message="Empty task body",
            ))

    # Report unclosed braces
    for line, col in brace_stack:
        diagnostics.append(lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=line, character=col),
                end=lsp.Position(line=line, character=col + 1),
            ),
            severity=lsp.DiagnosticSeverity.Error,
            source="freak-lsp",
            message="Unclosed brace",
        ))

    server.publish_diagnostics(uri, diagnostics)


# ============================================================
#  Main
# ============================================================

def main():
    if '--tcp' in sys.argv:
        port = 2087
        for i, arg in enumerate(sys.argv):
            if arg == '--port' and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        server.start_tcp('127.0.0.1', port)
    else:
        server.start_io()


if __name__ == '__main__':
    main()
