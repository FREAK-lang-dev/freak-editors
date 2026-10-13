"""
FREAK Language Server — autocomplete, hover, diagnostics, document symbols.

Usage:
    pip install pygls lsprotocol
    python freak_lsp.py [--stdio | --tcp --port 2087]

Wire into VS Code via the freak-lang extension's settings, or use with any
LSP-compatible editor (Zed, Neovim, Helix, etc.).
"""

import os
import re
import shutil
import subprocess
import threading
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname
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
    ("grounded pilot", "Immutable variable declaration (same as fixed pilot)", "keyword"),
    ("grounded", "Immutable binding marker (same as fixed)", "keyword"),
    ("task", "Function declaration", "keyword"),
    ("shape", "Struct/record declaration", "keyword"),
    ("doctrine", "Trait/interface declaration", "keyword"),
    ("impl", "Implementation block", "keyword"),
    ("route", "Visual-novel outcome declaration", "keyword"),
    ("variant", "Nominal sum type declaration", "keyword"),
    ("alias", "Compile-time type alias", "keyword"),
    ("launch", "Mark a task/shape as public/exported", "keyword"),
    ("extern", "External function declaration (FFI)", "keyword"),
    ("use", "Import module", "keyword"),
    ("as", "Import alias, or explicit downcast (value as? Type)", "keyword"),
    ("dyn", "Dynamically-dispatched doctrine object (dyn Doctrine)", "keyword"),
    # Control flow
    ("if", "Conditional branch", "keyword"),
    ("else", "Else branch", "keyword"),
    ("when", "Pattern matching (match/switch)", "keyword"),
    ("repeat", "Loop (repeat N times / repeat until / repeat while)", "keyword"),
    ("repeat while", "Loop while the condition holds", "keyword"),
    ("while", "Loop while the condition holds", "keyword"),
    ("times", "Count marker: repeat N times", "keyword"),
    ("with", "Counter binding: repeat N times with i", "keyword"),
    ("step", "Range stride: for each i in 0..10 step 2", "keyword"),
    ("until", "Condition marker: repeat until / training arc until", "keyword"),
    ("sessions", "Budget marker: training arc ... max N sessions", "keyword"),
    ("max", "Budget marker: training arc ... max N sessions", "keyword"),
    ("training arc", "Bounded loop (compiler-verified termination)", "keyword"),
    ("for each", "Iterator loop", "keyword"),
    ("for", "Loop introducer: for each, or for (init; condition; update)", "keyword"),
    ("each", "Iterator marker (for each)", "keyword"),
    ("in", "Iteration source: for each item in collection", "keyword"),
    ("give back", "Return value from task", "keyword"),
    ("break", "Exit loop", "keyword"),
    ("continue", "Skip to next iteration", "keyword"),
    # Error handling
    ("check", "Exhaustive maybe/result/route check", "keyword"),
    ("check result", "Exhaustive result check (ok / err)", "keyword"),
    ("check route", "Exhaustive route check (TrueRoute / BadEnd / ...)", "keyword"),
    ("got", "Success arm of a check block", "keyword"),
    ("result", "Result marker (check result / result<T, E>)", "keyword"),
    ("or else", "Fallback for maybe/result", "keyword"),
    # Borrowing / closures
    ("lend", "Borrow parameter", "keyword"),
    ("lend mut", "Mutable borrow parameter", "keyword"),
    ("copy", "Copy capture for closures", "keyword"),
    ("move", "Move capture for closures (OneShot)", "keyword"),
    ("mut", "Mutable capture for closures", "keyword"),
    # Concurrency (Squadron / XM3)
    ("xm3", "Parallel racing block (first success wins)", "keyword"),
    ("sortie", "Spawn a concurrent thread", "keyword"),
    ("debrief", "Wait for a sortie / formation result", "keyword"),
    ("formation", "Run all branches, wait for all (or first)", "keyword"),
    ("first", "Fastest-wins marker: formation first", "keyword"),
    ("enter", "Exclusive write: enter briefing room as x", "keyword"),
    ("observe", "Shared read: observe briefing room as x", "keyword"),
    ("briefing", "Mutex-guarded shared state room", "keyword"),
    ("wingman", "Actor-model declaration", "keyword"),
    ("on", "Actor message handler: on msg(...) / route guard: only on", "keyword"),
    # Anime operators
    ("PLUS ULTRA", "Emotion-driven power scaling", "keyword"),
    ("NAKAMA", "Friendship synergy operator", "keyword"),
    ("FINAL FORM", "Ultimate squaring operator", "keyword"),
    ("TSUNDERE", "Inverse operator (bool negation / num negation)", "keyword"),
    # Special blocks
    ("say", "Print to stdout (always available)", "function"),
    ("eventually", "Deferred execution block (runs at scope end)", "keyword"),
    ("trust me", "Unsafe block (monologue of intent, honor-gated)", "keyword"),
    ("on my honor as", "Honor level gate for trust me blocks", "keyword"),
    ("isekai", "Isolated fresh scope", "keyword"),
    ("bringing back", "Export from isekai scope", "keyword"),
    ("only on", "Route-locked scope: only on TrueRoute from x", "keyword"),
    ("deus_ex_machina", "Dramatic escape hatch (monologue required)", "keyword"),
    ("foreshadow", "Narrative debt variable", "keyword"),
    ("payoff", "Resolve a foreshadowed variable", "keyword"),
    ("declare", "Cross-timeline assertion: declare x was v in timeline", "keyword"),
    ("prob_when", "Exhaustive probability branching", "keyword"),
    ("direct_order", "Inline assembly block (commander/honor+)", "keyword"),
    ("done", "Synonym for }", "keyword"),
    # Call prefixes
    ("knowing this will hurt,", "Acknowledgement prefix for @nakige calls", "keyword"),
    ("sadly", "Short acknowledgement prefix for @nakige calls", "keyword"),
    ("for science,", "Required prefix for @experiment calls", "keyword"),
    # Testing
    ("test", "Test block", "keyword"),
    ("expect", "Test assertion", "keyword"),
    ("to be", "Test equality check", "keyword"),
    # Expressions
    ("some", "Wrap value in maybe (some(x))", "function"),
    ("nobody", "Empty maybe value", "constant"),
    ("ok", "Success result (ok(x))", "function"),
    ("err", "Error result (err(msg))", "function"),
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
    ("never", "Bottom type (panic/exit/infinite loops coerce to any type)"),
    ("float", "64-bit IEEE 754"),
    ("float32", "32-bit IEEE 754"),
    ("big", "Arbitrary precision integer"),
    ("maybe", "Optional type: some(T) | nobody"),
    ("result", "Success/failure: ok(T) | err(E)"),
    ("List", "Dynamic array"),
    ("Map", "Hash map"),
    ("Set", "Unique collection"),
    ("Lineup", "FIFO queue"),
    ("Shared", "Atomic reference-counted owning pointer"),
    ("Weak", "Non-owning observer pointer (upgrade while alive)"),
    ("mood", ".chill | .focused | .hype | .mono_no_aware | .muv_luv | ..."),
    ("power", "Number guaranteed >= N at compile time: power<N>"),
    ("prob", "Value constrained to probability range: prob[lo..hi]"),
    ("causality", "Cross-timeline broadcast value: causality<T>"),
    ("route", "Visual-novel outcome type (TrueRoute/GoodEnd/...)"),
]

ANNOTATIONS = [
    ("@protagonist", "Main character (one per program, grants power<over9000>)"),
    ("@nakige", "Tragedy: callers must acknowledge (knowing this will hurt,)"),
    ("@side_character", "Death-flag monitoring for this pilot"),
    ("@experiment", "Scientific context: calls require 'for science,'"),
    ("@fixed_fate", "Certain outcome: removes probability and maybe"),
    ("@classified", "Value redacted from all output without clearance"),
    ("@rival", "Mutual power boost based on shared missions"),
    ("@season_finale", "One allowed per codebase, maximum"),
    ("@i_know_what_im_doing", "Explicit override for death-flag errors"),
    ("@deprecated", "Do not use"),
    ("@layout", "FFI memory layout contract: @layout(C)"),
    ("@repr", "Variant representation: @repr(u32)"),
    ("@skip", "Skip this test"),
    ("@only", "Run only this test"),
]

BUILTINS = [
    ("say", "Print to stdout", "task say(value: word) -> void"),
    ("ask", "Read a line from stdin", "task ask(prompt: word) -> word"),
    ("panic", "Abort with a message (type never)", "task panic(msg: word) -> never"),
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
    ("std::math", "sin, cos, sqrt, log, gcd, simd"),
    ("std::string", "starts_with, ends_with, contains, trim, replace, substring"),
    ("std::convert", "int_to_hex/bin/oct, char_to_digit, bool_to_word"),
    ("std::algorithm", "sort, binary_search, find, reverse, unique, sum"),
    ("std::collections", "List, Map, Set, Lineup collections"),
    ("std::iter", "Lazy iterators: map, filter, fold, zip, enumerate"),
    ("std::io", "ask, say_err, stdout, stdin"),
    ("std::json", "Parse and serialize JSON"),
    ("std::http", "HTTP/1.1 client (GET/POST/PUT/DELETE)"),
    ("std::fs", "File I/O (read, read_checked, write, exists, mkdir)"),
    ("std::net", "TCP, UDP sockets"),
    ("std::time", "Timestamps, durations, sleep"),
    ("std::bytes", "ByteBuffer for binary I/O"),
    ("std::process", "Spawn processes, env, CLI args"),
    ("std::thread", "spawn, atomics, channels"),
    ("std::random", "rand, rand_range, pick, secure, seed"),
    ("std::mem", "Shared, Weak, size_of, alloc, free"),
    ("std::ffi", "C/OS boundary types: c_int, c_bool, usize, ..."),
    ("std::anime", "mood arithmetic, power checks"),
    ("std::narrative", "Death flags, foreshadow logs"),
    ("std::test", "test blocks and expect assertions"),
    ("std::ui", "Native window, events, canvas"),
]

SNIPPETS = {
    "task": ("task ${1:name}(${2:params}) -> ${3:void} {\n\t$0\n}", "Define a task (function)"),
    "taskshort": ("task ${1:name}(${2:params}) => $0", "Arrow-shorthand task (single expression)"),
    "shape": ("shape ${1:Name} {\n\t${2:field}: ${3:type}\n}", "Define a shape (struct)"),
    "impl": ("impl ${1:Type} {\n\ttask ${2:method}(self${3:, params}) -> ${4:void} {\n\t\t$0\n\t}\n}", "Implementation block"),
    "implfor": ("impl ${1:Doctrine} for ${2:Type} {\n\ttask ${3:method}(self${4:, params}) -> ${5:void} {\n\t\t$0\n\t}\n}", "Doctrine implementation for a type"),
    "variant": ("variant ${1:Name} {\n\t${2:Case} {\n\t\t${3:field}: ${4:type}\n\t},\n\t${0:Other}\n}", "Nominal sum type"),
    "alias": ("alias ${1:Name} = ${0:Type}", "Compile-time type alias"),
    "if": ("if ${1:condition} {\n\t$0\n}", "If statement"),
    "ifelse": ("if ${1:condition} {\n\t$2\n} else {\n\t$0\n}", "If/else statement"),
    "when": ("when ${1:value} {\n\t${2:pattern} -> ${3:body}\n\t_ -> ${0:body}\n}", "Pattern matching"),
    "repeat": ("repeat ${1:n} times {\n\t$0\n}", "Counted loop"),
    "repeatuntil": ("repeat until ${1:condition} {\n\t$0\n}", "Repeat-until loop"),
    "foreach": ("for each ${1:item} in ${2:collection} {\n\t$0\n}", "Iterator loop"),
    "forrange": ("for each ${1:i} in ${2:0}..${3:n} {\n\t$0\n}", "Range loop (end excluded; ..= includes it)"),
    "forstep": ("for each ${1:i} in ${2:0}..${3:n} step ${4:2} {\n\t$0\n}", "Range loop with a stride"),
    "for": ("for (pilot ${1:i} = ${2:0}; ${1:i} < ${3:n}; ${1:i} += 1) {\n\t$0\n}", "C-style loop"),
    "while": ("while ${1:condition} {\n\t$0\n}", "While loop"),
    "repeatwhile": ("repeat while ${1:condition} {\n\t$0\n}", "Repeat-while loop"),
    "timeswith": ("repeat ${1:n} times with ${2:i} {\n\t$0\n}", "Counted loop with a counter"),
    "grounded": ("grounded pilot ${1:name} = ${0:value}", "Immutable variable"),
    "readchecked": ("pilot ${1:r} = fs::read_checked(${2:path})\ncheck result ${1:r} {\n\tok(${3:text}) -> { $0 }\n\terr(${4:e}) -> { say \"could not read: \" + ${4:e} }\n}", "Read a file, telling a missing one from an empty one"),
    "pilot": ("pilot ${1:name} = ${0:value}", "Variable declaration"),
    "fixed": ("fixed pilot ${1:name} = ${0:value}", "Immutable variable"),
    "eventually": ("eventually {\n\t$0\n}", "Deferred execution"),
    "test": ("test \"${1:description}\" {\n\texpect ${2:actual} to be ${0:expected}\n}", "Test block"),
    "expect": ("expect ${1:actual} to be ${0:expected}", "Test equality assertion"),
    "say": ("say \"${1:message}\"", "Print statement"),
    "main": ("@protagonist\ntask main() {\n\t$0\n}", "Main entry point"),
    "route": ("route ${1:Name} {\n\t${2:Variant1},\n\t${0:Variant2}\n}", "Tagged union"),
    "doctrine": ("doctrine ${1:Name} {\n\ttask ${2:method}(self${3:, params}) -> ${0:type}\n}", "Trait declaration"),
    "trustme": ("trust me \"${1:reason}\" on my honor as ${2|cadet,pilot,ace,commander,humanity|} {\n\t$0\n}", "Unsafe block"),
    "use": ("use ${1:std}::${0:module}", "Import module"),
    "check_maybe": ("check ${1:value} {\n\tgot ${2:x} -> ${3:body}\n\tnobody -> ${0:body}\n}", "Check maybe value"),
    "check_result": ("check result ${1:value} {\n\tok(${2:x}) -> ${3:body}\n\terr(${4:e}) -> ${0:body}\n}", "Check result value"),
    "check_route": ("check route ${1:value} {\n\tTrueRoute -> ${2:body}\n\t_ -> ${0:body}\n}", "Check route outcome"),
    "lambda": ("|${1:x}| => $0", "Arrow lambda/closure"),
    "lambdablock": ("|${1:x}| {\n\tgive back $0\n}", "Block lambda/closure"),
    "training": ("training arc until ${1:condition} max ${2:n} sessions {\n\t$0\n}", "Training arc loop"),
    "isekai": ("isekai {\n\t$0\n} bringing back {\n\t${1:exports}\n}", "Isolated scope with exports"),
    "foreshadow": ("foreshadow pilot ${1:name} = ${0:value}", "Narrative promise (must pay off)"),
    "payoff": ("payoff ${0:name}", "Resolve a foreshadowed variable"),
    "extern": ("extern [${1:C}] {\n\ttask ${2:name}(${3:params}) -> ${0:type}\n}", "External FFI block"),
}

# Annotations the diagnostics pass understands (kept in sync with ANNOTATIONS).
KNOWN_ANNOTATIONS = frozenset(a[1:] for a, _ in ANNOTATIONS) | {"test", "tool"}

# ============================================================
#  Document analysis — scan file for symbols
# ============================================================

RE_TASK = re.compile(r'\btask\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?')
RE_SHAPE = re.compile(r'\bshape\s+([A-Z]\w*)')
RE_DOCTRINE = re.compile(r'\bdoctrine\s+([A-Z]\w*)')
RE_IMPL = re.compile(r'\bimpl\s+([A-Z]\w*)')
RE_ROUTE = re.compile(r'\broute\s+([A-Z]\w*)')
RE_PILOT = re.compile(r'\bpilot\s+([a-zA-Z_]\w*)\s*(?::\s*(\S+))?\s*=')
RE_FIXED = re.compile(r'\b(?:fixed|grounded)\s+pilot\s+([a-zA-Z_]\w*)\s*(?::\s*(\S+))?\s*=')
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

server = LanguageServer("freak-lsp", "v0.15.0")
documents: dict[str, str] = {}
doc_symbols: dict[str, DocumentSymbols] = {}


@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams):
    uri = params.text_document.uri
    text = params.text_document.text
    documents[uri] = text
    doc_symbols[uri] = scan_document(text)
    _publish_diagnostics(uri, text)
    _schedule_compiler_check(uri)


@server.feature(lsp.INITIALIZE)
def initialize(params: lsp.InitializeParams):
    options = params.initialization_options
    if isinstance(options, dict):
        if isinstance(options.get("compilerPath"), str) and options["compilerPath"]:
            compiler["path"] = options["compilerPath"]
        if options.get("compilerDiagnostics") is False:
            compiler["enabled"] = False


@server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams):
    _schedule_compiler_check(params.text_document.uri)


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(params: lsp.DidChangeTextDocumentParams):
    uri = params.text_document.uri
    text = documents.get(uri, "")
    for change in params.content_changes:
        # Incremental update carries a range; a bare change is the full text.
        change_range = getattr(change, "range", None)
        if change_range is None:
            text = change.text
        else:
            text = _apply_incremental_change(text, change_range, change.text)
    documents[uri] = text
    doc_symbols[uri] = scan_document(text)
    _publish_diagnostics(uri, text)


def _apply_incremental_change(old: str, change_range, new_text: str) -> str:
    """Apply one ranged LSP edit to the cached document text."""
    lines = old.split(chr(10))
    start, end = change_range.start, change_range.end

    def to_offset(line: int, character: int) -> int:
        line = max(0, min(line, len(lines) - 1))
        character = max(0, min(character, len(lines[line])))
        return sum(len(lines[i]) + 1 for i in range(line)) + character

    start_off = to_offset(start.line, start.character)
    end_off = to_offset(end.line, end.character)
    if end_off < start_off:
        end_off = start_off
    return old[:start_off] + new_text + old[end_off:]


@server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams):
    uri = params.text_document.uri
    documents.pop(uri, None)
    compiler_diagnostics.pop(uri, None)
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

    frag = _completion_fragment(prefix)
    if frag:
        lowered = frag.lower()
        items = [it for it in items if (it.label or "").lower().startswith(lowered)]

    return lsp.CompletionList(is_incomplete=False, items=items)


def _completion_fragment(prefix: str) -> str:
    """Trailing word run the user is typing (letters, digits, _, space, comma).

    Spaces are kept so multi-word keywords (give back, trust me, ...) filter
    correctly; anything else (brackets, quotes, dots) ends the fragment.
    """
    run = []
    for ch in reversed(prefix):
        if ch.isalnum() or ch in ("_", " ", ","):
            run.append(ch)
        else:
            break
    return "".join(reversed(run)).strip().lower()


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

    candidates = _phrases_at(line, col, word)

    # Check keywords (single words and multi-word phrases like "trust me")
    for kw, desc, _ in KEYWORDS:
        if kw in candidates:
            return lsp.Hover(contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"**{kw}** — {desc}",
            ))

    # Check annotations (@protagonist, ...). _word_at drops the @ sigil.
    for ann, desc in ANNOTATIONS:
        if ann in candidates or ann[1:] in candidates:
            return lsp.Hover(contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"**{ann}** — {desc}",
            ))

    # Check std modules (std::fs, ...) — the cursor word alone won't match.
    module = _module_at(line, col)
    if module:
        for mod, desc in STD_MODULES:
            if module == mod or module.startswith(mod + "::"):
                return lsp.Hover(contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=f"**{mod}** — {desc}",
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


def _words_around(line: str, col: int):
    """Split the line into words, returning (words, index_of_word_at_col)."""
    words = []
    spans = []
    i = 0
    while i < len(line):
        if line[i].isalnum() or line[i] == '_':
            j = i
            while j < len(line) and (line[j].isalnum() or line[j] == '_'):
                j += 1
            words.append(line[i:j])
            spans.append((i, j))
            i = j
        else:
            i += 1
    idx = None
    for k, (s, e) in enumerate(spans):
        if s <= col < e or (col == e and k == len(spans) - 1):
            idx = k
    return words, spans, idx


def _phrases_at(line: str, col: int, word: str) -> set:
    """Candidate phrases at the cursor: the word plus nearby n-grams.

    Lets hover recognize multi-word keywords (trust me, give back, ...)
    no matter which word the cursor sits on.
    """
    words, spans, idx = _words_around(line, col)
    found = {word}
    if idx is None:
        return found
    for width in (2, 3, 4):
        for start in range(max(0, idx - width + 1), min(idx + 1, len(words))):
            chunk = words[start:start + width]
            if len(chunk) == width and idx in range(start, start + width):
                found.add(" ".join(chunk))
    # Annotations keep their sigil for matching.
    word_start = spans[idx][0]
    if word_start > 0 and line[word_start - 1] == "@":
        found.add("@" + word)
    return found


def _module_at(line: str, col: int) -> str:
    """Expand the cursor position to a :: chained path (std::fs, ...)."""
    start = col
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] in "_:"):
        start -= 1
    end = col
    while end < len(line) and (line[end].isalnum() or line[end] in "_:"):
        end += 1
    candidate = line[start:end].strip(":")
    if "::" in candidate and all(
        part and all(c.isalnum() or c == "_" for c in part)
        for part in candidate.split("::")
    ):
        return candidate
    return ""


# ---- Go to definition ----

@server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
def definition(params: lsp.DefinitionParams) -> Optional[lsp.Location]:
    uri = params.text_document.uri
    lines = documents.get(uri, "").split('\n')
    if params.position.line >= len(lines):
        return None
    word = _word_at(lines[params.position.line], params.position.character)
    syms = doc_symbols.get(uri)
    if not word or not syms:
        return None
    declared = (
        [(t[0], t[3]) for t in syms.tasks]
        + [(s[0], s[1]) for s in syms.shapes]
        + list(syms.doctrines) + list(syms.routes)
        + [(n, line) for n, _, line in syms.fixed + syms.pilots]
    )
    for name, line in declared:
        if name == word:
            # The declared name is the last whole-word match before any '=' or '('.
            head = re.split(r'[=(]', lines[line], maxsplit=1)[0]
            found = list(re.finditer(r'(?<!\w)' + re.escape(word) + r'(?!\w)', head))
            start = found[-1].start() if found else 0
            return lsp.Location(uri=uri, range=lsp.Range(
                start=lsp.Position(line=line, character=start),
                end=lsp.Position(line=line, character=start + len(word)),
            ))
    return None


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

    server.publish_diagnostics(uri, diagnostics + compiler_diagnostics.get(uri, []))


# ---- Compiler diagnostics (freak check) ----

# Overridden by the client's initializationOptions, then by the environment.
compiler = {
    "path": os.environ.get("FREAK_LSP_COMPILER", "freak"),
    "enabled": os.environ.get("FREAK_LSP_COMPILER_DIAGNOSTICS", "1") != "0",
    "missing": False,
}
compiler_diagnostics: dict[str, list] = {}
_check_generation: dict[str, int] = {}
_check_lock = threading.Lock()

RE_ANSI = re.compile(r'\x1b\[[0-9;]*m')
RE_COMPILER_HEAD = re.compile(r'^((?:[a-z]+ )?(?:error|warning)): (.+)$')
RE_COMPILER_AT = re.compile(r'^\s*--> (.+):(\d+):(\d+)\s*$')
RE_COMPILER_HINT = re.compile(r'^\s*\|\s*\^+ (\S.*)$')
RE_LINE_SUFFIX = re.compile(r' \(line \d+\)$')


def _uri_to_path(uri: str) -> Optional[str]:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path = url2pathname(unquote(parsed.path))
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"
    return path


def parse_compiler_output(output: str, path: str, text: str) -> list[lsp.Diagnostic]:
    """Turn `freak check` output into diagnostics for the checked file."""
    lines = text.split('\n')
    out = [RE_ANSI.sub('', raw).rstrip('\r') for raw in output.split('\n')]
    here = os.path.normcase(os.path.abspath(path))
    diagnostics = []
    for i, raw in enumerate(out):
        head = RE_COMPILER_HEAD.match(raw.strip())
        at = RE_COMPILER_AT.match(out[i + 1]) if head and i + 1 < len(out) else None
        if not at:
            continue
        kind, message = head.group(1), RE_LINE_SUFFIX.sub('', head.group(2))
        for follow in out[i + 2:i + 6]:
            hint = RE_COMPILER_HINT.match(follow)
            if hint:
                message += f" ({hint.group(1)})"
                break
        line, col = int(at.group(2)) - 1, int(at.group(3)) - 1
        there = os.path.normcase(os.path.abspath(
            os.path.join(os.path.dirname(path), at.group(1))))
        if there != here:
            message = f"{at.group(1)}:{line + 1}:{col + 1}: {message}"
            line, col = 0, 0
        source_line = lines[line].rstrip('\r') if 0 <= line < len(lines) else ""
        if col == 0:
            # Type errors point at column 1; underline the statement instead.
            col = len(source_line) - len(source_line.lstrip())
            end = len(source_line.rstrip())
        else:
            end = col
            while end < len(source_line) and (source_line[end].isalnum() or source_line[end] == '_'):
                end += 1
        diagnostics.append(lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=max(line, 0), character=col),
                end=lsp.Position(line=max(line, 0), character=max(end, col + 1)),
            ),
            severity=(lsp.DiagnosticSeverity.Warning if kind.endswith("warning")
                      else lsp.DiagnosticSeverity.Error),
            source="freak",
            message=message,
        ))
    return diagnostics


def _schedule_compiler_check(uri: str):
    """Run `freak check` on the saved file without blocking the server."""
    if not compiler["enabled"] or compiler["missing"]:
        return
    path = _uri_to_path(uri)
    if not path or not os.path.isfile(path):
        return
    with _check_lock:
        generation = _check_generation.get(uri, 0) + 1
        _check_generation[uri] = generation
    threading.Thread(target=_run_compiler_check, args=(uri, path, generation),
                     daemon=True).start()


def _run_compiler_check(uri: str, path: str, generation: int):
    executable = shutil.which(compiler["path"])
    if executable is None:
        compiler["missing"] = True
        server.show_message_log(
            f"FREAK compiler '{compiler['path']}' not found; compiler diagnostics are off")
        return
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            saved = handle.read()
        result = subprocess.run(
            [executable, "check", os.path.basename(path)],
            cwd=os.path.dirname(path) or ".", capture_output=True, timeout=30,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "NO_COLOR": "1"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        server.show_message_log(f"freak check failed: {error}")
        return
    output = (result.stdout + b"\n" + result.stderr).decode("utf-8", errors="replace")
    found = parse_compiler_output(output, path, saved)
    with _check_lock:
        if _check_generation.get(uri) != generation or uri not in documents:
            return
        compiler_diagnostics[uri] = found
    _publish_diagnostics(uri, documents[uri])


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
