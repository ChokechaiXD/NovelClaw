const test = require('node:test');
const assert = require('node:assert/strict');

const { classifyChapterState, decorateChapter, summarizeChapterStates } = require('../lib/chapter-state');

test('classifyChapterState lets active run status override source and quality', () => {
  const state = classifyChapterState({
    chapter: {
      hasTh: true,
      qualityRecord: { passed: false, hardFailures: ['too short'] },
    },
    sourceIssue: {
      issues: [{ code: 'empty_content', severity: 'error' }],
    },
    runResult: {
      status: 'running',
      reason: 'current chapter',
    },
  });

  assert.equal(state.workflowStatus, 'running');
  assert.equal(state.workflowBlocked, false);
  assert.deepEqual(state.workflowReasons, ['current chapter']);
});

test('classifyChapterState blocks chapters with source errors', () => {
  const state = classifyChapterState({
    chapter: { status: 'source_only', hasTh: false },
    sourceIssue: {
      issues: [
        { code: 'empty_content', severity: 'error' },
        { code: 'dirty_title', severity: 'warn' },
      ],
    },
  });

  assert.equal(state.workflowStatus, 'source_not_ready');
  assert.equal(state.workflowReady, false);
  assert.deepEqual(state.workflowReasons, ['empty_content, dirty_title']);
});

test('classifyChapterState marks failed quality records as review', () => {
  const state = classifyChapterState({
    chapter: {
      hasTh: true,
      qualityRecord: { passed: false, hardFailures: ['Completeness: too short'] },
    },
  });

  assert.equal(state.workflowStatus, 'needs_review');
  assert.deepEqual(state.workflowReasons, ['Completeness: too short']);
});

test('classifyChapterState separates translated and untranslated chapters', () => {
  assert.equal(classifyChapterState({ chapter: { hasTh: true } }).workflowStatus, 'translated');
  assert.equal(classifyChapterState({ chapter: { status: 'source_only', hasTh: false } }).workflowStatus, 'untranslated');
});

test('decorateChapter adds workflow fields without mutating the input chapter', () => {
  const chapter = { num: 7, status: 'source_only', hasTh: false };
  const decorated = decorateChapter(chapter, {
    sourceIssue: { issues: [{ code: 'site_shell', severity: 'error' }] },
  });

  assert.equal(chapter.workflowStatus, undefined);
  assert.equal(decorated.workflowStatus, 'source_not_ready');
  assert.deepEqual(decorated.workflowSourceIssues, [{ code: 'site_shell', severity: 'error' }]);
});

test('summarizeChapterStates counts decorated workflow statuses', () => {
  const summary = summarizeChapterStates([
    { workflowStatus: 'translated' },
    { workflowStatus: 'translated' },
    { workflowStatus: 'source_not_ready' },
    { status: 'source_only', hasTh: false },
  ]);

  assert.equal(summary.translated, 2);
  assert.equal(summary.source_not_ready, 1);
  assert.equal(summary.untranslated, 1);
});
