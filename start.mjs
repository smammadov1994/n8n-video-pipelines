// Same as start.sh, for launchers that can only run node (Claude's preview pane).
import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
mkdirSync(join(here, 'output'), { recursive: true });
const node = join(here, 'node24/node_modules/.bin/node');
const env = {
  ...process.env,
  PATH: `${join(here, 'node24/node_modules/.bin')}:${process.env.HOME}/.local/bin:${process.env.PATH}`,
  N8N_USER_FOLDER: here,
  N8N_PORT: '5678',
  N8N_HOST: 'localhost',
  NODES_EXCLUDE: '[]',
  N8N_RESTRICT_FILE_ACCESS_TO: join(here, 'output'),
  N8N_DIAGNOSTICS_ENABLED: 'false',
  N8N_VERSION_NOTIFICATIONS_ENABLED: 'false',
  N8N_PERSONALIZATION_ENABLED: 'false',
};
const child = spawn(node, [join(here, 'node_modules/n8n/bin/n8n'), ...process.argv.slice(2)], { cwd: here, env, stdio: 'inherit' });
child.on('exit', code => process.exit(code ?? 0));
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => child.kill(sig));
