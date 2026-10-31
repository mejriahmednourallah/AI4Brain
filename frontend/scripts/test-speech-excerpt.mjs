import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/speechExcerpt.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
const { MAX_SPEECH_SENTENCE_LENGTH, WRITTEN_REPLY_PROMPT, speechExcerpt } = await import(moduleUrl);

assert.equal(speechExcerpt('  First sentence. Second sentence stays written.  '), 'First sentence.');
assert.equal(speechExcerpt('A question? Another answer!'), 'A question?');
assert.equal(speechExcerpt('She said “Ready.” Then continued.'), 'She said “Ready.”');
assert.equal(speechExcerpt('First sentence. ' + 'x'.repeat(200) + '.'), 'First sentence.');
assert.equal(speechExcerpt('   Incomplete sentence with no ending'), WRITTEN_REPLY_PROMPT);
assert.equal(speechExcerpt('x'.repeat(MAX_SPEECH_SENTENCE_LENGTH - 1) + '.'), 'x'.repeat(MAX_SPEECH_SENTENCE_LENGTH - 1) + '.');
assert.equal(speechExcerpt('x'.repeat(MAX_SPEECH_SENTENCE_LENGTH) + '. Follow-up.'), WRITTEN_REPLY_PROMPT);
assert.equal(speechExcerpt('A very long first sentence ' + 'x'.repeat(180) + '. Short later sentence.'), WRITTEN_REPLY_PROMPT);
assert.equal(speechExcerpt('No punctuation means no safe spoken excerpt'), WRITTEN_REPLY_PROMPT);

console.log('PASS speech excerpt: first complete sentence, strict bound, normalization, and truthful written-reply fallback');
