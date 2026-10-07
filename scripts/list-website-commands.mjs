#!/usr/bin/env node
// Inspect public TypeScript literals without executing website code.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const root = path.resolve(process.argv[2]);
const ts = createRequire(path.join(root, 'package.json'))('typescript');
const commands = new Map();
function scan(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) { scan(file); continue; }
    if (!/\.(?:tsx?|jsx?)$/.test(entry.name)) continue;
    const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
    function visit(node) {
      if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && /^agenteng\s+(?:--[\w-]+|[a-z][\w-]*)(?:\s|$)/.test(node.text)) {
        const command = node.text.trim();
        const locations = commands.get(command) ?? [];
        locations.push(path.relative(root, file));
        commands.set(command, locations);
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
}
scan(path.join(root, 'src'));
process.stdout.write(JSON.stringify([...commands].map(([command, locations]) => ({ command, locations }))));
