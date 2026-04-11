const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const plugin = require('../src/index.js');

const registeredTools = [];
plugin.register({
  logger: { info() {} },
  pluginConfig: {},
  registerTool(def) { registeredTools.push(def.name); },
  on() {},
});

assert(registeredTools.includes('websearch_pro_status'));
assert(registeredTools.includes('websearch_pro_extract'));
assert(registeredTools.includes('websearch_pro_research'));
assert(registeredTools.includes('websearch_pro_auth_status'));
assert(registeredTools.includes('websearch_pro_login_assist'));
assert(!registeredTools.includes('search_orchestrator_status'));
assert(!registeredTools.includes('search_orchestrator_extract'));
assert(!registeredTools.includes('search_orchestrator_research'));

assert.equal(plugin.__private.inferIntent('请搜索 github 上的 openclaw skill 和 clawhub 插件'), 'plugin_discovery');
assert.equal(plugin.__private.inferIntent('帮我调研知乎和小红书上的相关讨论'), 'social_research');
assert.equal(plugin.__private.inferIntent('new api的文档地址给我'), 'find_url');
assert.equal(
  plugin.__private.inferIntent('查一下魔方业务系统有没有社区免费版 免费与收费版本区别以及有没有其他系统更加适配我们做token中转站的需求'),
  'product_compare'
);
assert.equal(
  plugin.__private.isProductComparePrompt('查一下魔方业务系统有没有社区免费版 免费与收费版本区别以及有没有其他系统更加适配我们做token中转站的需求'),
  true
);
assert.deepEqual(
  plugin.__private.authSitesFromResearch({
    intent: 'product_compare',
    results: [
      { url: 'https://www.zhihu.com/question/1' },
      { url: 'https://blog.csdn.net/example/article/details/1' },
    ],
  }, 'product_compare'),
  []
);
assert.equal(
  plugin.__private.shouldAttachAuthForResearch({ intent: 'product_compare', applied_rules: [] }, 'product_compare'),
  false
);
assert.equal(plugin.__private.shouldForceSearch('请帮我查找最新的 clawhub 插件和 GitHub skill'), true);
assert.equal(plugin.__private.shouldForceSearch('只回复 OK'), false);
assert.equal(plugin.__private.isInjectionEnabled({ enabled: true, injectBeforePromptBuild: true, proactiveSearch: true }), true);
assert.equal(plugin.__private.isInjectionEnabled({ injectBeforePromptBuild: false }), false);
assert.equal(plugin.__private.authSiteFromUrl('https://wenku.baidu.com/view/abc.html'), 'wenku');
assert.equal(plugin.__private.authSiteFromUrl('https://tieba.baidu.com/p/123'), 'tieba');
assert.equal(plugin.__private.authSiteFromUrl('https://www.zhihu.com/question/1'), 'zhihu');
assert.deepEqual(plugin.__private.authSitesFromQuery('请检查知乎和小红书登录状态').sort(), ['xiaohongshu', 'zhihu']);
assert.deepEqual(
  plugin.__private.normalizeToolArgs({ arguments: { query: 'Claude source code leak git repository 2026', max_results: 8 } }),
  { query: 'Claude source code leak git repository 2026', max_results: 8 }
);
assert.deepEqual(
  plugin.__private.normalizeToolArgs({ payload: '{"query":"Claude source code leak git repository 2026","max_results":8}' }),
  { query: 'Claude source code leak git repository 2026', max_results: 8 }
);
assert.deepEqual(
  plugin.__private.normalizeToolArgs('{"query":"Claude source code leak git repository 2026"}'),
  { query: 'Claude source code leak git repository 2026' }
);
assert.equal(plugin.__private.isUrlLookupPrompt('new api的文档地址给我'), true);
const candidates = plugin.__private.collectDirectAnswerCandidates({
  results: [
    { url: 'https://example.com/', score: 0.5, extraction: { finalUrl: 'https://example.com/', status: 200, title: 'Home' } },
    { url: 'https://example.com/docs', score: 0.4, extraction: { finalUrl: 'https://example.com/docs', status: 200, title: 'Docs' } },
  ],
}, 'new api的文档地址给我');
assert.equal(candidates[0].url, 'https://example.com/docs');
assert.equal(plugin.__private.collectDirectAnswerCandidates({
  results: [
    {
      url: 'https://zhidao.baidu.com/question/123.html',
      score: 99,
      extraction: { finalUrl: 'https://zhidao.baidu.com/question/123.html', status: 200, title: '如何一次性修改字体_百度知道' },
    },
  ],
}, 'new api的文档地址给我').length, 0);
assert.match(plugin.__private.buildDirectAnswerSummary('new api的文档地址给我', {
  results: [
    { url: 'https://example.com/docs', score: 0.8, extraction: { finalUrl: 'https://example.com/docs', status: 200, title: 'Docs' } },
  ],
}), /Direct answer candidates/);
assert.match(JSON.stringify(plugin.__private.buildFindUrlCompactResult('new api的文档地址给我', {
  results: [
    { url: 'https://example.com/docs', score: 0.8, extraction: { finalUrl: 'https://example.com/docs', status: 200, title: 'Docs' } },
  ],
})), /"intent":"find_url"/);

const pluginDir = path.join(__dirname, '..');
const previewFile = path.join(pluginDir, 'tests', '.preview.json');
const authPreviewFile = path.join(pluginDir, 'tests', '.auth-preview.json');
try { fs.unlinkSync(previewFile); } catch {}
try { fs.unlinkSync(authPreviewFile); } catch {}
const api2 = {
  logger: { info() {} },
  pluginConfig: { previewFile, authPreviewFile },
  registerTool(def) { registeredTools.push(def.name); api2.__tools.set(def.name, def); },
  on() {},
  __tools: new Map(),
};
plugin.register(api2);
const researchTool = api2.__tools.get('websearch_pro_research');
const originalSpawnSync = require('node:child_process').spawnSync;
const childProcess = require('node:child_process');
childProcess.spawnSync = (...args) => originalSpawnSync(...args);
const originalExecFile = childProcess.execFile;
childProcess.execFile = (bin, argv, opts, cb) => {
  if (String(argv[0]).includes('search_orchestrator.py')) {
    cb(null, JSON.stringify({ query: JSON.parse(argv[2]).query, results: [] }), '');
    return;
  }
  if (String(argv[0]).includes('auth_workflow.py')) {
    cb(null, JSON.stringify({ ok: true, sites: [] }), '');
    return;
  }
  return originalExecFile(bin, argv, opts, cb);
};
(async () => {
  const execResult = await researchTool.execute('call_function_demo_1', { query: 'new api的文档地址给我' });
  childProcess.execFile = originalExecFile;
  assert.match(execResult.content[0].text, /"query": "new api的文档地址给我"/);
  console.log('websearch pro smoke test passed');
})().catch((error) => {
  childProcess.execFile = originalExecFile;
  console.error(error);
  process.exit(1);
});
