/* 온라인 타이머 화면 로직. 계산은 timer-core.js, 문자열은 페이지가 내려 준 #i18n 사전을 쓴다.
   서버로 아무것도 보내지 않는다. 설정·진행 상태는 이 기기의 localStorage 에만 저장한다. */
(function () {
  'use strict';
  var core = window.TimerCore;
  var doc = document;
  var root = doc.getElementById('tool');
  if (!core || !root) return;

  function $(id) { return doc.getElementById(id); }
  var data;
  try { data = JSON.parse($('i18n').textContent); } catch (e) { return; }
  var ui = data.ui;

  function tr(key, vars) {
    var s = ui[key];
    if (s == null) return key;
    return vars ? s.replace(/\{(\w+)\}/g, function (m, k) { return vars[k] != null ? vars[k] : m; }) : s;
  }
  function spoken(ms) {
    var mins = Math.max(0, Math.ceil(ms / 60000)), h = Math.floor(mins / 60), m = mins % 60, parts = [];
    if (h) parts.push(tr('dur_h', {n: h}));
    if (m || !h) parts.push(tr('dur_m', {n: m}));
    return parts.join(ui.dur_sep);
  }

  /* ---------- 저장소 (실패해도 조용히) ---------- */
  var KEY_SET = 'mlms.timer.settings.v1', KEY_RUN = 'mlms.timer.run.v1';
  var store = {
    get: function (k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* 저장 불가: 무시 */ } },
    del: function (k) { try { localStorage.removeItem(k); } catch (e) { /* 무시 */ } }
  };

  var PRESETS = {
    mix: {work: 45, rest: 5, cycles: 4},
    pomodoro: {work: 25, rest: 5, cycles: 4},
    practice: {work: 20, rest: 5, cycles: 3}
  };
  var MODES = ['countdown', 'stopwatch', 'range', 'interval', 'booking'];
  var SOUNDS = ['bell', 'beep', 'chime'];

  function loadSettings() {
    var s = store.get(KEY_SET) || {}, ci = core.clampInt;
    var cd = s.cd || {}, iv = s.iv || {}, rg = s.range || {};
    return {
      mode: MODES.indexOf(s.mode) >= 0 ? s.mode : 'countdown',
      cd: {h: ci(cd.h, 0, 99, 0), m: ci(cd.m, 0, 5999, 25), s: ci(cd.s, 0, 5999, 0)},
      range: {start: typeof rg.start === 'string' ? rg.start : '', end: typeof rg.end === 'string' ? rg.end : ''},
      iv: {
        preset: PRESETS[iv.preset] || iv.preset === 'custom' ? iv.preset : 'mix',
        work: ci(iv.work, 1, 600, 45), rest: ci(iv.rest, 0, 600, 5), cycles: ci(iv.cycles, 0, 99, 4)
      },
      bookH: [1, 2, 3].indexOf(s.bookH) >= 0 ? s.bookH : 2,
      bookPre: ci(s.bookPre, 0, 120, 10),
      preOn: s.preOn === true, preMin: ci(s.preMin, 1, 999, 5),
      sound: SOUNDS.indexOf(s.sound) >= 0 ? s.sound : 'bell',
      volume: ci(s.volume, 0, 100, 70), repeat: ci(s.repeat, 1, 5, 2),
      notify: s.notify === true, wake: s.wake === true
    };
  }
  var settings = loadSettings();
  function saveSettings() { store.set(KEY_SET, settings); }

  /* ---------- 상태 ---------- */
  var sel = settings.mode;
  var run = null;
  var cursor = Date.now();          // 이 시각까지의 알림은 처리했다
  var fired = {};
  var sched = {};                   // 오디오 시계에 미리 예약한 알림
  var HORIZON = 20 * 60 * 1000;
  var lastMin = null;
  var baseTitle = doc.title;
  var timerId = null;

  function persistRun() { if (run) store.set(KEY_RUN, run); else store.del(KEY_RUN); }

  /* ---------- 요소 ---------- */
  var el = {
    time: $('disp-time'), label: $('disp-label'), bar: $('disp-bar'), barWrap: $('disp-barwrap'),
    card: $('display-card'), main: $('btn-main'), lap: $('btn-lap'), reset: $('btn-reset'), full: $('btn-full'),
    laps: $('laps'), lapsWrap: $('laps-wrap'), stats: $('range-stats'), sr: $('sr-live'), hint: $('hint'),
    other: $('other-run'), otherText: $('other-run-text'), otherBtn: $('btn-goto'), rangeMsg: $('range-msg')
  };
  var tabs = {}, panels = {};
  MODES.forEach(function (m) { tabs[m] = $('tab-' + m); panels[m] = $('panel-' + m); });

  function setText(node, txt) { if (node && node.textContent !== txt) node.textContent = txt; }
  function setHidden(node, hide) { if (node && node.hidden !== hide) node.hidden = hide; }

  function announce(msg) {
    if (!el.sr) return;
    el.sr.textContent = '';
    setTimeout(function () { el.sr.textContent = msg; }, 60);
  }
  function showHint(msg) { setText(el.hint, msg || ''); setHidden(el.hint, !msg); }

  /* ---------- 소리 (WebAudio 합성) ---------- */
  var ctx = null, master = null;
  function volGain() { var v = settings.volume / 100; return v * v; }
  function ensureAudio() {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    if (!ctx) {
      try {
        ctx = new AC();
        master = ctx.createGain();
        master.gain.value = volGain();
        master.connect(ctx.destination);
      } catch (e) { ctx = null; return null; }
    }
    if (ctx.state === 'suspended') { try { ctx.resume(); } catch (e2) { /* 무시 */ } }
    return ctx;
  }
  function audioReady() { return !!(ctx && ctx.state === 'running'); }

  function notesFor(sound, mul) {
    if (sound === 'beep') return [0, 0.2, 0.4].map(function (t) { return {f: 1000 * mul, t: t, d: 0.11, type: 'square', g: 0.22}; });
    if (sound === 'chime') return [{f: 659.25 * mul, t: 0, d: 0.9, type: 'sine', g: 0.55}, {f: 880 * mul, t: 0.3, d: 1.2, type: 'sine', g: 0.55}];
    return [{f: 880 * mul, t: 0, d: 1.8, type: 'sine', g: 0.6, partial: 2.76}];
  }
  function cueNotes(kind) {
    var sound = settings.sound;
    var mul = kind === 'rest' ? 0.8 : (kind === 'work' || kind === 'start') ? 1.25 : 1;
    var span = sound === 'beep' ? 0.95 : sound === 'chime' ? 1.7 : 1.9;
    var times = (kind === 'end' || kind === 'done') ? settings.repeat : 1;
    var gainMul = kind === 'pre' ? 0.7 : 1, out = [], i;
    for (i = 0; i < times; i++) {
      notesFor(sound, mul).forEach(function (n) {
        out.push({f: n.f, t: n.t + i * span, d: n.d, type: n.type, g: n.g * gainMul, partial: n.partial});
      });
    }
    return out;
  }
  function voice(freq, type, when, dur, gain, nodes) {
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type;
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, when);
    g.gain.linearRampToValueAtTime(gain, when + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    o.connect(g);
    g.connect(master);
    o.start(when);
    o.stop(when + dur + 0.05);
    nodes.push({osc: o, gain: g});
  }
  function playCue(kind, when) {
    var nodes = [];
    if (!audioReady()) return nodes;
    cueNotes(kind).forEach(function (n) {
      voice(n.f, n.type, when + n.t, n.d, n.g, nodes);
      if (n.partial) voice(n.f * n.partial, 'sine', when + n.t, n.d * 0.5, n.g * 0.25, nodes);
    });
    return nodes;
  }
  function stopNodes(nodes) {
    nodes.forEach(function (n) {
      try { n.osc.stop(0); } catch (e) { /* 이미 끝남 */ }
      try { n.gain.disconnect(); } catch (e2) { /* 무시 */ }
    });
  }
  function cancelAudio() {
    Object.keys(sched).forEach(function (id) { stopNodes(sched[id].nodes); });
    sched = {};
  }

  /* ---------- 알림 목록 ---------- */
  function eventsBetween(r, from, to) {
    if (!r) return [];
    if (r.mode === 'countdown' || r.mode === 'booking') {
      return r.status === 'running' ? core.countdownEvents(r.endTs, r.totalMs, r.preMin, from, to) : [];
    }
    if (r.mode === 'range') return core.rangeEvents(r.startTs, r.endTs, r.preMin, from, to);
    if (r.mode === 'interval') {
      return r.status === 'running' ? core.intervalEvents(r.plan, r.startTs, r.preMin, from, to) : [];
    }
    return [];
  }

  function scheduleAhead(now) {
    if (!run || !audioReady()) return;
    eventsBetween(run, now, now + HORIZON).forEach(function (ev) {
      if (sched[ev.id] || fired[ev.id]) return;
      var when = ctx.currentTime + (ev.ts - Date.now()) / 1000;
      if (when <= ctx.currentTime) return;
      sched[ev.id] = {ctxTime: when, nodes: playCue(ev.kind, when)};
    });
  }

  function notify(body) {
    if (!settings.notify || !('Notification' in window) || Notification.permission !== 'granted') return;
    try { new Notification(tr('tool_name'), {body: body, tag: 'mlms-timer'}); } catch (e) { /* 일부 모바일 브라우저는 지원 안 함 */ }
  }

  function fire(ev, now) {
    fired[ev.id] = true;
    var late = now - ev.ts, s = sched[ev.id];
    if (s) {
      // 오디오 시계가 그 시각까지 흘렀으면 이미 울린 것. 멈춰 있었다면 지금 대신 울린다.
      if (!(ctx && ctx.currentTime >= s.ctxTime - 0.05)) {
        stopNodes(s.nodes);
        if (late < 30000) playCue(ev.kind, ctx ? ctx.currentTime : 0);
      }
      delete sched[ev.id];
    } else if (late < 30000 && audioReady()) {
      playCue(ev.kind, ctx.currentTime);
    }
    var msg = '';
    if (ev.kind === 'pre') msg = tr('sr_pre', {n: ev.preMin});
    else if (ev.kind === 'start') msg = tr('sr_range_start');
    else if (ev.kind === 'work') msg = tr('sr_phase_work');
    else if (ev.kind === 'rest') msg = tr('sr_phase_rest');
    else if (ev.kind === 'end') { msg = tr('sr_done'); if (run.mode !== 'range') run.status = 'done'; }
    else if (ev.kind === 'done') { msg = tr('sr_all_done'); run.status = 'done'; }
    if (msg) { announce(msg); notify(msg); }
    persistRun();
  }

  function processEvents(now) {
    if (!run) return;
    eventsBetween(run, cursor, now).forEach(function (ev) { if (!fired[ev.id]) fire(ev, now); });
    scheduleAhead(now);
  }

  /* ---------- 실행 제어 ---------- */
  function stopRun() { cancelAudio(); run = null; fired = {}; lastMin = null; persistRun(); }

  function preMinNow() { return settings.preOn ? settings.preMin : 0; }

  function cdInputMs() {
    return core.hmsToMs($('cd-h').value, $('cd-m').value, $('cd-s').value);
  }
  function planFromFields() {
    return core.normalizePlan({
      workMs: core.clampInt($('iv-work').value, 1, 600, 25) * 60000,
      restMs: core.clampInt($('iv-rest').value, 0, 600, 5) * 60000,
      cycles: core.clampInt($('iv-cycles').value, 0, 99, 4)
    });
  }

  function begin(mode, now, extra) {
    ensureAudio();
    stopRun();
    cursor = now;
    run = {mode: mode};
    var k;
    for (k in extra) if (Object.prototype.hasOwnProperty.call(extra, k)) run[k] = extra[k];
    persistRun();
    showHint('');
    syncWake();
    tick();
  }

  function startCurrent(now) {
    if (sel === 'countdown') {
      var ms = cdInputMs();
      if (ms <= 0) return;
      begin('countdown', now, {status: 'running', totalMs: ms, endTs: now + ms, preMin: preMinNow()});
    } else if (sel === 'interval') {
      begin('interval', now, {status: 'running', plan: planFromFields(), startTs: now, preMin: preMinNow()});
    } else if (sel === 'stopwatch') {
      begin('stopwatch', now, {status: 'running', startTs: now, elapsedMs: 0, laps: []});
    }
  }

  function pauseRun(now) {
    cancelAudio();
    if (run.mode === 'countdown' || run.mode === 'booking') {
      run.remainingMs = Math.max(0, run.endTs - now);
      delete run.endTs;
    } else if (run.mode === 'interval') {
      run.elapsedMs = now - run.startTs;
      delete run.startTs;
    } else if (run.mode === 'stopwatch') {
      run.elapsedMs += now - run.startTs;
      delete run.startTs;
    }
    run.status = 'paused';
    persistRun();
    syncWake();
  }

  function resumeRun(now) {
    ensureAudio();
    if (run.mode === 'countdown' || run.mode === 'booking') {
      run.endTs = now + run.remainingMs;
      delete run.remainingMs;
    } else if (run.mode === 'interval') {
      run.startTs = now - run.elapsedMs;
      delete run.elapsedMs;
    } else if (run.mode === 'stopwatch') {
      run.startTs = now;
    }
    run.status = 'running';
    cursor = now;
    persistRun();
    syncWake();
    tick();
  }

  function onMain() {
    var now = Date.now(), r = run && run.mode === sel ? run : null;
    if (r && r.status === 'running') pauseRun(now);
    else if (r && r.status === 'paused') resumeRun(now);
    else startCurrent(now);
    tick();
  }

  function onReset() {
    stopRun();
    releaseWake();
    doc.title = baseTitle;
    showHint('');
    tick();
  }

  function onLap() {
    if (!run || run.mode !== 'stopwatch' || run.status !== 'running') return;
    run.laps.push(core.stopwatchElapsed(run, Date.now()));
    persistRun();
    renderLaps(true);
  }

  function applyRange() {
    var s = $('rg-start').value, e = $('rg-end').value, now = Date.now();
    var res = core.computeRange(s, e, now);
    if (res.error) {
      setText(el.rangeMsg, tr(res.error === 'same' ? 'range_err_same' : 'range_err_invalid'));
      setHidden(el.rangeMsg, false);
      return;
    }
    setHidden(el.rangeMsg, true);
    settings.range = {start: s, end: e};
    saveSettings();
    begin('range', now, {status: 'active', startTs: res.startTs, endTs: res.endTs, preMin: preMinNow(), startHM: s, endHM: e});
  }

  function startBooking(h) {
    var now = Date.now();
    settings.bookH = h;
    saveSettings();
    var ms = h * 3600000;
    begin('booking', now, {status: 'running', totalMs: ms, endTs: now + ms, preMin: core.clampInt($('book-pre').value, 0, 120, 10)});
  }

  /* ---------- 화면 꺼짐 방지 · 알림 · 전체 화면 ---------- */
  var wakeLock = null, wakePending = false;
  function runActive(now) {
    if (!run) return false;
    if (run.mode === 'range') return now < run.endTs;
    return run.status === 'running';
  }
  function releaseWake() {
    if (wakeLock) { try { wakeLock.release(); } catch (e) { /* 무시 */ } wakeLock = null; }
  }
  function syncWake() {
    if (!navigator.wakeLock) return;
    var want = settings.wake && runActive(Date.now()) && !doc.hidden;
    if (want && !wakeLock && !wakePending) {
      wakePending = true;
      navigator.wakeLock.request('screen').then(function (l) {
        wakePending = false;
        wakeLock = l;
        l.addEventListener('release', function () { if (wakeLock === l) wakeLock = null; });
        if (!settings.wake) releaseWake();
      }).catch(function () { wakePending = false; });
    } else if (!want && wakeLock) {
      releaseWake();
    }
  }

  function toggleFull() {
    var fs = doc.fullscreenElement || doc.webkitFullscreenElement;
    try {
      if (fs) (doc.exitFullscreen || doc.webkitExitFullscreen).call(doc);
      else (root.requestFullscreen || root.webkitRequestFullscreen).call(root);
    } catch (e) { /* 지원 안 함 */ }
  }
  function onFullChange() {
    var fs = !!(doc.fullscreenElement || doc.webkitFullscreenElement);
    setText(el.full, fs ? tr('btn_full_exit') : tr('btn_full'));
  }

  /* ---------- 화면 그리기 ---------- */
  function viewFor(mode, r, now) {
    var v = {time: '', label: '', state: 'idle', progress: 0, bar: true, sub: ''};
    if (mode === 'countdown' || mode === 'booking') {
      if (!r) {
        var total = mode === 'booking' ? settings.bookH * 3600000 : cdInputMs();
        v.time = core.formatClock(total);
        v.label = tr('st_ready');
        return v;
      }
      var cv = core.countdownView(r, now);
      v.time = core.formatClock(cv.remainingMs);
      v.progress = cv.progress;
      v.state = cv.status;
      v.label = tr(cv.status === 'running' ? 'st_running' : cv.status === 'paused' ? 'st_paused' : 'st_done');
      v.remainingMs = cv.remainingMs;
      return v;
    }
    if (mode === 'stopwatch') {
      var el0 = r ? core.stopwatchElapsed(r, now) : 0;
      v.time = core.formatStopwatch(el0);
      v.bar = false;
      v.state = r ? r.status : 'idle';
      v.label = tr(!r ? 'st_ready' : r.status === 'running' ? 'st_running' : 'st_paused');
      return v;
    }
    if (mode === 'range') {
      if (!r) { v.time = '00:00'; v.label = tr('st_ready'); return v; }
      var rs = core.rangeStatus(r.startTs, r.endTs, now);
      v.progress = rs.progress;
      v.state = rs.phase;
      if (rs.phase === 'waiting') { v.time = core.formatClock(rs.untilStartMs); v.label = tr('range_until'); }
      else if (rs.phase === 'running') { v.time = core.formatClock(rs.remainingMs); v.label = tr('st_running'); }
      else { v.time = core.formatClock(0); v.label = tr('st_ended'); }
      v.range = rs;
      v.remainingMs = rs.phase === 'waiting' ? null : rs.remainingMs;
      return v;
    }
    // interval
    if (!r) {
      var p = planFromFields();
      v.time = core.formatClock(p.workMs);
      v.label = tr('phase_work');
      return v;
    }
    var elapsed = r.status === 'running' ? now - r.startTs : r.elapsedMs;
    var st = core.intervalState(r.plan, r.status === 'done' ? Infinity : elapsed);
    v.time = core.formatClock(st.phaseRemainingMs);
    v.state = st.phase === 'done' ? 'done' : (r.status === 'paused' ? 'paused' : st.phase);
    v.progress = st.phase === 'done' ? 1 : 1 - st.phaseRemainingMs / st.phaseTotalMs;
    var cyc = r.plan.cycles > 0 ? tr('cycle_n', {n: st.cycle, total: st.cycles}) : tr('cycle_n_inf', {n: st.cycle});
    v.label = st.phase === 'done' ? tr('st_done') : tr(st.phase === 'work' ? 'phase_work' : 'phase_rest') + ' · ' + cyc +
      (r.status === 'paused' ? ' · ' + tr('st_paused') : '');
    v.remainingMs = st.phaseRemainingMs;
    return v;
  }

  var lapCount = -1;
  function renderLaps(force) {
    var laps = run && run.mode === 'stopwatch' ? run.laps : [];
    if (!force && lapCount === laps.length) return;
    lapCount = laps.length;
    var rows = core.lapRows(laps).reverse();
    el.laps.textContent = '';
    rows.forEach(function (r) {
      var li = doc.createElement('li');
      [['lap-n', tr('lap_n', {n: r.n})], ['lap-split', core.formatStopwatch(r.split)], ['lap-total', core.formatStopwatch(r.total)]].forEach(function (c) {
        var sp = doc.createElement('span');
        sp.className = c[0];
        sp.textContent = c[1];
        li.appendChild(sp);
      });
      el.laps.appendChild(li);
    });
    setHidden(el.lapsWrap, sel !== 'stopwatch' || !rows.length);
  }

  function setDisabled(node, v) { if (node && node.disabled !== v) node.disabled = v; }

  function renderStats(v, r) {
    var rs = v.range;
    if (!rs || !r) { setHidden(el.stats, true); return; }
    setHidden(el.stats, false);
    var crosses = new Date(r.endTs).getDate() !== new Date(r.startTs).getDate();
    setText($('rs-window'), (r.startHM || '') + ' – ' + (r.endHM || '') + (crosses ? ' ' + tr('range_next_day') : ''));
    setText($('rs-total'), core.formatClock(rs.totalMs));
    setText($('rs-elapsed'), core.formatClock(rs.elapsedMs, 'floor'));
    setText($('rs-left'), core.formatClock(rs.remainingMs));
  }

  function render(now) {
    var r = run && run.mode === sel ? run : null;
    var v = viewFor(sel, r, now);
    setText(el.time, v.time);
    setText(el.label, v.label);
    el.card.setAttribute('data-state', v.state);
    el.time.classList.toggle('is-sw', sel === 'stopwatch');
    setHidden(el.barWrap, !v.bar);
    var pct = Math.max(0, Math.min(1, v.progress)) * 100;
    var w = pct.toFixed(2) + '%';
    if (el.bar.style.width !== w) el.bar.style.width = w;

    var active = !!r, running = r && r.status === 'running', paused = r && r.status === 'paused';
    setHidden(el.main, sel === 'range' || (sel === 'booking' && !r));
    setHidden(el.lap, sel !== 'stopwatch');
    setDisabled(el.lap, !running);
    setText(el.main, tr(running ? 'btn_pause' : paused ? 'btn_resume' : 'btn_start'));
    setDisabled(el.reset, !active);
    renderStats(v, r);
    renderLaps(false);

    // 진행 중인 모드의 입력은 잠근다(바꿔도 반영되지 않으므로)
    var locked = !!(r && (r.status === 'running' || r.status === 'paused'));
    var inputs = panels[sel] ? panels[sel].querySelectorAll('input,select,button') : [];
    for (var i = 0; i < inputs.length; i++) {
      if (sel === 'range') continue;
      setDisabled(inputs[i], locked);
    }
    if (sel === 'range') setDisabled($('rg-apply'), false);

    // 다른 모드가 진행 중이면 알려 준다
    var other = run && run.mode !== sel && (run.status !== 'done');
    setHidden(el.other, !other);
    if (other) setText(el.otherText, tr('other_running', {mode: tr('tab_' + run.mode)}));

    // 탭에 진행 표시
    MODES.forEach(function (m) {
      var on = !!(run && run.mode === m && run.status !== 'done' && !(m === 'range' && now >= run.endTs));
      tabs[m].classList.toggle('is-live', on);
    });

    // 탭 제목: 진행 중인 실행의 시간
    if (run && runActive(now)) {
      var rv = run.mode === sel ? v : viewFor(run.mode, run, now);
      var title = rv.time + ' · ' + tr('tool_name');
      if (doc.title !== title) doc.title = title;
      announceMinutes(rv, now);
    } else {
      if (doc.title !== baseTitle && !(run && run.status === 'done')) doc.title = baseTitle;
      if (run && (run.status === 'done' || (run.mode === 'range' && now >= run.endTs))) {
        var dt = tr('st_done') + ' · ' + tr('tool_name');
        if (doc.title !== dt) doc.title = dt;
      }
      lastMin = null;
    }
  }

  function announceMinutes(v, now) {
    if (v.remainingMs == null || v.remainingMs <= 0) { lastMin = null; return; }
    var mins = core.wholeMinutes(v.remainingMs);
    if (lastMin === null) { lastMin = mins; return; }
    if (mins !== lastMin && mins >= 1) {
      lastMin = mins;
      announce(tr('sr_remaining', {t: spoken(v.remainingMs)}));
    }
  }

  function tick() {
    var now = Date.now();
    processEvents(now);
    cursor = now;
    render(now);
    schedule();
  }
  function schedule() {
    if (timerId) clearTimeout(timerId);
    var fast = sel === 'stopwatch' && run && run.mode === 'stopwatch' && run.status === 'running' && !doc.hidden;
    timerId = setTimeout(tick, fast ? 40 : 250);
  }

  /* ---------- 모드 전환 ---------- */
  function selectMode(m, focus) {
    if (MODES.indexOf(m) < 0) return;
    sel = m;
    settings.mode = m;
    saveSettings();
    MODES.forEach(function (k) {
      var on = k === m;
      tabs[k].setAttribute('aria-selected', on ? 'true' : 'false');
      tabs[k].tabIndex = on ? 0 : -1;
      panels[k].hidden = !on;
    });
    if (focus) tabs[m].focus();
    lapCount = -1;
    tick();
  }

  /* ---------- 입력 연결 ---------- */
  function fillInputs() {
    $('cd-h').value = settings.cd.h;
    $('cd-m').value = settings.cd.m;
    $('cd-s').value = settings.cd.s;
    $('rg-start').value = settings.range.start;
    $('rg-end').value = settings.range.end;
    $('iv-preset').value = settings.iv.preset;
    $('iv-work').value = settings.iv.work;
    $('iv-rest').value = settings.iv.rest;
    $('iv-cycles').value = settings.iv.cycles;
    $('book-pre').value = settings.bookPre;
    $('opt-pre').checked = settings.preOn;
    $('opt-pre-min').value = settings.preMin;
    $('opt-sound').value = settings.sound;
    $('opt-volume').value = settings.volume;
    $('opt-repeat').value = settings.repeat;
    $('opt-notify').checked = settings.notify && 'Notification' in window && Notification.permission === 'granted';
    $('opt-wake').checked = settings.wake;
    if (!$('opt-notify').checked) settings.notify = false;
  }

  function bind() {
    MODES.forEach(function (m, i) {
      tabs[m].addEventListener('click', function () { selectMode(m, false); });
      tabs[m].addEventListener('keydown', function (e) {
        var n = null;
        if (e.key === 'ArrowRight') n = MODES[(i + 1) % MODES.length];
        else if (e.key === 'ArrowLeft') n = MODES[(i + MODES.length - 1) % MODES.length];
        else if (e.key === 'Home') n = MODES[0];
        else if (e.key === 'End') n = MODES[MODES.length - 1];
        if (n) { e.preventDefault(); selectMode(n, true); }
      });
    });

    el.main.addEventListener('click', onMain);
    el.reset.addEventListener('click', onReset);
    el.lap.addEventListener('click', onLap);
    el.full.addEventListener('click', toggleFull);
    el.otherBtn.addEventListener('click', function () { if (run) selectMode(run.mode, true); });
    doc.addEventListener('fullscreenchange', onFullChange);
    doc.addEventListener('webkitfullscreenchange', onFullChange);

    ['cd-h', 'cd-m', 'cd-s'].forEach(function (id) {
      $(id).addEventListener('input', function () {
        settings.cd = {h: core.clampInt($('cd-h').value, 0, 99, 0), m: core.clampInt($('cd-m').value, 0, 5999, 0), s: core.clampInt($('cd-s').value, 0, 5999, 0)};
        saveSettings();
        tick();
      });
    });
    Array.prototype.forEach.call(doc.querySelectorAll('[data-quick]'), function (b) {
      b.addEventListener('click', function () {
        var m = parseInt(b.getAttribute('data-quick'), 10);
        $('cd-h').value = Math.floor(m / 60);
        $('cd-m').value = m % 60;
        $('cd-s').value = 0;
        settings.cd = {h: Math.floor(m / 60), m: m % 60, s: 0};
        saveSettings();
        tick();
      });
    });

    $('rg-now').addEventListener('click', function () {
      var d = new Date(), p = function (n) { return (n < 10 ? '0' : '') + n; };
      $('rg-start').value = p(d.getHours()) + ':' + p(d.getMinutes());
    });
    $('rg-apply').addEventListener('click', applyRange);
    ['rg-start', 'rg-end'].forEach(function (id) {
      $(id).addEventListener('change', function () {
        settings.range = {start: $('rg-start').value, end: $('rg-end').value};
        saveSettings();
      });
    });

    function saveIv(fromPreset) {
      var p = $('iv-preset').value;
      if (fromPreset && PRESETS[p]) {
        $('iv-work').value = PRESETS[p].work;
        $('iv-rest').value = PRESETS[p].rest;
        $('iv-cycles').value = PRESETS[p].cycles;
      } else if (!fromPreset) {
        var w = +$('iv-work').value, r = +$('iv-rest').value, c = +$('iv-cycles').value, match = 'custom';
        Object.keys(PRESETS).forEach(function (k) {
          if (PRESETS[k].work === w && PRESETS[k].rest === r && PRESETS[k].cycles === c) match = k;
        });
        $('iv-preset').value = match;
      }
      settings.iv = {
        preset: $('iv-preset').value,
        work: core.clampInt($('iv-work').value, 1, 600, 25), rest: core.clampInt($('iv-rest').value, 0, 600, 5),
        cycles: core.clampInt($('iv-cycles').value, 0, 99, 4)
      };
      saveSettings();
      tick();
    }
    $('iv-preset').addEventListener('change', function () { saveIv(true); });
    ['iv-work', 'iv-rest', 'iv-cycles'].forEach(function (id) { $(id).addEventListener('input', function () { saveIv(false); }); });

    Array.prototype.forEach.call(doc.querySelectorAll('[data-book]'), function (b) {
      b.addEventListener('click', function () { startBooking(parseInt(b.getAttribute('data-book'), 10)); });
    });
    $('book-pre').addEventListener('input', function () {
      settings.bookPre = core.clampInt($('book-pre').value, 0, 120, 10);
      saveSettings();
    });

    $('opt-pre').addEventListener('change', function () { settings.preOn = this.checked; saveSettings(); });
    $('opt-pre-min').addEventListener('input', function () { settings.preMin = core.clampInt(this.value, 1, 999, 5); saveSettings(); });
    $('opt-sound').addEventListener('change', function () { settings.sound = this.value; saveSettings(); });
    $('opt-repeat').addEventListener('input', function () { settings.repeat = core.clampInt(this.value, 1, 5, 2); saveSettings(); });
    $('opt-volume').addEventListener('input', function () {
      settings.volume = core.clampInt(this.value, 0, 100, 70);
      if (master) master.gain.value = volGain();
      saveSettings();
    });
    $('opt-test').addEventListener('click', function () {
      ensureAudio();
      if (!ctx) return;
      var go = function () { playCue('test', ctx.currentTime + 0.02); };
      if (ctx.state === 'running') go();
      else if (ctx.resume) ctx.resume().then(go, function () {});
    });
    $('opt-wake').addEventListener('change', function () { settings.wake = this.checked; saveSettings(); syncWake(); });
    $('opt-notify').addEventListener('change', function () {
      var box = this;
      if (!box.checked) { settings.notify = false; saveSettings(); showHint(''); return; }
      var done = function (perm) {
        if (perm === 'granted') { settings.notify = true; showHint(''); }
        else { box.checked = false; settings.notify = false; showHint(tr('notify_denied')); }
        saveSettings();
      };
      if (!('Notification' in window)) { done('denied'); return; }
      if (Notification.permission === 'granted') { done('granted'); return; }
      if (Notification.permission === 'denied') { done('denied'); return; }
      var settled = false;
      var cb = function (p) { if (!settled) { settled = true; done(p); } };
      try {
        var res = Notification.requestPermission(cb);       // 사용자가 체크박스를 누른 이 클릭 안에서만 요청
        if (res && res.then) res.then(cb, function () { cb('denied'); });
      } catch (e) { cb('denied'); }
    });

    doc.addEventListener('visibilitychange', function () {
      if (!doc.hidden) syncWake();
      tick();
    });
    window.addEventListener('pagehide', function () { persistRun(); });

    // 소리 잠금: 사용자가 화면을 한 번 건드리면 오디오를 깨워 둔다(복원된 진행에 필요).
    var unlock = function () {
      ensureAudio();
      if (audioReady()) { showHint(''); }
      scheduleAhead(Date.now());
    };
    doc.addEventListener('pointerdown', unlock, {passive: true});
    doc.addEventListener('keydown', unlock);
  }

  /* ---------- 시작 ---------- */
  function init() {
    // 지원하지 않는 기능의 옵션은 보이지 않게
    if (!navigator.wakeLock) setHidden($('opt-wake-row'), true);
    if (!('Notification' in window)) setHidden($('opt-notify-row'), true);
    if (!(root.requestFullscreen || root.webkitRequestFullscreen)) setHidden(el.full, true);
    if (!(window.AudioContext || window.webkitAudioContext)) setHidden($('opt-audio-box'), true);

    fillInputs();
    var now = Date.now();
    run = core.sanitizeRun(store.get(KEY_RUN), now);
    if (run) {
      sel = run.mode;
      settings.mode = sel;
      cursor = now;
      persistRun();
      showHint(tr('restored') + (run.status === 'running' || run.mode === 'range' ? ' ' + tr('tap_for_sound') : ''));
    } else {
      store.del(KEY_RUN);
    }
    bind();
    selectMode(sel, false);
    syncWake();
  }
  init();
})();
