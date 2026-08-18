import { pathToFileURL } from 'url';
import path from 'path';

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const req = JSON.parse(Buffer.concat(chunks).toString('utf8'));
const modulePath = path.join(req.upstream, 'src/lib/engine/state-updates.ts');
const mod = await import(pathToFileURL(modulePath).href);
const state = req.state || {};
const hours = Math.max(0, Number(req.hours_since || 0));
const decay = mod.applyTimeDecay(state, hours);
const impact = mod.calculateMessageImpact(
  Number(req.sentiment || 0),
  req.topic_depth || 'shallow',
  Boolean(req.is_emotional),
  Boolean(req.is_question),
  state,
);
process.stdout.write(JSON.stringify({decay, impact}));
