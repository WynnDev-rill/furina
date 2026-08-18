'use strict';

const fs = require('fs');
const path = require('path');
const Module = require('module');

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', c => chunks.push(c));
    process.stdin.on('end', () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
      catch (e) { reject(e); }
    });
    process.stdin.on('error', reject);
  });
}

(async () => {
  const req = await readStdin();
  const root = path.resolve(req.upstream);
  const tsRoot = path.resolve(req.typescript_root);
  const ts = require(path.join(tsRoot, 'node_modules', 'typescript'));
  const originalLoad = Module._load;

  require.extensions['.ts'] = function loadTs(module, filename) {
    const source = fs.readFileSync(filename, 'utf8');
    const output = ts.transpileModule(source, {
      compilerOptions: { esModuleInterop: true, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
      fileName: filename,
    });
    module._compile(output.outputText, filename);
  };

  // state-updates.ts imports stages.ts for a different exported function.
  // The two functions Furina invokes do not call it; keep the original target
  // functions untouched while satisfying the module boundary explicitly.
  Module._load = function loadWithBoundary(request, parent, isMain) {
    if (request === './stages.ts' && parent && parent.filename.endsWith('state-updates.ts')) {
      return { resolveStageTransition: () => ({ changed: false }) };
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    const mod = require(path.join(root, 'src/lib/engine/state-updates.ts'));
    const state = req.state || {};
    const decay = mod.applyTimeDecay(state, Math.max(0, Number(req.hours_since || 0)));
    const impact = mod.calculateMessageImpact(
      Number(req.sentiment || 0),
      req.topic_depth || 'shallow',
      Boolean(req.is_emotional),
      Boolean(req.is_question),
      state,
    );
    process.stdout.write(JSON.stringify({ decay, impact }));
  } finally {
    Module._load = originalLoad;
  }
})().catch(error => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
