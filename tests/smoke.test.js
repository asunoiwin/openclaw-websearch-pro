const assert = require('node:assert/strict');
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

console.log('websearch pro smoke test passed');
