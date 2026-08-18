'use strict';

const fs = require('fs');
const path = require('path');
const Module = require('module');

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', chunk => chunks.push(chunk));
    process.stdin.on('end', () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
      catch (error) { reject(error); }
    });
    process.stdin.on('error', reject);
  });
}

function normalizeMemory(memory) {
  const now = new Date().toISOString();
  const tags = Array.isArray(memory.tags) ? memory.tags : [];
  const sourceIds = Array.isArray(memory.source_msg_ids) ? memory.source_msg_ids : [];
  return {
    id: String(memory.id),
    character_id: String(memory.character_id || 'furina'),
    category: String(memory.category || '话题历史'),
    content: String(memory.content || '').trim(),
    confidence: Number.isFinite(Number(memory.confidence)) ? Number(memory.confidence) : 0.65,
    tags,
    source_msg_ids: sourceIds,
    memory_kind: String(memory.memory_kind || 'user_fact'),
    importance: Number.isFinite(Number(memory.importance)) ? Number(memory.importance) : 0.5,
    emotional_weight: Number.isFinite(Number(memory.emotional_weight)) ? Number(memory.emotional_weight) : 0.3,
    status: String(memory.status || 'active'),
    pinned: Boolean(memory.pinned),
    last_used_at: String(memory.last_used_at || ''),
    usage_count: Number(memory.usage_count || 0),
    metadata: memory.metadata || {},
    created_at: String(memory.created_at || now),
    updated_at: String(memory.updated_at || memory.created_at || now),
  };
}

(async () => {
  const req = await readStdin();
  const root = path.resolve(req.upstream);
  const tsRoot = path.resolve(req.typescript_root);
  const ts = require(path.join(tsRoot, 'node_modules', 'typescript'));
  const originalResolveFilename = Module._resolveFilename;
  const originalLoad = Module._load;

  Module._resolveFilename = function resolveFilename(request, parent, isMain, options) {
    if (request.startsWith('@/')) {
      const mapped = path.join(root, 'src', request.slice(2));
      for (const candidate of [mapped, `${mapped}.ts`, `${mapped}.tsx`, path.join(mapped, 'index.ts')]) {
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
      }
    }
    return originalResolveFilename.call(this, request, parent, isMain, options);
  };

  require.extensions['.ts'] = function loadTs(module, filename) {
    const source = fs.readFileSync(filename, 'utf8');
    const output = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: filename,
    });
    module._compile(output.outputText, filename);
  };

  const mockDb = { getDb: () => { throw new Error('LumiMuse DB path disabled; Furina supplies retrieval deps'); } };
  const mockCategory = {
    inferMemoryDefaults: () => ({ memory_kind: 'user_fact', importance: 0.5, emotional_weight: 0.3 }),
  };
  const mockEngine = { retrieveRelevantMemories: () => [] };
  const mockProfile = {
    readMemoryProfile: () => null,
    renderMemoryProfile: profile => {
      if (!profile) return '';
      return [profile.relationship_state, profile.recent_story_state, profile.user_profile_summary]
        .filter(Boolean).join('\n');
    },
  };
  const mockNormalize = { normalizeMemoryRow: normalizeMemory };
  const mockEmbeddings = {
    embedText: async () => { throw new Error('embedding disabled'); },
    loadReadyMemoryEmbeddings: () => [],
    rankEmbeddingRows: () => [],
  };
  const mockReranker = { rerankDocuments: async () => [] };
  const mockTokenCounter = {
    estimateTokens: text => Math.max(1, Math.ceil(Buffer.byteLength(String(text || ''), 'utf8') / 4)),
  };
  const mocks = {
    '@/lib/db': mockDb,
    '@/lib/memory-category': mockCategory,
    '@/lib/memory-engine': mockEngine,
    '@/lib/memory-profile': mockProfile,
    '@/lib/memory-normalization': mockNormalize,
    '@/lib/memory-embeddings': mockEmbeddings,
    '@/lib/memory-reranker': mockReranker,
    '@/lib/token-counter': mockTokenCounter,
  };

  Module._load = function loadWithMocks(request, parent, isMain) {
    if (Object.prototype.hasOwnProperty.call(mocks, request)) return mocks[request];
    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    const retrieval = require(path.join(root, 'src/lib/memory-retrieval.ts'));
    const memories = (req.memories || []).map(normalizeMemory).filter(m => m.content);
    const priority = (req.priority_memories || []).map(normalizeMemory).filter(m => m.content);
    const settings = {
      memory_inject: true,
      limit_inject: true,
      memory_max_inject: Number(req.final_top_k || 14),
      memory_engine: {
        enabled: true,
        allow_memory_context_in_chat: true,
        allow_external_memory_payloads: false,
        retrieval_mode: 'local',
        embedding_enabled: false,
        embedding_api_base: '', embedding_api_key: '', embedding_model: '', embedding_dimension: 1024,
        reranker_enabled: false,
        reranker_api_base: '', reranker_api_key: '', reranker_model: '',
        fallback_local_enabled: true,
        memory_package_token_budget: Number(req.token_budget || 1400),
        retrieval_token_budget: 8000,
        vector_top_k: 30, keyword_top_k: 24, reranker_top_k: 24,
        final_top_k: Number(req.final_top_k || 14),
        embedding_timeout_ms: 500, reranker_timeout_ms: 500, total_retrieval_timeout_ms: 1800,
        profile_token_budget: 500,
      },
    };
    const tokenCounter = text => Math.max(1, Math.ceil(Buffer.byteLength(String(text || ''), 'utf8') / 4));
    const result = await retrieval.retrieveWorkingMemoryPackage({
      characterId: 'furina',
      queryText: String(req.query || ''),
      settings,
      deps: {
        localRetrieve: () => memories,
        loadPriorityMemories: () => priority,
        tokenCounter,
        loadMemoryProfile: () => null,
        markMemoriesUsed: () => {},
      },
    });
    process.stdout.write(JSON.stringify({
      ok: true,
      text: result.text || '',
      tokenCount: result.tokenCount || 0,
      mode: result.mode,
      selectedIds: (result.selectedMemories || []).map(m => String(m.id)),
      diagnostics: result.diagnostics || {},
    }));
  } finally {
    Module._load = originalLoad;
    Module._resolveFilename = originalResolveFilename;
  }
})().catch(error => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
