/* 메트로놈의 순수 계산 모듈. 브라우저(window.MetronomeCore)와 node(require) 양쪽에서 쓴다.
   소리는 만들지 않는다: 스케줄러는 "언제(오디오 시계 초) 어떤 박을 울릴지" 목록만 돌려준다. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.MetronomeCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var BPM_MIN = 20, BPM_MAX = 300;
  var TAP_RESET_MS = 2000, TAP_KEEP = 8;

  function clampBpm(v, fallback) {
    var n = Math.round(Number(v));
    if (!isFinite(n) || v === '' || v === null) n = fallback === undefined ? 120 : fallback;
    return Math.min(BPM_MAX, Math.max(BPM_MIN, n));
  }

  function clampInt(v, lo, hi, fallback) {
    var n = Math.round(Number(v));
    if (!isFinite(n) || v === '' || v === null) n = fallback === undefined ? lo : fallback;
    return Math.min(hi, Math.max(lo, n));
  }

  /* 박자. accents: 박마다 2=강, 1=중간, 0=약. x/8 박자는 8분음표 한 개가 한 박이다. */
  var SIGNATURES = {
    '2/4': {beats: 2, accents: [2, 0]},
    '3/4': {beats: 3, accents: [2, 0, 0]},
    '4/4': {beats: 4, accents: [2, 0, 0, 0]},
    '5/4': {beats: 5, accents: [2, 0, 0, 1, 0]},
    '6/8': {beats: 6, accents: [2, 0, 0, 1, 0, 0]},
    '7/8': {beats: 7, accents: [2, 0, 1, 0, 1, 0, 0]}
  };
  var SIG_IDS = ['2/4', '3/4', '4/4', '5/4', '6/8', '7/8', 'custom'];

  function meterFor(id, customBeats) {
    if (SIGNATURES[id]) return {id: id, beats: SIGNATURES[id].beats, accents: SIGNATURES[id].accents.slice()};
    var n = clampInt(customBeats, 1, 16, 4), acc = [], i;
    for (i = 0; i < n; i++) acc.push(i === 0 ? 2 : 0);
    return {id: 'custom', beats: n, accents: acc};
  }

  /* 분할: 한 박을 몇 개로 나누는가. */
  var SUBDIVISIONS = {quarter: 1, eighth: 2, triplet: 3, sixteenth: 4};
  var SUB_IDS = ['quarter', 'eighth', 'triplet', 'sixteenth'];

  function secondsPerTick(bpm, subCount) { return 60 / bpm / subCount; }

  /* 소리 세기 종류: 'strong' | 'medium' | 'weak' | 'sub' (분할음) */
  function tickAccent(meter, beat, subIdx, accentOn) {
    if (subIdx > 0) return 'sub';
    if (accentOn === false) return 'weak';
    var lv = meter.accents[beat];
    return lv === 2 ? 'strong' : lv === 1 ? 'medium' : 'weak';
  }

  /* ---- 가속 연습 ---- */
  function normalizeTrainer(t) {
    t = t || {};
    return {
      on: !!t.on,
      start: clampBpm(t.start, 80),
      target: clampBpm(t.target, 120),
      every: clampInt(t.every, 1, 64, 4),
      step: clampInt(t.step, 1, 50, 5)
    };
  }

  /* barIndex(0부터)마디의 BPM. 목표를 넘지 않는다. 목표가 시작보다 낮으면 감속. */
  function trainerBpm(tr, barIndex) {
    var steps = Math.floor(Math.max(0, barIndex) / tr.every);
    if (tr.target >= tr.start) return Math.min(tr.target, tr.start + steps * tr.step);
    return Math.max(tr.target, tr.start - steps * tr.step);
  }

  function trainerReached(tr, bpm) { return bpm === tr.target; }

  /* ---- 스케줄러 ----
     cfg: {startTime(오디오 시계 초), bpm, meter, sub('quarter'…), accentOn, trainer}
     collect(until): until(초) 이전에 울릴 박들을 돌려주고 내부 위치를 앞으로 옮긴다. */
  function Scheduler(cfg) {
    this.meter = cfg.meter;
    this.subCount = SUBDIVISIONS[cfg.sub] || 1;
    this.bpm = clampBpm(cfg.bpm);
    this.accentOn = cfg.accentOn !== false;
    this.trainer = cfg.trainer && cfg.trainer.on ? cfg.trainer : null;
    this.nextTime = cfg.startTime || 0;
    this.bar = 0;
    this.beat = 0;
    this.subIdx = 0;
  }

  Scheduler.prototype.setBpm = function (bpm) { this.bpm = clampBpm(bpm, this.bpm); };
  Scheduler.prototype.setSub = function (sub) {
    this.subCount = SUBDIVISIONS[sub] || 1;
    if (this.subIdx >= this.subCount) this.subIdx = 0;
  };
  Scheduler.prototype.setMeter = function (meter) {
    this.meter = meter;
    if (this.beat >= meter.beats) { this.beat = 0; this.subIdx = 0; }
  };

  Scheduler.prototype.collect = function (until) {
    var out = [];
    while (this.nextTime < until) {
      if (this.beat === 0 && this.subIdx === 0 && this.trainer) this.bpm = trainerBpm(this.trainer, this.bar);
      out.push({
        time: this.nextTime, bar: this.bar, beat: this.beat, sub: this.subIdx,
        accent: tickAccent(this.meter, this.beat, this.subIdx, this.accentOn), bpm: this.bpm
      });
      this.nextTime += secondsPerTick(this.bpm, this.subCount);
      this.subIdx++;
      if (this.subIdx >= this.subCount) {
        this.subIdx = 0;
        this.beat++;
        if (this.beat >= this.meter.beats) { this.beat = 0; this.bar++; }
      }
    }
    return out;
  };

  /* ---- 탭 템포 ----
     state: {taps:[ms,...]}. 마지막 탭에서 2초가 넘으면 처음부터. 최근 8번 탭의 평균 간격으로 BPM. */
  function tapTempo(state, now) {
    var taps = (state && state.taps ? state.taps : []).slice();
    if (taps.length && now - taps[taps.length - 1] > TAP_RESET_MS) taps = [];
    taps.push(now);
    if (taps.length > TAP_KEEP) taps = taps.slice(taps.length - TAP_KEEP);
    var bpm = null;
    if (taps.length >= 2) {
      var avg = (taps[taps.length - 1] - taps[0]) / (taps.length - 1);
      if (avg > 0) bpm = clampBpm(60000 / avg);
    }
    return {taps: taps, bpm: bpm};
  }

  /* ---- 템포 용어 ---- */
  var TERMS = [
    {id: 'largo', max: 59}, {id: 'larghetto', max: 65}, {id: 'adagio', max: 75}, {id: 'andante', max: 107},
    {id: 'moderato', max: 119}, {id: 'allegro', max: 155}, {id: 'vivace', max: 167}, {id: 'presto', max: Infinity}
  ];
  function termForBpm(bpm) {
    for (var i = 0; i < TERMS.length; i++) if (bpm <= TERMS[i].max) return TERMS[i].id;
    return 'presto';
  }

  /* 연습 타이머: 끝 timestamp 와 now 로 남은 ms. */
  function practiceRemaining(endTs, now) { return Math.max(0, endTs - now); }

  /* 오디오 시계 초 -> 벽시계 ms (연습 타이머 종료 시각과 비교용) */
  function tickWallMs(tickTime, ctxNow, wallNow) { return wallNow + (tickTime - ctxNow) * 1000; }

  /* ---- 저장된 설정 ---- */
  var SOUNDS = ['click', 'wood', 'beep'];
  var DEFAULTS = {
    bpm: 100, sig: '4/4', customBeats: 5, sub: 'quarter', accent: true, volume: 80, sound: 'click',
    trainer: {on: false, start: 80, target: 120, every: 4, step: 5}, practiceMin: 0, wake: false
  };

  function sanitizeSettings(raw) {
    raw = raw && typeof raw === 'object' ? raw : {};
    var d = DEFAULTS;
    return {
      bpm: clampBpm(raw.bpm, d.bpm),
      sig: SIG_IDS.indexOf(raw.sig) >= 0 ? raw.sig : d.sig,
      customBeats: clampInt(raw.customBeats, 1, 16, d.customBeats),
      sub: SUB_IDS.indexOf(raw.sub) >= 0 ? raw.sub : d.sub,
      accent: raw.accent === false ? false : true,
      volume: clampInt(raw.volume, 0, 100, d.volume),
      sound: SOUNDS.indexOf(raw.sound) >= 0 ? raw.sound : d.sound,
      trainer: normalizeTrainer(raw.trainer || d.trainer),
      practiceMin: clampInt(raw.practiceMin, 0, 180, 0),
      wake: raw.wake === true
    };
  }

  return {
    BPM_MIN: BPM_MIN, BPM_MAX: BPM_MAX, SIG_IDS: SIG_IDS, SUB_IDS: SUB_IDS, SOUNDS: SOUNDS, TERMS: TERMS,
    SIGNATURES: SIGNATURES, SUBDIVISIONS: SUBDIVISIONS, DEFAULTS: DEFAULTS,
    clampBpm: clampBpm, clampInt: clampInt, meterFor: meterFor, secondsPerTick: secondsPerTick,
    tickAccent: tickAccent, normalizeTrainer: normalizeTrainer, trainerBpm: trainerBpm, trainerReached: trainerReached,
    Scheduler: Scheduler, tapTempo: tapTempo, termForBpm: termForBpm,
    practiceRemaining: practiceRemaining, tickWallMs: tickWallMs, sanitizeSettings: sanitizeSettings
  };
});
