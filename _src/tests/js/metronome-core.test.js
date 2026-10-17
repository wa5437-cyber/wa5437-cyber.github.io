const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../../../assets/metronome-core.js');

const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test('clampBpm limits to 20-300 and rounds', () => {
  assert.equal(M.clampBpm(5), 20);
  assert.equal(M.clampBpm(999), 300);
  assert.equal(M.clampBpm('120.6'), 121);
  assert.equal(M.clampBpm('abc', 90), 90);
  assert.equal(M.clampBpm(''), 120);
});

test('tap tempo averages the recent intervals and resets after 2 seconds', () => {
  let s = M.tapTempo({taps: []}, 0);
  assert.equal(s.bpm, null);
  s = M.tapTempo(s, 500);
  assert.equal(s.bpm, 120);
  s = M.tapTempo(s, 1000);
  s = M.tapTempo(s, 1520);                     // 평균 (1520-0)/3 = 506.67ms
  assert.equal(s.bpm, Math.round(60000 / (1520 / 3)));
  s = M.tapTempo(s, 1520 + 2001);               // 2초 초과 -> 리셋
  assert.deepEqual(s.taps, [3521]);
  assert.equal(s.bpm, null);
  s = M.tapTempo(s, 3521 + 2000);               // 정확히 2초는 이어짐
  assert.equal(s.bpm, 30);
  // 오래된 탭은 8개까지만
  let st = {taps: []};
  for (let i = 0; i < 12; i++) st = M.tapTempo(st, i * 600);
  assert.equal(st.taps.length, 8);
  assert.equal(st.bpm, 100);
  // 너무 빠르면 300 으로 클램프
  assert.equal(M.tapTempo(M.tapTempo({taps: []}, 0), 100).bpm, 300);
});

test('scheduler: 4/4 quarter notes at 120 BPM', () => {
  const sch = new M.Scheduler({startTime: 10, bpm: 120, meter: M.meterFor('4/4'), sub: 'quarter'});
  const ticks = sch.collect(10 + 4.01);        // 2마디 중 첫 마디 + 1
  assert.equal(ticks.length, 9);
  near(ticks[1].time - ticks[0].time, 0.5);
  assert.deepEqual(ticks.slice(0, 5).map(t => [t.bar, t.beat, t.accent]),
    [[0, 0, 'strong'], [0, 1, 'weak'], [0, 2, 'weak'], [0, 3, 'weak'], [1, 0, 'strong']]);
  assert.equal(ticks[8].bar, 2);
});

test('scheduler: lookahead windows never repeat or skip a tick', () => {
  const sch = new M.Scheduler({startTime: 0, bpm: 137, meter: M.meterFor('3/4'), sub: 'eighth'});
  let all = [];
  for (let t = 0.1; t < 20; t += 0.025) all = all.concat(sch.collect(t));
  const ref = new M.Scheduler({startTime: 0, bpm: 137, meter: M.meterFor('3/4'), sub: 'eighth'}).collect(20.0);
  assert.ok(all.length >= ref.length - 1);
  all.forEach((t, i) => { near(t.time, ref[i].time); assert.equal(t.beat, ref[i].beat); assert.equal(t.sub, ref[i].sub); });
  near(60 / 137 / 2, all[1].time - all[0].time);
});

test('scheduler: subdivisions and sub tick accent', () => {
  for (const [sub, n] of [['quarter', 1], ['eighth', 2], ['triplet', 3], ['sixteenth', 4]]) {
    const ticks = new M.Scheduler({startTime: 0, bpm: 60, meter: M.meterFor('2/4'), sub}).collect(2.0 - 1e-6);   // 2 beats = 2 sec (부동소수점 오차 여유)
    assert.equal(ticks.length, 2 * n, sub);
    assert.equal(ticks.filter(t => t.accent === 'sub').length, 2 * (n - 1), sub);
  }
  const tri = new M.Scheduler({startTime: 0, bpm: 60, meter: M.meterFor('4/4'), sub: 'triplet'}).collect(1.0);
  near(tri[1].time, 1 / 3);
});

test('scheduler: accents for 6/8, 7/8, custom and accent off', () => {
  const six = new M.Scheduler({startTime: 0, bpm: 120, meter: M.meterFor('6/8'), sub: 'quarter'}).collect(3.0);
  assert.deepEqual(six.map(t => t.accent), ['strong', 'weak', 'weak', 'medium', 'weak', 'weak']);
  const seven = new M.Scheduler({startTime: 0, bpm: 120, meter: M.meterFor('7/8'), sub: 'quarter'}).collect(3.5);
  assert.deepEqual(seven.map(t => t.accent), ['strong', 'weak', 'medium', 'weak', 'medium', 'weak', 'weak']);
  const custom = new M.Scheduler({startTime: 0, bpm: 120, meter: M.meterFor('custom', 9), sub: 'quarter'}).collect(5.0);
  assert.equal(custom.length, 10);
  assert.equal(custom[9].bar, 1);
  assert.equal(M.meterFor('custom', 99).beats, 16);
  const off = new M.Scheduler({startTime: 0, bpm: 120, meter: M.meterFor('4/4'), sub: 'quarter', accentOn: false}).collect(1.0);
  assert.ok(off.every(t => t.accent === 'weak'));
});

test('scheduler: tempo change applies from the next tick; meter change wraps safely', () => {
  const sch = new M.Scheduler({startTime: 0, bpm: 60, meter: M.meterFor('4/4'), sub: 'quarter'});
  sch.collect(1.5);           // ticks at 0, 1
  sch.setBpm(120);
  const next = sch.collect(3.0);
  near(next[0].time, 2);      // 이미 예약된 간격은 그대로, 그다음부터 0.5s 간격
  near(next[1].time, 2.5);
  sch.setMeter(M.meterFor('2/4'));
  const after = sch.collect(5.0);
  assert.ok(after.every(t => t.beat < 2));
});

test('speed trainer: +5 BPM every 4 bars up to the target', () => {
  const tr = M.normalizeTrainer({on: true, start: 80, target: 100, every: 4, step: 5});
  assert.equal(M.trainerBpm(tr, 0), 80);
  assert.equal(M.trainerBpm(tr, 3), 80);
  assert.equal(M.trainerBpm(tr, 4), 85);
  assert.equal(M.trainerBpm(tr, 15), 95);
  assert.equal(M.trainerBpm(tr, 16), 100);
  assert.equal(M.trainerBpm(tr, 400), 100);      // 목표를 넘지 않는다
  const down = M.normalizeTrainer({on: true, start: 120, target: 100, every: 2, step: 15});
  assert.equal(M.trainerBpm(down, 2), 105);
  assert.equal(M.trainerBpm(down, 4), 100);
});

test('scheduler with trainer changes BPM at bar lines only', () => {
  const tr = M.normalizeTrainer({on: true, start: 60, target: 120, every: 1, step: 30});
  const sch = new M.Scheduler({startTime: 0, bpm: 60, meter: M.meterFor('2/4'), sub: 'quarter', trainer: tr});
  const t = sch.collect(100);
  // 마디0: 60 BPM(1s 간격), 마디1: 90 BPM, 마디2 이후: 120 BPM
  assert.deepEqual(t.slice(0, 6).map(x => x.bpm), [60, 60, 90, 90, 120, 120]);
  near(t[1].time - t[0].time, 1);
  near(t[3].time - t[2].time, 60 / 90);
  near(t[5].time - t[4].time, 0.5);
});

test('tempo terms', () => {
  assert.equal(M.termForBpm(40), 'largo');
  assert.equal(M.termForBpm(60), 'larghetto');
  assert.equal(M.termForBpm(70), 'adagio');
  assert.equal(M.termForBpm(100), 'andante');
  assert.equal(M.termForBpm(110), 'moderato');
  assert.equal(M.termForBpm(120), 'allegro');
  assert.equal(M.termForBpm(160), 'vivace');
  assert.equal(M.termForBpm(200), 'presto');
});

test('practice timer helpers', () => {
  assert.equal(M.practiceRemaining(10000, 4000), 6000);
  assert.equal(M.practiceRemaining(10000, 20000), 0);
  assert.equal(M.tickWallMs(5.5, 5.0, 1000), 1500);
});

test('settings are sanitized', () => {
  const s = M.sanitizeSettings({bpm: 9999, sig: '9/9', sub: 'x', volume: -5, sound: 'laser', practiceMin: 9999,
    trainer: {on: true, start: 1, target: 999, every: 0, step: 'a'}, accent: false, wake: 'yes'});
  assert.deepEqual([s.bpm, s.sig, s.sub, s.volume, s.sound, s.practiceMin, s.accent, s.wake],
    [300, '4/4', 'quarter', 0, 'click', 180, false, false]);
  assert.deepEqual(s.trainer, {on: true, start: 20, target: 300, every: 1, step: 5});
  assert.equal(M.sanitizeSettings(null).bpm, M.DEFAULTS.bpm);
});
