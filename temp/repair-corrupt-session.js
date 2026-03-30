#!/usr/bin/env node
/**
 * Script para reparar arquivo de sessão corrompido
 * Uso: node repair-session.js [caminho-para-docs/maestro]
 */

const fs = require('fs');
const path = require('path');

const STATE_DIR = process.argv[2] || 'docs/maestro';
const SESSION_FILE = path.join(STATE_DIR, 'state', 'active-session.md');

console.log(`Verificando: ${SESSION_FILE}`);

if (!fs.existsSync(SESSION_FILE)) {
  console.error('Erro: Arquivo de sessão não encontrado.');
  console.error(`Caminho: ${SESSION_FILE}`);
  console.error('\nUse: node repair-session.js [caminho-do-projeto]/docs/maestro');
  process.exit(1);
}

const content = fs.readFileSync(SESSION_FILE, 'utf8');

// Extrair frontmatter YAML
const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
if (!match) {
  console.error('Erro: Formato inválido. Esperado: ---\\n<YAML>\\n---\\n<corpo>');
  process.exit(1);
}

const yamlContent = match[1];
const bodyContent = match[2];

console.log('Analisando conteúdo YAML...');

// Detectar linhas problemáticas (valores com caracteres especiais não-escapados)
const lines = yamlContent.split('\n');
const problematicLines = [];

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  // Detectar valores que parecem código em campos de downstream_context
  if (line.includes(':') && !line.trim().startsWith('#')) {
    // Procurar padrões como: has_flag(args: list[str], flag: str) -> bool
    if (line.match(/:\s*\w+\([^)]*\)|:\s*[^"'\s]+\s*->/)) {
      if (!line.includes(': "') && !line.includes(": '")) {
        problematicLines.push({ index: i, content: line });
      }
    }
  }
}

if (problematicLines.length === 0) {
  console.log('✓ Nenhum problema óbvio detectado. O arquivo pode estar válido.');
  console.log('Se ainda houver erro, o problema pode estar em valores multilinha.');
  process.exit(0);
}

console.log(`\n✗ ${problematicLines.length} linha(s) problemática(s) encontrada(s):\n`);

problematicLines.forEach(({ index, content }) => {
  console.log(`  Linha ${index + 1}: ${content.substring(0, 80)}${content.length > 80 ? '...' : ''}`);
});

console.log('\nTentando reparação automática...');

// Reparar: envolver valores problemáticos em aspas duplas
const fixedLines = [...lines];
problematicLines.forEach(({ index, content }) => {
  // Extrair indentação, chave e valor
  const parts = content.match(/^(\s*)([\w_]+):\s*(.+)$/);
  if (parts) {
    const [, indent, key, value] = parts;
    // Escapar aspas duplas no valor e envolver
    const escaped = value.replace(/"/g, '\\"');
    fixedLines[index] = `${indent}${key}: "${escaped}"`;
  }
});

const fixedYaml = fixedLines.join('\n');
const newContent = `---\n${fixedYaml}\n---\n${bodyContent}`;

// Criar backup e escrever arquivo corrigido
const backupPath = SESSION_FILE + '.bak';
fs.writeFileSync(backupPath, content, 'utf8');
fs.writeFileSync(SESSION_FILE, newContent, 'utf8');

console.log('✓ Reparação aplicada!');
console.log(`\nArquivo corrigido: ${SESSION_FILE}`);
console.log(`Backup criado: ${backupPath}`);
console.log('\nTente executar o comando Maestro novamente.');
console.log('Se o erro persistir, edite o arquivo manualmente ou delete a sessão.');
