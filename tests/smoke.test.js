const assert = require('node:assert/strict');
const plugin = require('../src/index.js');

assert.equal(plugin.__private.inferIntent('请搜索 github 上的 openclaw skill 和 clawhub 插件'), 'plugin_discovery');
assert.equal(plugin.__private.inferIntent('帮我调研知乎和小红书上的相关讨论'), 'social_research');
assert.equal(plugin.__private.shouldForceSearch('请帮我查找最新的 clawhub 插件和 GitHub skill'), true);
assert.equal(plugin.__private.shouldForceSearch('只回复 OK'), false);
assert.equal(plugin.__private.isInjectionEnabled({ enabled: true, injectBeforePromptBuild: true, proactiveSearch: true }), true);
assert.equal(plugin.__private.isInjectionEnabled({ injectBeforePromptBuild: false }), false);

console.log('search orchestrator smoke test passed');
