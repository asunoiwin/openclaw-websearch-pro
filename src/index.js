const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFile } = require('node:child_process');

const DEFAULT_POLICY = require('./default-policy.json');

const HOME = os.homedir();
const SCRIPT = path.join(__dirname, '..', 'scripts', 'search_orchestrator.py');
const AUTH_SCRIPT = path.join(__dirname, '..', 'scripts', 'auth_workflow.py');
const DEFAULT_PREVIEW = path.join(HOME, '.openclaw', 'workspace', '.openclaw', 'websearch-pro-preview.json');
const DEFAULT_AUTH_PREVIEW = path.join(HOME, '.openclaw', 'workspace', '.openclaw', 'websearch-pro-auth-preview.json');
const AUTH_SITES = new Set(['xiaohongshu', 'douyin', 'zhihu', 'csdn', 'tieba', 'wenku', 'weibo', 'x']);
const DOMAIN_TO_AUTH_SITE = new Map([
  ['xiaohongshu.com', 'xiaohongshu'],
  ['douyin.com', 'douyin'],
  ['zhihu.com', 'zhihu'],
  ['csdn.net', 'csdn'],
  ['baidu.com', 'tieba'],
  ['wenku.baidu.com', 'wenku'],
  ['tieba.baidu.com', 'tieba'],
  ['weibo.com', 'weibo'],
  ['x.com', 'x'],
  ['twitter.com', 'x'],
]);

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

function normalizeToolArgs(args) {
  if (!args) return {};
  if (typeof args === 'string') {
    try {
      return JSON.parse(args);
    } catch {
      return { query: args };
    }
  }
  if (typeof args === 'object') {
    if (args.query || args.url || args.site || args.intent) return args;
    const nestedKeys = ['arguments', 'input', 'payload'];
    for (const key of nestedKeys) {
      const value = args[key];
      if (!value) continue;
      if (typeof value === 'object') return value;
      if (typeof value === 'string') {
        try {
          return JSON.parse(value);
        } catch {
          return { query: value };
        }
      }
    }
  }
  return {};
}

// Precompiled regex patterns for performance
const PATTERNS = {
  forceSearch: /github|clawhub|插件|plugin|skill|搜索|调研|专利|竞品|知乎|抖音|小红书|百度|google|reddit|rebbit|官网|文档/,
  isUrlLookup: /(文档地址|文档链接|官网地址|官网链接|地址给我|链接给我|docs?\b|wiki\b|documentation)/,
  isProductCompareEdition: /(免费版|社区版|收费版|专业版|企业版|开源版|付费版|商业版|版本区别|版本对比|价格|定价|pricing|edition|compare)/,
  isProductCompareProduct: /(系统|平台|业务系统|中转站|new[- ]?api|魔方|zjmf|zjmf-cbap|token中转|api中转|中转平台)/,
  isProductCompareAlt: /(替代|竞品|更适合|还有什么系统|还有哪些系统|alternative|alternatives)/,
  isPluginDiscovery: /github|clawhub|plugin|plugins|skill|skills|安装/,
  isSocialResearch: /小红书|抖音|知乎|b站|bilibili|微博/,
  isWebSearch: /百度|google|谷歌|bing|搜索引擎/,
  isResearch: /专利|竞品|调研|资料|文档|官网/,
  questionSignals: /^(ok|okay|收到|明白|继续|继续做|go on|status|yes|no)[.!]?$/i,
};

const EXEC_OPTIONS = { timeout: 120000, maxBuffer: 10 * 1024 * 1024 };

function execScript(scriptPath, args) {
  return new Promise((resolve, reject) => {
    execFile('python3', [scriptPath, ...args], EXEC_OPTIONS, (error, stdout, stderr) => {
      if (error) {
        // Include script name in error for debugging
        const scriptName = path.basename(scriptPath);
        reject(new Error(`[${scriptName}] ${stderr || stdout || error.message}`));
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

function execJson(args) {
  return execScript(SCRIPT, args);
}

function execAuthJson(args) {
  return execScript(AUTH_SCRIPT, args);
}

// Known second-level domains that should not be stripped
const SECOND_LEVEL_DOMAINS = new Set([
  'co.uk', 'co.jp', 'co.kr', 'co.nz', 'co.za', 'co.in',
  'com.cn', 'com.tw', 'com.hk', 'com.sg',
  'net.cn', 'org.cn', 'gov.cn', 'edu.cn',
]);

function rootDomain(host) {
  const value = String(host || '').toLowerCase().trim();
  if (!value) return '';
  const parts = value.split('.').filter(Boolean);
  if (parts.length <= 2) return value;

  // Check for known second-level domains
  const lastTwo = parts.slice(-2).join('.');
  if (SECOND_LEVEL_DOMAINS.has(lastTwo)) {
    return parts.slice(-3).join('.');
  }
  return lastTwo;
}

function authSiteFromUrl(url) {
  try {
    const parsed = new URL(String(url || ''));
    const host = parsed.hostname.toLowerCase();
    if (host === 'wenku.baidu.com') return 'wenku';
    if (host === 'tieba.baidu.com') return 'tieba';
    const root = rootDomain(host);
    return DOMAIN_TO_AUTH_SITE.get(host) || DOMAIN_TO_AUTH_SITE.get(root) || '';
  } catch {
    return '';
  }
}

function authSitesFromQuery(query) {
  const text = String(query || '').toLowerCase();
  const sites = new Set();
  if (/小红书|xhs|rednote/.test(text)) sites.add('xiaohongshu');
  if (/抖音|douyin/.test(text)) sites.add('douyin');
  if (/知乎|zhihu/.test(text)) sites.add('zhihu');
  if (/csdn/.test(text)) sites.add('csdn');
  if (/贴吧|tieba/.test(text)) sites.add('tieba');
  if (/文库|wenku/.test(text)) sites.add('wenku');
  if (/微博|weibo/.test(text)) sites.add('weibo');
  if (/\bx\b|twitter/.test(text)) sites.add('x');
  return [...sites];
}

function authSitesFromResearch(result = {}, intent = '') {
  const normalizedIntent = String(intent || result.intent || '').trim().toLowerCase();
  // auth-sites collection is only relevant for explicit social_research intent.
  // For other intents, result URLs from various domains may pollute the set and
  // cause cross-platform follow-up queries (e.g. a zhihu query leaking into xiaohongshu).
  if (normalizedIntent !== 'social_research') return [];
  const sites = new Set();
  for (const item of result.results || []) {
    const extraction = item?.extraction || {};
    const site = authSiteFromUrl(extraction.url || item?.url || '');
    if (site) sites.add(site);
  }
  for (const site of authSitesFromQuery(result.query || '')) sites.add(site);
  return [...sites].slice(0, 6);
}

function needsAuthReminder(result = {}) {
  const rules = new Set(result.applied_rules || []);
  if (rules.has('access_wall') || rules.has('browser_auth_audit')) return true;
  for (const rule of rules) {
    if (/login_required|cookie_file_missing|probe_failed|persistent_profile_login|cookie_file_login|bootstrap_blocked|service_unavailable/i.test(String(rule))) {
      return true;
    }
  }
  return Boolean(authSiteFromUrl(result.url || ''));
}

function shouldAttachAuthForResearch(result = {}, intent = '') {
  const normalizedIntent = String(intent || result.intent || '').trim().toLowerCase();
  // For non-social_research intents, auth attachment is driven purely by applied_rules.
  // Avoid unconditionally triggering browser-auth for every zhihu/douyin query.
  if (normalizedIntent !== 'social_research') {
    const rules = new Set(result.applied_rules || []);
    for (const rule of rules) {
      if (/login_required|cookie_file_missing|probe_failed|persistent_profile_login|cookie_file_login|bootstrap_blocked|service_unavailable|access_wall/i.test(String(rule))) {
        return true;
      }
    }
    return false;
  }
  return true;
}

async function attachAuthStatus(sites = [], previewFile = DEFAULT_AUTH_PREVIEW) {
  const normalized = [...new Set((sites || []).filter((site) => AUTH_SITES.has(site)))];
  if (!normalized.length) return null;
  const result = await execAuthJson(['status', JSON.stringify({ sites: normalized })]);
  writeJson(previewFile, result);
  return result;
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

function stripPromptWrappers(prompt) {
  let text = String(prompt || '');
  text = text.replace(/Sender \(untrusted metadata\):\s*```json[\s\S]*?```\s*/g, '');
  text = text.replace(/Conversation info \(untrusted metadata\):\s*```json[\s\S]*?```\s*/g, '');
  text = text.replace(/^\[[^\]]+\]\s*/gm, '');
  return text.trim();
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
  return PATTERNS.forceSearch.test(text);
}

function isUrlLookupPrompt(prompt) {
  const text = String(prompt || '').toLowerCase();
  return PATTERNS.isUrlLookup.test(text);
}

function isProductComparePrompt(prompt) {
  const text = String(prompt || '').toLowerCase();
  if (!text) return false;
  const editionSignals = PATTERNS.isProductCompareEdition.test(text);
  const productSignals = PATTERNS.isProductCompareProduct.test(text);
  const alternativesSignal = PATTERNS.isProductCompareAlt.test(text);
  return (editionSignals && productSignals) || alternativesSignal;
}

function inferIntent(prompt) {
  const text = String(prompt || '').toLowerCase();
  if (isUrlLookupPrompt(text)) return 'find_url';
  if (isProductComparePrompt(text)) return 'product_compare';
  if (PATTERNS.isPluginDiscovery.test(text)) return 'plugin_discovery';
  if (PATTERNS.isSocialResearch.test(text)) return 'social_research';
  if (PATTERNS.isWebSearch.test(text)) return 'web_search';
  if (PATTERNS.isResearch.test(text)) return 'research';
  return 'auto';
}

function extractQueryTerms(query) {
  const text = String(query || '').toLowerCase();
  const tokens = new Set();
  for (const match of text.matchAll(/[a-z0-9][a-z0-9._-]*/g)) {
    const token = String(match[0] || '').trim();
    if (token.length >= 2) tokens.add(token);
  }
  for (const match of text.matchAll(/[\u4e00-\u9fff]{2,}/g)) {
    const token = String(match[0] || '').trim();
    if (token.length >= 2) tokens.add(token);
  }
  return [...tokens];
}

function hasQueryOverlap(query, ...fields) {
  const terms = extractQueryTerms(query);
  if (!terms.length) return true;
  const haystack = fields.filter(Boolean).join(' ').toLowerCase();
  const asciiTerms = terms.filter((term) => /^[a-z0-9._-]+$/.test(term));
  const cjkTerms = terms.filter((term) => !/^[a-z0-9._-]+$/.test(term));
  const normalizedQuery = String(query || '').toLowerCase().replace(/[-_/]+/g, ' ').replace(/\s+/g, ' ').trim();
  if (normalizedQuery && normalizedQuery.length >= 5 && haystack.includes(normalizedQuery)) return true;
  let asciiHits = 0;
  for (const term of asciiTerms) {
    if (haystack.includes(term)) asciiHits += 1;
  }
  if (asciiTerms.length >= 2 && asciiHits >= 2) return true;
  if (!asciiTerms.length && cjkTerms.some((term) => haystack.includes(term))) return true;
  return false;
}

function collectDirectAnswerCandidates(result = {}, query = '') {
  const items = Array.isArray(result?.results) ? result.results : [];
  const seen = new Set();
  const candidates = [];
  for (const item of items) {
    const extraction = item?.extraction || item?.extract || {};
    const url = String(extraction?.finalUrl || extraction?.url || item?.url || '').trim();
    if (!url || seen.has(url)) continue;
    const status = Number(extraction?.status || item?.status || 0);
    const title = String(extraction?.title || item?.title || '').trim();
    const contentType = String(extraction?.contentType || item?.contentType || '').trim();
    const score = Number(item?.score || extraction?.score || 0);
    const looksLikeDoc = /docs?|wiki|documentation|manual|guide/i.test(url) || /docs?|wiki|文档|手册/i.test(title);
    const queryAligned = hasQueryOverlap(query, url, title, item?.snippet || '', extraction?.summary?.join?.(' ') || '');
    if (!looksLikeDoc && status && status !== 200) continue;
    if (!looksLikeDoc && !queryAligned) continue;
    candidates.push({ url, status, title, contentType, score, looksLikeDoc });
    seen.add(url);
  }
  candidates.sort((a, b) => {
    const docDelta = Number(b.looksLikeDoc) - Number(a.looksLikeDoc);
    if (docDelta !== 0) return docDelta;
    const statusDelta = Number(b.status === 200) - Number(a.status === 200);
    if (statusDelta !== 0) return statusDelta;
    return (b.score || 0) - (a.score || 0);
  });
  return candidates.slice(0, 3);
}

function buildDirectAnswerSummary(query, result = {}) {
  const candidates = collectDirectAnswerCandidates(result, query);
  if (!candidates.length) return '';
  const queryText = String(query || '');
  const lines = [
    `Direct answer candidates for "${queryText}":`,
    ...candidates.map((candidate, index) => {
      const suffix = candidate.status ? ` (status ${candidate.status})` : '';
      return `${index + 1}. ${candidate.url}${suffix}`;
    }),
    'If the user only asked for a documentation/homepage URL, answer with the best candidate immediately and stop.'
  ];
  return lines.join('\n');
}

function buildFindUrlCompactResult(query, result = {}) {
  const candidates = collectDirectAnswerCandidates(result, query);
  const compact = {
    query: String(query || ''),
    intent: 'find_url',
    candidates: candidates.map((candidate) => ({
      url: candidate.url,
      status: candidate.status || 0,
      title: candidate.title || '',
      contentType: candidate.contentType || '',
      looksLikeDoc: Boolean(candidate.looksLikeDoc),
      score: candidate.score || 0,
    })),
    resultCount: Array.isArray(result?.results) ? result.results.length : 0,
    applied_rules: Array.isArray(result?.applied_rules) ? result.applied_rules : [],
    notes: [
      'If the user asked only for a documentation/homepage URL, answer with the best candidate immediately.',
      'Do not continue GitHub or local-file exploration once a reachable docs/wiki/homepage URL is available.',
    ],
  };
  if (result?.auth) compact.auth = result.auth;
  return compact;
}

function buildGuidance(pluginConfig, prompt) {
  const cleanedPrompt = stripPromptWrappers(prompt);
  const intent = pluginConfig.defaultIntent && pluginConfig.defaultIntent !== 'auto'
    ? pluginConfig.defaultIntent
    : inferIntent(cleanedPrompt);
  const lines = [
    'Search orchestration guidance:',
    '- 这一轮需要先调用 websearch_pro_research 建立证据集，再回答。',
    `- 研究查询：${cleanedPrompt}`,
    '- 先用搜索引擎做一级发现，再对高价值命中域名做二级深度提取与站点适配。',
    '- 搜索结果只负责提供路径，不直接等同于高质量证据；要优先保留官方站点、文档、定价页、版本页、GitHub 仓库的链接和证据。',
    '- 对搜索引擎已命中的高价值域名，优先使用对应站点适配/reader/distill；低质量社区页面、内容农场和问答站默认只作补充，不作为第一结论来源。',
    `- 建议意图：${intent}`,
    '- 对 DOM 获取差或 JS 很重的页面，优先使用 reader/distill 提取，不要因为首层抓取差就放弃。',
    '- 在 websearch_pro_research 返回之前，不要直接凭记忆作答。',
  ];
  if (intent === 'find_url') {
    lines.push('- 这是 find_url 任务：一旦拿到可访问的 docs/wiki/homepage URL，立即返回，不再继续追 GitHub 溯源或额外站点。');
  }
  if (intent === 'product_compare') {
    lines.push('- 这是 product_compare 任务：第一轮先查官方站点、文档、定价页、版本说明和 GitHub；不要先把知乎、CSDN、百度知道当主证据。');
    lines.push('- 只有在官方信息不足时，才把知乎、CSDN、论坛作为补充证据，并明确标注为二手来源。');
    lines.push('- 输出时先回答版本/价格/免费版事实，再补充更适合当前业务的替代系统。');
  }
  return lines.join('\n');
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
    api.logger.info?.('[openclaw-websearch-pro] plugin registered');

    api.registerTool({
      name: 'websearch_pro_status',
      label: 'WebSearch Pro Status',
      description: 'Inspect the latest search orchestration preview.',
      parameters: { type: 'object', properties: {}, required: [] },
      execute: async (_toolCallId, _args = {}) => {
        const cfg = api.pluginConfig || {};
        const details = readJson(cfg.previewFile || DEFAULT_PREVIEW, null);
        const auth = readJson(cfg.authPreviewFile || DEFAULT_AUTH_PREVIEW, null);
        return {
          content: [{ type: 'text', text: details ? `websearch pro ready: ${details.intent || 'auto'}` : 'websearch pro ready: no preview yet' }],
          details: { success: true, details, auth },
        };
      },
    });

    api.registerTool({
      name: 'websearch_pro_auth_status',
      label: 'WebSearch Pro Auth Status',
      description: 'Inspect login state, session expiry, and cookie/profile artifacts for supported sites.',
      parameters: {
        type: 'object',
        properties: {
          sites: { type: 'array', items: { type: 'string' } },
        },
        required: [],
      },
      execute: async (_toolCallId, args = {}) => {
        const normalizedArgs = normalizeToolArgs(args);
        const sites = Array.isArray(normalizedArgs.sites) && normalizedArgs.sites.length ? normalizedArgs.sites : ['xiaohongshu', 'douyin', 'zhihu', 'csdn', 'tieba', 'wenku'];
        const result = await attachAuthStatus(sites, (api.pluginConfig || {}).authPreviewFile || DEFAULT_AUTH_PREVIEW);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
          details: { success: true, result },
        };
      },
    });

    api.registerTool({
      name: 'websearch_pro_login_assist',
      label: 'WebSearch Pro Login Assist',
      description: 'Open a login page or generate a QR code image for supported sites.',
      parameters: {
        type: 'object',
        properties: {
          site: { type: 'string' },
        },
        required: ['site'],
      },
      execute: async (_toolCallId, args = {}) => {
        const normalizedArgs = normalizeToolArgs(args);
        const result = await execAuthJson(['login', JSON.stringify({ site: String(normalizedArgs.site || '') })]);
        writeJson((api.pluginConfig || {}).authPreviewFile || DEFAULT_AUTH_PREVIEW, result);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
          details: { success: true, result },
        };
      },
    });

    api.registerTool({
      name: 'websearch_pro_extract',
      label: 'WebSearch Pro Extract',
      description: 'Deep extract a specific page, including fallback for JS-heavy pages.',
      parameters: {
        type: 'object',
        properties: {
          url: { type: 'string' },
          query: { type: 'string' }
        },
        required: ['url']
      },
      execute: async (_toolCallId, args = {}) => {
        const normalizedArgs = normalizeToolArgs(args);
        const result = await execJson(['extract', JSON.stringify({ url: String(normalizedArgs.url || ''), query: String(normalizedArgs.query || normalizedArgs.q || '') })]);
        if (needsAuthReminder(result)) {
          const site = authSiteFromUrl(result.url || normalizedArgs.url || '');
          if (site) {
            result.auth = await attachAuthStatus([site], (api.pluginConfig || {}).authPreviewFile || DEFAULT_AUTH_PREVIEW);
          }
        }
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
          details: { success: true, result },
        };
      },
    });

    api.registerTool({
      name: 'websearch_pro_research',
      label: 'WebSearch Pro Research',
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
      execute: async (_toolCallId, args = {}) => {
        const normalizedArgs = normalizeToolArgs(args);
        const query = String(normalizedArgs.query || normalizedArgs.q || normalizedArgs.question || normalizedArgs.text || '').trim();
        if (!query) {
          return {
            content: [{ type: 'text', text: JSON.stringify({ error: 'empty_query' }, null, 2) }],
            details: { success: false, error: 'empty_query' },
          };
        }
        const cfg = api.pluginConfig || {};
        const payload = {
          query,
          intent: String(normalizedArgs.intent || cfg.defaultIntent || 'auto'),
          max_results: Number(normalizedArgs.max_results || normalizedArgs.maxResults || cfg.maxInitialResults || 8),
          max_deep_results: Number(normalizedArgs.max_deep_results || normalizedArgs.maxDeepResults || cfg.maxDeepResults || 5),
          max_refine_rounds: Number(normalizedArgs.max_refine_rounds || normalizedArgs.maxRefineRounds || cfg.maxRefineRounds || 2),
          site_profiles: cfg.siteProfiles || DEFAULT_POLICY.siteProfiles,
        };
        const result = await execJson(['research', JSON.stringify(payload)]);
        writeJson(cfg.previewFile || DEFAULT_PREVIEW, result);
        const authSites = authSitesFromResearch(result, payload.intent);
        if (authSites.length && shouldAttachAuthForResearch(result, payload.intent)) {
          result.auth = await attachAuthStatus(authSites, cfg.authPreviewFile || DEFAULT_AUTH_PREVIEW);
        }
        const summary = buildDirectAnswerSummary(query, result);
        const isFindUrl = payload.intent === 'find_url';
        const text = isFindUrl && summary
          ? `${summary}\n\n${JSON.stringify(buildFindUrlCompactResult(query, result), null, 2)}`
          : summary
            ? `${summary}\n\n${JSON.stringify(result, null, 2)}`
            : JSON.stringify(result, null, 2);
        return {
          content: [{ type: 'text', text }],
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
      const cleanedPrompt = stripPromptWrappers(prompt);
      if (isSystemPrompt(prompt)) return;
      if (!shouldForceSearch(cleanedPrompt, DEFAULT_POLICY)) return;
      const preview = {
        generatedAt: new Date().toISOString(),
        agentId,
        intent: inferIntent(cleanedPrompt),
        proactiveSearch: true,
        promptPreview: cleanedPrompt.slice(0, 500)
      };
      writeJson(pluginConfig.previewFile || DEFAULT_PREVIEW, preview);
      return {
        prependContext: buildGuidance(pluginConfig, cleanedPrompt)
      };
    });
  }
};

plugin.__private = {
  shouldForceSearch,
  inferIntent,
  isInjectionEnabled,
  shouldSkipAgent,
  authSiteFromUrl,
  authSitesFromQuery,
  authSitesFromResearch,
  normalizeToolArgs,
  stripPromptWrappers,
  isUrlLookupPrompt,
  isProductComparePrompt,
  shouldAttachAuthForResearch,
  collectDirectAnswerCandidates,
  buildDirectAnswerSummary,
  buildFindUrlCompactResult,
};

module.exports = plugin;
