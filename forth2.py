#!/usr/bin/env python3
"""Forth interpreter — stack-based programming language.

Supports: arithmetic, stack ops, definitions, conditionals, loops,
variables, constants, string I/O, comments.

Usage:
    python forth2.py -e ": square dup * ; 5 square ."
    python forth2.py --test
"""
import sys

class Forth:
    def __init__(self):
        self.stack = []
        self.rstack = []  # return stack
        self.dict = {}
        self.vars = {}
        self.output = []
        self._next_var = 1000
        self._setup_builtins()

    def _setup_builtins(self):
        b = self.dict
        b['+'] = lambda: self._binop(lambda a,b: a+b)
        b['-'] = lambda: self._binop(lambda a,b: a-b)
        b['*'] = lambda: self._binop(lambda a,b: a*b)
        b['/'] = lambda: self._binop(lambda a,b: a//b)
        b['mod'] = lambda: self._binop(lambda a,b: a%b)
        b['negate'] = lambda: self.stack.append(-self.stack.pop())
        b['abs'] = lambda: self.stack.append(abs(self.stack.pop()))
        b['max'] = lambda: self._binop(lambda a,b: max(a,b))
        b['min'] = lambda: self._binop(lambda a,b: min(a,b))
        b['='] = lambda: self._binop(lambda a,b: -1 if a==b else 0)
        b['<'] = lambda: self._binop(lambda a,b: -1 if a<b else 0)
        b['>'] = lambda: self._binop(lambda a,b: -1 if a>b else 0)
        b['<>'] = lambda: self._binop(lambda a,b: -1 if a!=b else 0)
        b['and'] = lambda: self._binop(lambda a,b: a&b)
        b['or'] = lambda: self._binop(lambda a,b: a|b)
        b['xor'] = lambda: self._binop(lambda a,b: a^b)
        b['not'] = lambda: self.stack.append(~self.stack.pop())
        b['dup'] = lambda: self.stack.append(self.stack[-1])
        b['drop'] = lambda: self.stack.pop()
        b['swap'] = lambda: self._swap()
        b['over'] = lambda: self.stack.append(self.stack[-2])
        b['rot'] = lambda: self._rot()
        b['nip'] = lambda: (self._swap(), self.stack.pop())
        b['tuck'] = lambda: (self._swap(), self.stack.insert(-1, self.stack[-1]))
        b['.'] = lambda: self.output.append(str(self.stack.pop()))
        b['.s'] = lambda: self.output.append(f"<{len(self.stack)}> " + " ".join(str(x) for x in self.stack))
        b['cr'] = lambda: self.output.append('\n')
        b['emit'] = lambda: self.output.append(chr(self.stack.pop()))
        b['>r'] = lambda: self.rstack.append(self.stack.pop())
        b['r>'] = lambda: self.stack.append(self.rstack.pop())
        b['r@'] = lambda: self.stack.append(self.rstack[-1])
        b['depth'] = lambda: self.stack.append(len(self.stack))
        b['!'] = lambda: self._store()
        b['@'] = lambda: self._fetch()

    def _binop(self, fn):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(fn(a, b))

    def _swap(self):
        self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]

    def _rot(self):
        a = self.stack.pop(-3)
        self.stack.append(a)

    def _store(self):
        addr = self.stack.pop(); val = self.stack.pop()
        self.vars[addr] = val

    def _fetch(self):
        addr = self.stack.pop()
        self.stack.append(self.vars.get(addr, 0))

    def eval(self, text: str) -> str:
        tokens = self._tokenize(text)
        self._exec(tokens, 0, len(tokens))
        result = ' '.join(self.output)
        self.output.clear()
        return result

    def _tokenize(self, text):
        tokens = []; i = 0; text = text.strip()
        while i < len(text):
            if text[i] in ' \t\n': i += 1; continue
            if text[i] == '(' :  # comment
                j = text.index(')', i); i = j+1; continue
            if text[i:i+2] == '\\':  # line comment
                j = text.find('\n', i)
                i = j+1 if j >= 0 else len(text); continue
            if text[i:i+2] == '."':  # string
                j = text.index('"', i+2)
                tokens.append(('str', text[i+2:j].strip()))
                i = j+1; continue
            j = i
            while j < len(text) and text[j] not in ' \t\n': j += 1
            tokens.append(text[i:j].lower())
            i = j
        return tokens

    def _exec(self, tokens, start, end):
        i = start
        while i < end:
            t = tokens[i]
            if isinstance(t, tuple) and t[0] == 'str':
                self.output.append(t[1]); i += 1; continue
            if t == ':':
                # Definition
                name = tokens[i+1]; j = i+2
                body = []
                while tokens[j] != ';': body.append(tokens[j]); j += 1
                self.dict[name] = ('word', body)
                i = j + 1; continue
            if t == 'variable':
                name = tokens[i+1]; addr = self._next_var; self._next_var += 1
                self.dict[name] = ('var', addr); i += 2; continue
            if t == 'constant':
                name = tokens[i+1]; val = self.stack.pop()
                self.dict[name] = ('const', val); i += 2; continue
            if t == 'if':
                # Find matching then/else
                then_i, else_i = self._find_if_end(tokens, i)
                cond = self.stack.pop()
                if cond != 0:
                    self._exec(tokens, i+1, else_i if else_i else then_i)
                elif else_i:
                    self._exec(tokens, else_i+1, then_i)
                i = then_i + 1; continue
            if t == 'do':
                limit_i = self._find_match(tokens, i, 'do', 'loop')
                idx = self.stack.pop(); limit = self.stack.pop()
                while idx < limit:
                    self.rstack.append(idx)
                    self._exec(tokens, i+1, limit_i)
                    self.rstack.pop()
                    idx += 1
                i = limit_i + 1; continue
            if t == 'begin':
                until_i = self._find_word(tokens, i+1, 'until')
                while True:
                    self._exec(tokens, i+1, until_i)
                    if self.stack.pop() != 0: break
                i = until_i + 1; continue
            if t == 'i': self.stack.append(self.rstack[-1]); i += 1; continue
            # Lookup
            if t in self.dict:
                entry = self.dict[t]
                if isinstance(entry, tuple):
                    if entry[0] == 'word': self._exec(entry[1], 0, len(entry[1]))
                    elif entry[0] == 'var': self.stack.append(entry[1])
                    elif entry[0] == 'const': self.stack.append(entry[1])
                else:
                    entry()
                i += 1; continue
            # Number
            try: self.stack.append(int(t)); i += 1; continue
            except ValueError: pass
            raise ValueError(f"Unknown word: {t}")

    def _find_if_end(self, tokens, start):
        depth = 0; else_i = None
        for i in range(start, len(tokens)):
            if tokens[i] == 'if': depth += 1
            elif tokens[i] == 'else' and depth == 1: else_i = i
            elif tokens[i] == 'then':
                depth -= 1
                if depth == 0: return i, else_i
        raise ValueError("Missing THEN")

    def _find_match(self, tokens, start, open_w, close_w):
        depth = 0
        for i in range(start, len(tokens)):
            if tokens[i] == open_w: depth += 1
            elif tokens[i] == close_w: depth -= 1; 
            if depth == 0: return i
        raise ValueError(f"Missing {close_w}")

    def _find_word(self, tokens, start, word):
        for i in range(start, len(tokens)):
            if tokens[i] == word: return i
        raise ValueError(f"Missing {word}")


def test():
    print("=== Forth Interpreter Tests ===\n")
    f = Forth()

    assert f.eval("3 4 + .") == "7"
    print("✓ Arithmetic: 3 4 + = 7")

    assert f.eval("10 3 - .") == "7"
    assert f.eval("6 7 * .") == "42"
    print("✓ Sub/Mul")

    f.eval(": square dup * ;")
    assert f.eval("5 square .") == "25"
    print("✓ Definition: square(5) = 25")

    assert f.eval("3 4 > .") == "0"
    assert f.eval("5 3 > .") == "-1"
    print("✓ Comparison")

    assert f.eval("1 if 42 else 0 then .") == "42"
    assert f.eval("0 if 42 else 99 then .") == "99"
    print("✓ If/else/then")

    r = f.eval("5 0 do i . loop")
    assert "0" in r and "4" in r
    print(f"✓ Do loop: {r}")

    f.eval("variable x")
    f.eval("42 x !")
    assert f.eval("x @ .") == "42"
    print("✓ Variables")

    f.eval("100 constant hundred")
    assert f.eval("hundred .") == "100"
    print("✓ Constants")

    f.eval(": factorial dup 1 > if dup 1 - factorial * then ;")
    assert f.eval("5 factorial .") == "120"
    print("✓ Recursive factorial(5) = 120")

    assert f.eval('." Hello World"') == "Hello World"
    print('✓ String output')

    print("\nAll tests passed! ✓")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--test": test()
    elif args[0] == "-e": f = Forth(); print(f.eval(args[1]))
