#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import sys
sys.dont_write_bytecode = True
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import importlib.util
import shutil
from types import SimpleNamespace
from unittest import mock

BASE = Path(__file__).resolve().parents[2] / 'skills/e2e-reviewer/scripts'
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
lexer = load('lexer', BASE/'scope-lexer.py')
def resolve_rg():
    configured = os.environ.get('E2E_SMELL_RG_BIN')
    paths = [configured] if configured else ['/opt/homebrew/bin/rg','/usr/local/bin/rg','/usr/bin/rg','/bin/rg']
    for item in paths:
        path = Path(item)
        if path.is_absolute() and path.is_file() and os.access(path, os.X_OK): return str(path)
    raise RuntimeError('Set E2E_SMELL_RG_BIN to an absolute executable ripgrep path')
RG = resolve_rg()
CASES = [b'', b'const x = 1;\n', b"import {test} from '@playwright/test';",
 b"import {test} from '\\u0040playwright/test';", b"export {test} from `@playwright/test`;",
 b"// import {test} from '@playwright/test';\nimport './a';",
 b"const x = /import from '@playwright\\/test'/; import './b';",
 b"const x = `template ${require('@playwright/test')} tail`;",
 b"import {test} from '@play\\\nwright/test'; import './a\\\nb';",
 b"const a = 'one\ntwo'; /* block\n */ export {x} from '../a';",
 b"import x from './a'; import y from './b'; require('../z');",
 b"import x from './__E2E_STR__b'; import('./c');",
 b"require('\\x40playwright/test'); require('\\u{40}playwright/test');",
 b"require('\\u{}playwright/test'); require('\\8playwright/test');",
 b"if (x) /a[b/]c/.test(x); export * from './x';",
 b"const x = `outer ${`inner ${require('@playwright/test')}`} tail`;",
 b"import {x}\r\nfrom './a';\r\n",
]


# Deliberately include malformed JavaScript: equivalence is to the shell
# state machines, not a standards-compliant JavaScript parser.
for escaped in (r'\u0040', r'\u{40}', r'\x40', r'\u040', r'\u004G', r'\u{}',
                r'\u{xyz}', r'\u{000040}', r'\u{100000}', r'\x4', r'\xGG',
                r'\0', r'\07', r'\8', r'\n', r'\t', r'\v', r'\@'):
    CASES.append(("require('"+escaped+"playwright/test'); import './after';").encode())
for prefix in ('return ', 'throw ', 'case ', 'yield ', 'x => ', 'if (x) ',
               'while (x) ', 'for (;;) ', 'with (x) ', 'x / ', 'x = ', ''):
    CASES.append((prefix+"/[/\\\\]import('./phantom')/g; import './after';").encode())
for ref in ('./a', '../a', './a\\b', './a__E2E_STR__b', './a__E2E_END__b',
            './a; import __E2E_STR__../b', './a\rb', './a\tb'):
    for form in ("import X from '%s';", "require('%s');", "import('%s');", "import '%s';"):
        CASES.append((form % ref).encode())
CASES.extend([
 b"import/*gap*/x/*gap*/from/*gap*/'./a';",
 b"import x from './a' // tail\nexport * from '../b'",
 b"const x = 'open\\\nclose'; require('./a');",
 b"const x = `literal ${ /* comment } */ require('./a') } tail`;",
 b"const x = `literal ${ { key: `nested ${require('./b')}` } } tail`;",
 b"const x = `unclosed ${ 'quote }';\nrequire('./a')",
 b"/* open\n comment */ import x from './a'; /* no close",
 b"// one\\\nimport x from './a';",
 b"const x = /[a\\/\n]b/; import './a';",
 b"const x = /unterminated\nimport './a';",
 b"fooimport X from './a'; rexport X from './b'; myrequire('./c');",
 b"import x from './a' import y from './b' export z from './c'",
 b"import x from './a'; from './b'; import y from './c'",
 b"import x from `./a${require('./b')}`;",
 b"import x from './a\\'; import y from './b';",
 b"import x from '\\u002e/a'; require(`../b`);",
 b"require('./x');\vimport\f'./y';\rrequire\t('../z');",
])

class Equivalence(unittest.TestCase):
    def test_tiny_shell_differential(self):
        for locale in ('C', 'C.UTF-8'):
            with self.subTest(locale=locale): self.shell_differential(locale)

    def shell_differential(self, locale):
        with tempfile.TemporaryDirectory(prefix='lexer-',dir=str(Path('/tmp').resolve())) as tmp:
            path = Path(tmp)/'entry.ts'
            for source in CASES:
                with self.subTest(source=source):
                    path.write_bytes(source)
                    script = '''source "$1"
scanner_rg() { "$RG_BIN" "$@"; }
source_executable_code "$2" @playwright/test
'''
                    result = subprocess.run(['/bin/bash','-p','-c',script,'bash',str(BASE/'scope-source.sh'),str(path)],env={'PATH':'/usr/bin:/bin','LC_ALL':locale,'RG_BIN':RG},capture_output=True,check=True)
                    self.assertEqual(result.stdout,lexer.executable(source).encode('latin1'))
                    script = '''source "$1"
scanner_rg() { "$RG_BIN" "$@"; }
if source_has_playwright_module_reference "$2"; then printf '1\\n'; else printf '0\\n'; fi
source_relative_module_references "$2"
'''
                    result = subprocess.run(['/bin/bash','-p','-c',script,'bash',str(BASE/'scope-source.sh'),str(path)],env={'PATH':'/usr/bin:/bin','LC_ALL':locale,'RG_BIN':RG},capture_output=True)
                    lines = result.stdout.decode().split('\n')
                    if lines[-1] == '': lines.pop()
                    self.assertEqual(lexer.metadata(source, allow_positive_for_differential=True),(lines[0]=='1',lines[1:]))
    def test_unproved_transport_falls_back(self):
        for source in (b'\0',b'\xff',b'x'*32769,b"require('@playwright/test')"):
            with self.assertRaises(lexer.Fallback): lexer.metadata(source)


class DenseInputBudget(unittest.TestCase):
    def test_dense_inputs_fall_back_within_subprocess_budget(self):
        # A hung regex cannot hang CI: the child has a generous hard deadline.
        # Assert behavior, not host-dependent millisecond performance.
        program = r"""
import importlib.util, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('scope_lexer', sys.argv[1])
lexer = importlib.util.module_from_spec(spec); spec.loader.exec_module(lexer)
cases = [
    (b'import '*4681, 'dense module tokens'),
    (b'/ '*16384, 'dense slash tokens'),
    (b'im/**/port '*32 + b'import '*33, 'dense executable module tokens'),
    (b'im/**/port '*31 + b'import '*34 + b" require('@playwright/test')", 'dense executable module tokens'),
]
for source, reason in cases:
    try: lexer.metadata(source)
    except lexer.Fallback as error:
        assert reason in str(error), str(error)
    else: raise AssertionError('dense input did not fall back')
source = b'import '*64
source += b'x'*(32768-len(source))
assert lexer.metadata(source) == (False, [])
assert lexer.metadata(b'/ '*64) == (False, [])
print('dense fallback and 64-token boundaries passed')
"""
        result = subprocess.run([sys.executable,'-I','-B','-c',program,str(BASE/'scope-lexer.py')],
                                capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('64-token boundaries passed', result.stdout)


class GraphGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='lexer-guard-', dir=str(Path('/tmp').resolve()))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        for name in ('scope-graph.py','scope-source.sh','scope-lexer.py'):
            shutil.copyfile(BASE/name, self.base/name)
        self.engine = load('scope_graph_guards', self.base/'scope-graph.py')
        self.node = self.base/'source.ts'; self.node.write_text("import './relative';\n")
        self.args = SimpleNamespace(helper=str(self.base/'scope-source.sh'),project=str(self.base),rg=RG,rg_errors=str(self.base/'errors'))
        env = dict(os.environ); env.pop('E2E_SMELL_RG_BIN', None); env['LC_ALL'] = 'C'
        self.environment = mock.patch.dict(os.environ, env, clear=True)
        self.environment.start(); self.addCleanup(self.environment.stop)

    def graph(self):
        graph = self.engine.Graph(self.args, {'version':1,'project':str(self.base),'nodes':{},'edges':{},'witnesses':{}})
        self.addCleanup(graph.close)
        return graph

    def test_negative_eager_imports_without_helper(self):
        graph = self.graph(); self.assertIsNotNone(graph.lexer)
        with mock.patch.object(graph, 'request', side_effect=AssertionError('unexpected helper')):
            self.assertFalse(graph.direct(str(self.node)))
            self.assertEqual(graph.imports(str(self.node)), ['./relative'])
        graph.witnesses.validate()

    def test_ineligible_source_uses_original_request(self):
        for source in (b"require('@playwright/test')", b'// \xff', b'x'*32769):
            with self.subTest(source=source[:40]):
                self.node.write_bytes(source); graph = self.graph()
                with mock.patch.object(graph, 'request', return_value=['0']) as request:
                    self.assertFalse(graph.direct(str(self.node)))
                    request.assert_called_once_with('direct',str(self.node))

    def test_explicit_rg_or_unsupported_locale_disables(self):
        for updates in ({'E2E_SMELL_RG_BIN':RG},{'LC_ALL':'en_US.UTF-8'}):
            with mock.patch.dict(os.environ,updates): self.assertIsNone(self.graph().lexer)
        self.args.rg = str(self.base/'wrapper-rg')
        self.assertIsNone(self.graph().lexer)

    def test_changed_helper_disables(self):
        with Path(self.args.helper).open('a') as stream: stream.write('\n# wrapper\n')
        self.assertIsNone(self.graph().lexer)

    def test_source_mutation_after_fast_read_fails_validation(self):
        graph = self.graph(); self.assertFalse(graph.direct(str(self.node)))
        self.node.write_text('changed source')
        with self.assertRaises(self.engine.ScopeError): graph.witnesses.validate()

    def test_lexer_module_mutation_fails_validation(self):
        graph = self.graph(); self.assertIsNotNone(graph.lexer)
        with (self.base/'scope-lexer.py').open('a') as stream: stream.write('\n# mutation\n')
        with self.assertRaises(self.engine.ScopeError): graph.witnesses.validate()

    def test_symlink_source_rejected(self):
        graph = self.graph(); link = self.base/'link.ts'; link.symlink_to(self.node)
        with self.assertRaises((self.engine.ScopeError, OSError)): graph.direct(str(link))

if __name__ == '__main__': unittest.main()
