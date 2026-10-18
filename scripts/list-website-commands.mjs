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
    const add = (command) => {
      const locations = commands.get(command) ?? [];
      locations.push(path.relative(root, file));
      commands.set(command, locations);
    };
    const isCommand = (text) => /^agenteng\s+(?:--[\w-]+|[a-z][\w-]*)(?:\s|$)/.test(text);
    // Prose such as a meta description ("agenteng is the ...") ends like a sentence or has a
    // sentence break ("... | sh. More at ..."); commands never do.
    const isProse = (text) => /[.!?]\s*$/.test(text.trim()) || /[.!?]\s+[A-Z]/.test(text);
    function visit(node) {
      // Accessible labels ("agenteng terminal demo") describe UI, they are not commands.
      const label = node.parent && ts.isJsxAttribute(node.parent) && /^(?:aria-label|alt|title)$/.test(node.parent.name.getText());
      if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && !label) {
        if (node.text.includes('\n')) {
          // Multi-line code blocks: each line is its own command. An environment prefix
          // (AGENTENG_OUTPUT=json) is dropped and a pipe into another tool (| jq) is cut.
          for (const raw of node.text.split('\n')) {
            const line = raw.replace(/^(?:[A-Z_]+=\S+\s+)+/, '').split(/\s\|\s/)[0].trim();
            if (isCommand(line) && !isProse(line)) add(line);
          }
        } else if (isCommand(node.text) && !isProse(node.text)) {
          add(node.text.trim());
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
}
scan(path.join(root, 'src'));
process.stdout.write(JSON.stringify([...commands].map(([command, locations]) => ({ command, locations }))));
