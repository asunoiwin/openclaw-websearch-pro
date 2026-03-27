const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFile } = require('node:child_process');

const DEFAULT_POLICY = require('./default-policy.json');

const HOME = os.homedir();
const SCRIPT = path.join(__dirname, '..', 'scripts', 'search_orchestrator.py');
const DEFAULT_PREVIEW = path.join(HOME, '.openclaw', 'workspace', '.openclaw', 'search-orchestrator-preview.json');

function ensureDir(file) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
}

function writeJson(file, value) {
  ensureDir(file);
  fs.writeFileSync(file, JSON.stringify(value, null, 2), 'utf8');
}

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return fallback;
  }
}

function execJson(args) {
  return new Promise((resolve, reject) => {
    execFile('python3', [SCRIPT, ...args], { timeout: 120000, maxBuffer: 20 * 1024 * 1024 }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(stderr || stdout || error.message));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (parseError) {
        reject(new Error(`invalid_json:${parseError.message}`));
      }
    });
  });
}

function resolveEventAgentId(event, ctx) {
  const direct = String(ctx?.agentId || event?.agentId || '').trim();
  if (direct) return direct;
  const nested = String(event?.agent?.id || event?.agent?.name || event?.context?.agentId || '').trim();
  if (nested) return nested;
  const sessionKey = String(ctx?.sessionKey || event?.sessionKey || event?.session || '').trim();
  const match = sessionKey.match(/^agent:([^:]+):/);
  return match?.[1] || 'main';
}

function getPromptText(event) {
  return String(event?.prompt || '').trim();
}

function isSystemPrompt(prompt) {
  if (!prompt) return true;
  if (/^\[cron:[^\]]+\]/m.test(prompt)) return true;
  if (/你是任务巡检员|你是每日任务汇总助手|你是多 agent 编排调度器/.test(prompt)) return true;
  if (/Read HEARTBEAT\.md|Current time:|Multi-agent routing decision:/i.test(prompt)) return true;
  return false;
}

function normalizeList(values) {
  if (!Array.isArray(values)) return [];
  return values.map((item) => String(item || '').trim()).filter(Boolean);
}

function shouldForceSearch(prompt, policy = DEFAULT_POLICY) {
  const text = String(prompt || '').toLowerCase();
  if (!text) return false;
  if ((policy.skipKeywords || []).some((kw) => text.includes(String(kw).toLowerCase()))) return false;
  if ((policy.forceKeywords || []).some((kw) => text.includes(String(kw).toLowerCase()))) return true;
  if ((policy.questionSignals || []).some((kw) => text.includes(String(kw).toLowerCase()))) return true;
  return /github|clawhub|插件|plugin|skill|搜索|调研|专利|竞品|知乎|抖音|小红书|百度|google|reddit|rebbit|官网|文档/.test(text);
}

function inferIntent(prompt) {
  const text = String(prompt || '').toLowerCase();
  if (/github|clawhub|plugin|plugins|skill|skills|安装/.test(text)) return 'plugin_discovery';
  if (/小红书|抖音|知乎|b站|bilibili|微博/.test(text)) return 'social_research';
  if (/百度|google|谷歌|bing|搜索引擎/.test(text)) return 'web_search';
  if (/专利|竞品|调研|资料|文档|官网/.test(text)) return 'research';
  return 'auto';
}

function buildGuidance(pluginConfig, prompt) {
  const intent = pluginConfig.defaultIntent && pluginConfig.defaultIntent !== 'auto'
    ? pluginConfig.defaultIntent
    : inferIntent(prompt);
  return [
    'Search orchestration guidance:',
    '- 当前任务涉及外部信息时，先使用 search_orchestrator_research 建立证据集，再回答。',
    '- 先跑多引擎搜索，再对高价值结果做深度提取；若结果差，自动扩展查询再搜索，不要停在第一层搜索结果。',
    '- 对 GitHub、ClawHub、Google、Baidu、Reddit、小红书、抖音、知乎等来源，优先保留链接、证据、时间和二次搜索线索。',
    `- 建议意图：${intent}`,
    '- 对 DOM 获取差或 JS 很重的页面，优先使用 reader/distill 提取，不要因为首层抓取差就放弃。'
  ].join('\n');
}

function isInjectionEnabled(pluginConfig = {}) {
  if (pluginConfig.enabled === false) return false;
  if (pluginConfig.injectBeforePromptBuild === false) return false;
  if (pluginConfig.proactiveSearch === false) return false;
  return true;
}

function shouldSkipAgent(agentId, pluginConfig = {}) {
  const forced = normalizeList(pluginConfig.forceAgentIds);
  const skipped = normalizeList(pluginConfig.skipAgentIds);
  if (forced.length) return !forced.includes(agentId);
  return skipped.includes(agentId);
}

const plugin = {
  register(api) {
    api.logger.info?.('[openclaw-search-orchestrator] plugin registered');

    api.registerTool({
      name: 'search_orchestrator_status',
      label: 'Search Orchestrator Status',
      description: 'Inspect the latest search orchestration preview.',
      parameters: { type: 'object', properties: {}, required: [] },
      execute: async () => {
        const details = readJson((api.pluginConfig || {}).previewFile || DEFAULT_PREVIEW, null);
        return {
          content: [{ type: 'text', text: details ? `search orchestrator ready: ${details.intent || 'auto'}` : 'search orchestrator ready: no preview yet' }],
          details: { success: true, details },
        };
      },
    });

    api.registerTool({
      name: 'search_orchestrator_extract',
      label: 'Search Orchestrator Extract',
      description: 'Deep extract a specific page, including fallback for JS-heavy pages.',
      parameters: {
        type: 'object',
        properties: {
          url: { type: 'string' },
          query: { type: 'string' }
        },
        required: ['url']
      },
      execute: async (args = {}) => {
        const result = await execJson(['extract', JSON.stringify({ url: String(args.url || ''), query: String(args.query || '') })]);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
          details: { success: true, result },
        };
      },
    });

    api.registerTool({
      name: 'search_orchestrator_research',
      label: 'Search Orchestrator Research',
      description: 'Run unified multi-engine search, deep extraction, refinement, and evidence ranking.',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string' },
          intent: { type: 'string' },
          max_results: { type: 'number' },
          max_deep_results: { type: 'number' },
          max_refine_rounds: { type: 'number' }
        },
        required: ['query']
      },
      execute: async (args = {}) => {
        const cfg = api.pluginConfig || {};
        const payload = {
          query: String(args.query || ''),
          intent: String(args.intent || cfg.defaultIntent || 'auto'),
          max_results: Number(args.max_results || cfg.maxInitialResults || 8),
          max_deep_results: Number(args.max_deep_results || cfg.maxDeepResults || 5),
          max_refine_rounds: Number(args.max_refine_rounds || cfg.maxRefineRounds || 2),
          site_profiles: cfg.siteProfiles || DEFAULT_POLICY.siteProfiles,
        };
        const result = await execJson(['research', JSON.stringify(payload)]);
        writeJson(cfg.previewFile || DEFAULT_PREVIEW, result);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
          details: { success: true, result },
        };
      },
    });

    api.on('before_prompt_build', async (event, ctx) => {
      const pluginConfig = api.pluginConfig || {};
      if (!isInjectionEnabled(pluginConfig)) return;
      const agentId = resolveEventAgentId(event, ctx);
      if (shouldSkipAgent(agentId, pluginConfig)) return;
      const prompt = getPromptText(event);
      if (isSystemPrompt(prompt)) return;
      if (!shouldForceSearch(prompt, DEFAULT_POLICY)) return;
      const preview = {
        generatedAt: new Date().toISOString(),
        agentId,
        intent: inferIntent(prompt),
        proactiveSearch: true,
        promptPreview: prompt.slice(0, 500)
      };
      writeJson(pluginConfig.previewFile || DEFAULT_PREVIEW, preview);
      return {
        prependContext: buildGuidance(pluginConfig, prompt)
      };
    });
  }
};

plugin.__private = {
  shouldForceSearch,
  inferIntent,
  isInjectionEnabled,
  shouldSkipAgent,
};

module.exports = plugin;
