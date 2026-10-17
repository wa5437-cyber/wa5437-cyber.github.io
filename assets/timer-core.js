/* 온라인 타이머의 순수 계산 모듈. 브라우저(window.TimerCore)와 node(require) 양쪽에서 쓴다.
   시간은 전부 "종료/시작 timestamp(ms)" 기준으로 계산한다. setInterval 로 숫자를 깎지 않는다. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.TimerCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var SEC = 1000, MIN = 60000, HOUR = 3600000;
  var MAX_MS = 359999 * SEC;          // 99:59:59

  function clampInt(v, lo, hi, fallback) {
    var n = Math.round(Number(v));
    if (!isFinite(n) || v === '' || v === null) n = fallback === undefined ? lo : fallback;
    return Math.min(hi, Math.max(lo, n));
  }

  function hmsToMs(h, m, s) {
    var total = clampInt(h, 0, 99, 0) * 3600 + clampInt(m, 0, 5999, 0) * 60 + clampInt(s, 0, 359999, 0);
    return Math.min(MAX_MS, total * SEC);
  }

  function pad(n, w) { n = String(n); while (n.length < (w || 2)) n = '0' + n; return n; }

  /* 카운트다운 표시: 남은 시간은 올림(0.2초 남아도 00:01). 한 시간 이상이면 h:mm:ss. */
  function formatClock(ms, mode) {
    ms = Math.max(0, ms);
    var secs = mode === 'floor' ? Math.floor(ms / SEC) : Math.ceil(ms / SEC);
    var h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
    return h > 0 ? h + ':' + pad(m) + ':' + pad(s) : pad(m) + ':' + pad(s);
  }

  /* 스톱워치 표시: 내림, 1/100초. */
  function formatStopwatch(ms) {
    ms = Math.max(0, ms);
    var cs = Math.floor(ms / 10) % 100;
    return formatClock(ms, 'floor') + '.' + pad(cs);
  }

  /* 분 단위로 읽어 줄 값(스크린리더 안내용): 남은 올림 분. */
  function wholeMinutes(ms) { return Math.ceil(Math.max(0, ms) / MIN); }

  /* ---- 카운트다운 ---- */
  /* run: {status:'running'|'paused'|'done', totalMs, endTs, remainingMs} */
  function countdownView(run, now) {
    if (!run) return {status: 'idle', remainingMs: 0, progress: 0};
    var total = run.totalMs || 0, rem;
    if (run.status === 'running') {
      rem = Math.max(0, run.endTs - now);
      return {status: rem > 0 ? 'running' : 'done', remainingMs: rem, progress: total ? 1 - rem / total : 1};
    }
    if (run.status === 'paused') {
      rem = Math.max(0, run.remainingMs);
      return {status: 'paused', remainingMs: rem, progress: total ? 1 - rem / total : 1};
    }
    return {status: 'done', remainingMs: 0, progress: 1};
  }

  /* 알림 목록. kind: 'pre'(종료 N분 전) | 'end'. fromTs 초과 ~ toTs 이하만. */
  function countdownEvents(endTs, totalMs, preMin, fromTs, toTs) {
    var out = [], preMs = (preMin || 0) * MIN;
    if (preMs > 0 && preMs < totalMs) push(out, {kind: 'pre', ts: endTs - preMs, preMin: preMin}, fromTs, toTs);
    push(out, {kind: 'end', ts: endTs}, fromTs, toTs);
    return out;
  }

  function push(out, ev, fromTs, toTs) {
    if (ev.ts > fromTs && ev.ts <= toTs) { ev.id = ev.kind + ':' + ev.ts; out.push(ev); }
  }

  /* ---- 스톱워치 ---- */
  /* run: {status:'running'|'paused', startTs, elapsedMs, laps:[누적 ms,...]} (startTs 는 running 구간의 시작) */
  function stopwatchElapsed(run, now) {
    if (!run) return 0;
    return run.status === 'running' ? run.elapsedMs + Math.max(0, now - run.startTs) : run.elapsedMs;
  }

  function lapRows(laps) {
    var prev = 0;
    return laps.map(function (total, i) {
      var row = {n: i + 1, total: total, split: total - prev};
      prev = total;
      return row;
    });
  }

  /* ---- 시작·종료 시각 ---- */
  function parseHM(str) {
    var m = /^(\d{1,2}):(\d{2})$/.exec(String(str || '').trim());
    if (!m) return null;
    var h = +m[1], mi = +m[2];
    return h > 23 || mi > 59 ? null : h * 60 + mi;
  }

  function atTime(now, dayOffset, minOfDay) {
    var d = new Date(now);
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() + dayOffset);
    d.setHours(Math.floor(minOfDay / 60), minOfDay % 60, 0, 0);
    return d.getTime();
  }

  /* "HH:MM" 두 개 -> {startTs,endTs}. 종료가 시작보다 이르면 자정을 넘긴 것으로 본다.
     진행 중인 구간(어제 시작 포함)이 있으면 그것, 아니면 오늘 구간(앞으로 올 것이거나 이미 끝난 것). */
  function computeRange(startHM, endHM, now) {
    var s = parseHM(startHM), e = parseHM(endHM);
    if (s === null || e === null) return {error: 'invalid'};
    if (s === e) return {error: 'same'};
    var crosses = e < s, i, cand, list = [];
    for (i = -1; i <= 0; i++) {
      list.push({startTs: atTime(now, i, s), endTs: atTime(now, crosses ? i + 1 : i, e)});
    }
    for (i = 0; i < list.length; i++) {
      cand = list[i];
      if (cand.startTs <= now && now < cand.endTs) return cand;
    }
    return list[1];
  }

  function rangeStatus(startTs, endTs, now) {
    var total = endTs - startTs;
    if (now < startTs) return {phase: 'waiting', totalMs: total, elapsedMs: 0, remainingMs: total, untilStartMs: startTs - now, progress: 0};
    if (now >= endTs) return {phase: 'ended', totalMs: total, elapsedMs: total, remainingMs: 0, untilStartMs: 0, progress: 1};
    return {phase: 'running', totalMs: total, elapsedMs: now - startTs, remainingMs: endTs - now, untilStartMs: 0, progress: (now - startTs) / total};
  }

  function rangeEvents(startTs, endTs, preMin, fromTs, toTs) {
    var out = [], preMs = (preMin || 0) * MIN;
    push(out, {kind: 'start', ts: startTs}, fromTs, toTs);
    if (preMs > 0 && preMs < endTs - startTs) push(out, {kind: 'pre', ts: endTs - preMs, preMin: preMin}, fromTs, toTs);
    push(out, {kind: 'end', ts: endTs}, fromTs, toTs);
    return out;
  }

  /* ---- 반복(작업/휴식) ---- */
  /* plan: {workMs, restMs, cycles}  cycles 0 = 멈출 때까지. 마지막 작업 뒤에는 휴식이 없다. */
  function normalizePlan(plan) {
    return {
      workMs: clampInt(plan.workMs / MIN, 1, 600, 25) * MIN,
      restMs: clampInt(plan.restMs / MIN, 0, 600, 5) * MIN,
      cycles: clampInt(plan.cycles, 0, 99, 4)
    };
  }

  function planTotalMs(plan) {
    return plan.cycles > 0 ? plan.cycles * plan.workMs + (plan.cycles - 1) * plan.restMs : Infinity;
  }

  function intervalState(plan, elapsed) {
    var w = plan.workMs, r = plan.restMs, period = w + r;
    elapsed = Math.max(0, elapsed);
    if (plan.cycles > 0) {
      var total = planTotalMs(plan);
      if (elapsed >= total) return {phase: 'done', cycle: plan.cycles, cycles: plan.cycles, phaseRemainingMs: 0, phaseTotalMs: w, progress: 1};
    }
    var k = Math.floor(elapsed / period), within = elapsed - k * period;
    var base = {cycle: k + 1, cycles: plan.cycles};
    var total2 = planTotalMs(plan);
    base.progress = isFinite(total2) ? elapsed / total2 : 0;
    if (within < w) { base.phase = 'work'; base.phaseRemainingMs = w - within; base.phaseTotalMs = w; }
    else { base.phase = 'rest'; base.phaseRemainingMs = period - within; base.phaseTotalMs = r; }
    return base;
  }

  /* 구간 시작/끝 알림. kind: 'work'(작업 시작) | 'rest'(휴식 시작) | 'pre' | 'done'. fromTs 초과 ~ toTs 이하. */
  function intervalEvents(plan, startTs, preMin, fromTs, toTs) {
    var out = [], w = plan.workMs, r = plan.restMs, period = w + r, preMs = (preMin || 0) * MIN;
    var k = Math.max(0, Math.floor((fromTs - startTs) / period) - 1);
    for (; plan.cycles === 0 || k < plan.cycles; k++) {
      var ws = startTs + k * period, we = ws + w;
      if (ws > toTs) break;
      if (k > 0) push(out, {kind: 'work', ts: ws, cycle: k + 1}, fromTs, toTs);
      if (preMs > 0 && preMs < w) push(out, {kind: 'pre', ts: we - preMs, preMin: preMin, cycle: k + 1}, fromTs, toTs);
      var last = plan.cycles > 0 && k === plan.cycles - 1;
      if (last) push(out, {kind: 'done', ts: we}, fromTs, toTs);
      else if (r > 0) push(out, {kind: 'rest', ts: we, cycle: k + 1}, fromTs, toTs);
    }
    out.sort(function (a, b) { return a.ts - b.ts; });
    return out;
  }

  /* ---- 저장된 진행 상태 복원 ---- */
  var MODES = ['countdown', 'stopwatch', 'range', 'interval', 'booking'];
  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  /* localStorage 에서 읽은 값을 믿지 않고 모양을 검사해 돌려준다. 못 쓰면 null. */
  function sanitizeRun(run, now) {
    if (!run || typeof run !== 'object' || MODES.indexOf(run.mode) < 0) return null;
    var out = {mode: run.mode};
    if (run.mode === 'countdown' || run.mode === 'booking') {
      if (!isNum(run.totalMs) || run.totalMs <= 0 || run.totalMs > MAX_MS) return null;
      out.totalMs = run.totalMs;
      out.preMin = clampInt(run.preMin, 0, 999, 0);
      if (run.status === 'running' && isNum(run.endTs)) {
        out.status = run.endTs > now ? 'running' : 'done';
        out.endTs = run.endTs;
      } else if (run.status === 'paused' && isNum(run.remainingMs)) {
        out.status = 'paused';
        out.remainingMs = Math.min(run.totalMs, Math.max(0, run.remainingMs));
      } else if (run.status === 'done') out.status = 'done';
      else return null;
    } else if (run.mode === 'stopwatch') {
      if (!isNum(run.elapsedMs) || run.elapsedMs < 0) return null;
      out.elapsedMs = run.elapsedMs;
      out.laps = Array.isArray(run.laps) ? run.laps.filter(isNum).slice(0, 500) : [];
      if (run.status === 'running' && isNum(run.startTs) && run.startTs <= now + 1000) {
        out.status = 'running';
        out.startTs = Math.min(run.startTs, now);
      } else if (run.status === 'paused') out.status = 'paused';
      else return null;
    } else if (run.mode === 'range') {
      if (!isNum(run.startTs) || !isNum(run.endTs) || run.endTs <= run.startTs) return null;
      out.status = 'active';
      out.startTs = run.startTs;
      out.endTs = run.endTs;
      out.preMin = clampInt(run.preMin, 0, 999, 0);
      if (typeof run.startHM === 'string') out.startHM = run.startHM;
      if (typeof run.endHM === 'string') out.endHM = run.endHM;
    } else {
      var p = run.plan;
      if (!p || !isNum(p.workMs) || !isNum(p.restMs) || !isNum(p.cycles)) return null;
      out.plan = normalizePlan(p);
      out.preMin = clampInt(run.preMin, 0, 999, 0);
      if (run.status === 'running' && isNum(run.startTs)) {
        out.startTs = Math.min(run.startTs, now);
        out.status = intervalState(out.plan, now - out.startTs).phase === 'done' ? 'done' : 'running';
      } else if (run.status === 'paused' && isNum(run.elapsedMs) && run.elapsedMs >= 0) {
        out.status = 'paused';
        out.elapsedMs = run.elapsedMs;
      } else if (run.status === 'done') { out.status = 'done'; }
      else return null;
    }
    return out;
  }

  return {
    SEC: SEC, MIN: MIN, HOUR: HOUR, MAX_MS: MAX_MS,
    clampInt: clampInt, hmsToMs: hmsToMs, formatClock: formatClock, formatStopwatch: formatStopwatch,
    wholeMinutes: wholeMinutes,
    countdownView: countdownView, countdownEvents: countdownEvents,
    stopwatchElapsed: stopwatchElapsed, lapRows: lapRows,
    parseHM: parseHM, computeRange: computeRange, rangeStatus: rangeStatus, rangeEvents: rangeEvents,
    normalizePlan: normalizePlan, planTotalMs: planTotalMs, intervalState: intervalState, intervalEvents: intervalEvents,
    sanitizeRun: sanitizeRun
  };
});
