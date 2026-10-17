// node --test _src/tests/js
const test = require('node:test');
const assert = require('node:assert/strict');
const T = require('../../../assets/timer-core.js');

const at = (y, mo, d, h, mi, s = 0) => new Date(y, mo - 1, d, h, mi, s).getTime();

test('hmsToMs clamps and sums', () => {
  assert.equal(T.hmsToMs(0, 25, 0), 25 * 60000);
  assert.equal(T.hmsToMs(1, 2, 3), 3723000);
  assert.equal(T.hmsToMs('', 'x', -5), 0);
  assert.equal(T.hmsToMs(99, 99, 99), T.MAX_MS);
});

test('formatClock rounds remaining time up and switches to h:mm:ss', () => {
  assert.equal(T.formatClock(200), '00:01');
  assert.equal(T.formatClock(0), '00:00');
  assert.equal(T.formatClock(59000), '00:59');
  assert.equal(T.formatClock(3600000), '1:00:00');
  assert.equal(T.formatClock(3661000), '1:01:01');
  assert.equal(T.formatStopwatch(61234), '01:01.23');
});

test('countdown is computed from the end timestamp, not by decrementing', () => {
  const run = {status: 'running', totalMs: 600000, endTs: 1000000 + 600000};
  assert.equal(T.countdownView(run, 1000000).remainingMs, 600000);
  // 탭이 백그라운드여서 한참 뒤에 처음 계산해도 정확하다
  assert.equal(T.countdownView(run, 1000000 + 437000).remainingMs, 163000);
  assert.equal(T.countdownView(run, 1000000 + 600000).status, 'done');
  assert.equal(T.countdownView({status: 'paused', totalMs: 1000, remainingMs: 400}, 5).remainingMs, 400);
});

test('countdown events: pre-alert only when shorter than total', () => {
  const end = 10 * 60000;
  const evs = T.countdownEvents(end, 10 * 60000, 3, 0, end);
  assert.deepEqual(evs.map(e => [e.kind, e.ts]), [['pre', end - 3 * 60000], ['end', end]]);
  assert.equal(T.countdownEvents(end, 5 * 60000, 5, 0, end).length, 1);       // 5분 중 5분 전 = 의미 없음
  assert.equal(T.countdownEvents(end, 10 * 60000, 3, end - 60000, end).length, 1);   // from 이후만
});

test('stopwatch elapsed accumulates across pauses', () => {
  assert.equal(T.stopwatchElapsed({status: 'running', startTs: 1000, elapsedMs: 5000}, 3000), 7000);
  assert.equal(T.stopwatchElapsed({status: 'paused', startTs: 0, elapsedMs: 5000}, 99999), 5000);
  assert.deepEqual(T.lapRows([1000, 2500, 6000]).map(r => r.split), [1000, 1500, 3500]);
});

test('parseHM', () => {
  assert.equal(T.parseHM('09:30'), 570);
  assert.equal(T.parseHM('9:05'), 545);
  assert.equal(T.parseHM('24:00'), null);
  assert.equal(T.parseHM(''), null);
  assert.equal(T.parseHM('12:60'), null);
});

test('range: same-day, in progress / upcoming / ended', () => {
  const noon = at(2026, 10, 17, 12, 0);
  const inProgress = T.computeRange('11:00', '13:00', noon);
  assert.equal(inProgress.startTs, at(2026, 10, 17, 11, 0));
  assert.equal(inProgress.endTs, at(2026, 10, 17, 13, 0));
  assert.equal(T.rangeStatus(inProgress.startTs, inProgress.endTs, noon).phase, 'running');
  const up = T.computeRange('14:00', '16:00', noon);
  const st = T.rangeStatus(up.startTs, up.endTs, noon);
  assert.equal(st.phase, 'waiting');
  assert.equal(st.untilStartMs, 2 * 3600000);
  const ended = T.computeRange('08:00', '09:00', noon);
  assert.equal(T.rangeStatus(ended.startTs, ended.endTs, noon).phase, 'ended');
});

test('range: crossing midnight', () => {
  // 23:00 - 01:00
  const before = at(2026, 10, 17, 22, 0);
  let r = T.computeRange('23:00', '01:00', before);
  assert.equal(r.startTs, at(2026, 10, 17, 23, 0));
  assert.equal(r.endTs, at(2026, 10, 18, 1, 0));
  assert.equal(r.endTs - r.startTs, 2 * 3600000);
  assert.equal(T.rangeStatus(r.startTs, r.endTs, before).phase, 'waiting');
  // 자정이 지난 00:30 에는 어제 23:00 에 시작한 구간이 진행 중
  const after = at(2026, 10, 18, 0, 30);
  r = T.computeRange('23:00', '01:00', after);
  assert.equal(r.startTs, at(2026, 10, 17, 23, 0));
  const s = T.rangeStatus(r.startTs, r.endTs, after);
  assert.equal(s.phase, 'running');
  assert.equal(s.elapsedMs, 90 * 60000);
  assert.equal(s.remainingMs, 30 * 60000);
  assert.ok(Math.abs(s.progress - 0.75) < 1e-9);
  // 23:30 시작 직전 구간 (23:59 → 00:01)
  r = T.computeRange('23:59', '00:01', at(2026, 10, 18, 0, 0));
  assert.equal(r.endTs - r.startTs, 2 * 60000);
});

test('range: invalid and equal times', () => {
  assert.equal(T.computeRange('', '10:00', 0).error, 'invalid');
  assert.equal(T.computeRange('10:00', '10:00', 0).error, 'same');
});

test('range events are restored from timestamps only', () => {
  const s = at(2026, 10, 17, 14, 0), e = at(2026, 10, 17, 16, 0);
  const evs = T.rangeEvents(s, e, 10, s - 1, e);
  assert.deepEqual(evs.map(x => x.kind), ['start', 'pre', 'end']);
  assert.equal(evs[1].ts, e - 10 * 60000);
  // 복원 시점이 이미 종료 뒤면 앞으로 올 알림이 없다
  assert.equal(T.rangeEvents(s, e, 10, e, e + 1e6).length, 0);
});

test('interval state: mixing 45/5 x 3', () => {
  const plan = T.normalizePlan({workMs: 45 * 60000, restMs: 5 * 60000, cycles: 3});
  let st = T.intervalState(plan, 0);
  assert.deepEqual([st.phase, st.cycle], ['work', 1]);
  st = T.intervalState(plan, 44 * 60000);
  assert.equal(st.phaseRemainingMs, 60000);
  st = T.intervalState(plan, 45 * 60000);
  assert.deepEqual([st.phase, st.cycle, st.phaseRemainingMs], ['rest', 1, 5 * 60000]);
  st = T.intervalState(plan, 50 * 60000);
  assert.deepEqual([st.phase, st.cycle], ['work', 2]);
  const total = 3 * 45 * 60000 + 2 * 5 * 60000;
  assert.equal(T.planTotalMs(plan), total);
  assert.equal(T.intervalState(plan, total - 1).phase, 'work');
  assert.equal(T.intervalState(plan, total).phase, 'done');
});

test('interval state: unlimited cycles and no rest', () => {
  const inf = T.normalizePlan({workMs: 25 * 60000, restMs: 5 * 60000, cycles: 0});
  const st = T.intervalState(inf, 30 * 60000 * 100 + 26 * 60000);
  assert.deepEqual([st.phase, st.cycle], ['rest', 101]);
  const noRest = T.normalizePlan({workMs: 60000, restMs: 0, cycles: 2});
  assert.equal(T.intervalState(noRest, 61000).cycle, 2);
  assert.equal(T.intervalState(noRest, 120000).phase, 'done');
});

test('interval events', () => {
  const plan = T.normalizePlan({workMs: 25 * 60000, restMs: 5 * 60000, cycles: 2});
  const evs = T.intervalEvents(plan, 0, 0, -1, 1e9);
  assert.deepEqual(evs.map(e => [e.kind, e.ts / 60000]), [['rest', 25], ['work', 30], ['done', 55]]);
  const withPre = T.intervalEvents(plan, 0, 5, -1, 1e9);
  assert.deepEqual(withPre.map(e => e.kind), ['pre', 'rest', 'work', 'pre', 'done']);
  const inf = T.normalizePlan({workMs: 60000, restMs: 60000, cycles: 0});
  assert.equal(T.intervalEvents(inf, 0, 0, 0, 10 * 60000).length, 10);       // 무제한도 구간 안만 만든다
});

test('sanitizeRun restores running countdown by end timestamp', () => {
  const now = 5000000;
  const r = T.sanitizeRun({mode: 'countdown', status: 'running', totalMs: 600000, endTs: now + 1234, preMin: 2}, now);
  assert.equal(r.status, 'running');
  assert.equal(T.countdownView(r, now).remainingMs, 1234);
  const gone = T.sanitizeRun({mode: 'countdown', status: 'running', totalMs: 600000, endTs: now - 1}, now);
  assert.equal(gone.status, 'done');
  assert.equal(T.sanitizeRun({mode: 'nope'}, now), null);
  assert.equal(T.sanitizeRun({mode: 'countdown', status: 'running', totalMs: 'x', endTs: 1}, now), null);
  assert.equal(T.sanitizeRun(null, now), null);
  const sw = T.sanitizeRun({mode: 'stopwatch', status: 'running', startTs: now - 4000, elapsedMs: 1000, laps: [500, 'x']}, now);
  assert.equal(T.stopwatchElapsed(sw, now), 5000);
  assert.deepEqual(sw.laps, [500]);
  const rg = T.sanitizeRun({mode: 'range', startTs: 1, endTs: 5}, now);
  assert.equal(rg.endTs, 5);
  const iv = T.sanitizeRun({mode: 'interval', status: 'running', startTs: now - 60000,
    plan: {workMs: 120000, restMs: 60000, cycles: 2}}, now);
  assert.equal(iv.status, 'running');
  const ivDone = T.sanitizeRun({mode: 'interval', status: 'running', startTs: now - 9e6,
    plan: {workMs: 120000, restMs: 60000, cycles: 2}}, now);
  assert.equal(ivDone.status, 'done');
});

test('wholeMinutes rounds up', () => {
  assert.equal(T.wholeMinutes(60001), 2);
  assert.equal(T.wholeMinutes(60000), 1);
  assert.equal(T.wholeMinutes(0), 0);
});
