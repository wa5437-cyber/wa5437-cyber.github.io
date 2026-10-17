/* 메트로놈 화면 로직. 박 계산·탭 템포·가속 연습은 metronome-core.js, 문자열은 페이지가 내려 준 #i18n 사전을 쓴다.
   소리는 setTimeout(25ms) 룩어헤드 스케줄러가 AudioContext 시계로 미리 예약한다(setInterval 로 직접 울리지 않는다).
   서버로 아무것도 보내지 않는다. 설정은 이 기기의 localStorage 에만 저장한다. */
(function () {
  'use strict';
  var core = window.MetronomeCore;
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

  var KEY = 'mlms.metronome.settings.v1';
  var store = {
    get: function (k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* 저장 불가: 무시 */ } }
  };
  var settings = core.sanitizeSettings(store.get(KEY));
  function save() { store.set(KEY, settings); }

  var LOOK = 0.1, LOOK_HIDDEN = 1.5, POLL = 25;

  var el = {
    bpm: $('bpm'), range: $('bpm-range'), down: $('bpm-down'), up: $('bpm-up'), term: $('term'), leds: $('leds'),
    bar: $('bar-count'), main: $('btn-main'), tap: $('btn-tap'), tapInfo: $('tap-info'), sig: $('sig'),
    customWrap: $('sig-custom-wrap'), custom: $('sig-custom'), sub: $('sub'), accent: $('opt-accent'),
    sound: $('sound'), volume: $('volume'),
    trOn: $('tr-on'), trStart: $('tr-start'), trTarget: $('tr-target'), trEvery: $('tr-every'), trStep: $('tr-step'),
    trNote: $('tr-note'), prMin: $('pr-min'), prLeft: $('pr-left'), wake: $('opt-wake'), wakeRow: $('opt-wake-row'),
    sr: $('sr-live'), hint: $('hint'), card: $('display-card')
  };

  /* ---------- 상태 ---------- */
  var ctx = null, master = null;
  var sch = null, running = false, pollId = null, rafId = null, practiceId = null;
  var live = [];              // 예약한 소리 노드 {osc, gain, time}
  var visual = [];            // 화면에 표시할 박 {time,...}
  var liveBpm = settings.bpm;
  var practiceEnd = 0, practiceCut = false;
  var tapState = {taps: []}, tapTimer = null;
  var ledNodes = [];

  function meter() { return core.meterFor(settings.sig, settings.customBeats); }
  function trainerOn() { return settings.trainer.on; }
  function trainerLocked() { return running && trainerOn(); }

  function setText(node, txt) { if (node && node.textContent !== txt) node.textContent = txt; }
  function setHidden(node, hide) { if (node && node.hidden !== hide) node.hidden = hide; }
  function announce(msg) {
    el.sr.textContent = '';
    setTimeout(function () { el.sr.textContent = msg; }, 60);
  }
  function showHint(msg) { setText(el.hint, msg || ''); setHidden(el.hint, !msg); }

  /* ---------- 소리 합성 ---------- */
  function volGain() { var v = settings.volume / 100; return v * v; }
  function ensureAudio() {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    if (!ctx) {
      try {
        ctx = new AC({latencyHint: 'interactive'});
        master = ctx.createGain();
        master.gain.value = volGain();
        master.connect(ctx.destination);
      } catch (e) {
        try { ctx = new AC(); master = ctx.createGain(); master.gain.value = volGain(); master.connect(ctx.destination); }
        catch (e2) { ctx = null; return null; }
      }
    }
    if (ctx.state === 'suspended') { try { ctx.resume(); } catch (e3) { /* 무시 */ } }
    return ctx;
  }

  var PITCH = {
    click: {strong: 2200, medium: 1800, weak: 1450, sub: 1100},
    wood: {strong: 1150, medium: 980, weak: 820, sub: 660},
    beep: {strong: 1320, medium: 1100, weak: 880, sub: 660}
  };
  var LEVEL = {strong: 1, medium: 0.8, weak: 0.66, sub: 0.38};

  function env(g, when, peak, attack, decay) {
    g.gain.setValueAtTime(0.0001, when);
    g.gain.linearRampToValueAtTime(peak, when + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, when + attack + decay);
  }

  function playTick(t) {
    var kind = settings.sound, f = PITCH[kind][t.accent], lvl = LEVEL[t.accent], when = t.time;
    var o = ctx.createOscillator(), g = ctx.createGain(), end;
    if (kind === 'click') {
      o.type = 'square';
      env(g, when, 0.5 * lvl, 0.0008, 0.022);
      end = when + 0.04;
    } else if (kind === 'wood') {
      o.type = 'sine';
      o.frequency.setValueAtTime(f * 1.15, when);
      o.frequency.exponentialRampToValueAtTime(f, when + 0.012);
      env(g, when, 0.95 * lvl, 0.001, 0.07);
      end = when + 0.1;
      var o2 = ctx.createOscillator(), g2 = ctx.createGain();     // 나무 울림의 2배음
      o2.type = 'triangle';
      o2.frequency.value = f * 2.4;
      env(g2, when, 0.25 * lvl, 0.001, 0.03);
      o2.connect(g2);
      g2.connect(master);
      o2.start(when);
      o2.stop(when + 0.06);
      live.push({osc: o2, gain: g2, time: when});
    } else {
      o.type = 'sine';
      env(g, when, 0.8 * lvl, 0.004, 0.07);
      end = when + 0.1;
    }
    if (kind !== 'wood') o.frequency.value = f;
    o.connect(g);
    g.connect(master);
    o.start(when);
    o.stop(end);
    live.push({osc: o, gain: g, time: when});
  }

  function pruneLive() {
    var now = ctx ? ctx.currentTime : 0;
    live = live.filter(function (n) { return n.time + 0.2 > now; });
  }
  function cancelFuture() {
    var now = ctx ? ctx.currentTime : 0;
    live.forEach(function (n) {
      if (n.time > now) {
        try { n.osc.stop(0); } catch (e) { /* 이미 끝남 */ }
        try { n.gain.disconnect(); } catch (e2) { /* 무시 */ }
      }
    });
    live = [];
  }

  function playEndCue() {
    if (!ctx || ctx.state !== 'running') return;
    var t0 = ctx.currentTime + 0.05, notes = [[784, 0], [988, 0.18], [1175, 0.36], [1568, 0.6]];
    notes.forEach(function (n) {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'sine';
      o.frequency.value = n[0];
      env(g, t0 + n[1], 0.6, 0.01, n[1] > 0.5 ? 0.9 : 0.25);
      o.connect(g);
      g.connect(master);
      o.start(t0 + n[1]);
      o.stop(t0 + n[1] + 1.1);
    });
  }

  /* ---------- 스케줄러 루프 ---------- */
  function poll() {
    if (!running) return;
    var now = ctx.currentTime;
    if (practiceEnd && Date.now() >= practiceEnd) { stop(true); return; }
    var ticks = sch.collect(now + (doc.hidden ? LOOK_HIDDEN : LOOK));
    var wall = Date.now();
    for (var i = 0; i < ticks.length; i++) {
      var t = ticks[i];
      if (practiceEnd && core.tickWallMs(t.time, now, wall) >= practiceEnd) { practiceCut = true; continue; }
      if (t.time < now - 0.05) continue;                // 너무 늦은 박(탭이 멈췄다 돌아온 경우)은 건너뜀
      playTick(t);
      if (!doc.hidden) visual.push(t);
    }
    if (doc.hidden) visual.length = 0;
    pruneLive();
    pollId = setTimeout(poll, POLL);
  }

  function visualLoop() {
    if (!running) return;
    var now = ctx.currentTime - (ctx.outputLatency || ctx.baseLatency || 0);
    while (visual.length && visual[0].time <= now) {
      var t = visual.shift();
      if (t.sub === 0) flash(t);
    }
    rafId = requestAnimationFrame(visualLoop);
  }

  function flash(t) {
    for (var i = 0; i < ledNodes.length; i++) {
      ledNodes[i].classList.remove('on', 'on-strong');
    }
    var led = ledNodes[t.beat];
    if (led) led.classList.add(t.accent === 'strong' ? 'on-strong' : 'on');
    setText(el.bar, tr('bar_n', {n: t.bar + 1}));
    if (t.bpm !== liveBpm) { liveBpm = t.bpm; showBpm(liveBpm, true); }
  }

  /* ---------- BPM ---------- */
  function showBpm(v, fromTrainer) {
    if (doc.activeElement !== el.bpm || fromTrainer) el.bpm.value = v;
    el.range.value = v;
    var id = core.termForBpm(v);
    setText(el.term, id.charAt(0).toUpperCase() + id.slice(1) + ' · ' + tr('term_' + id));
  }

  function setBpm(v) {
    if (trainerLocked()) return;
    var b = core.clampBpm(v, settings.bpm);
    settings.bpm = b;
    liveBpm = b;
    showBpm(b);
    if (sch) sch.setBpm(b);
    save();
  }

  /* ---------- 박 표시 ---------- */
  function buildLeds() {
    var m = meter();
    el.leds.textContent = '';
    ledNodes = [];
    for (var i = 0; i < m.beats; i++) {
      var s = doc.createElement('span');
      s.className = 'led' + (m.accents[i] === 2 ? ' first' : m.accents[i] === 1 ? ' mid' : '');
      el.leds.appendChild(s);
      ledNodes.push(s);
    }
  }

  /* ---------- 시작·정지 ---------- */
  function start() {
    if (!ensureAudio()) { showHint(tr('no_audio')); return; }
    var go = function () {
      if (running) return;
      var tr0 = core.normalizeTrainer(settings.trainer);
      liveBpm = trainerOn() ? tr0.start : settings.bpm;
      showBpm(liveBpm, true);
      sch = new core.Scheduler({
        startTime: ctx.currentTime + 0.08, bpm: liveBpm, meter: meter(), sub: settings.sub,
        accentOn: settings.accent, trainer: trainerOn() ? tr0 : null
      });
      practiceEnd = settings.practiceMin > 0 ? Date.now() + settings.practiceMin * 60000 : 0;
      practiceCut = false;
      running = true;
      visual = [];
      showHint('');
      renderState();
      announce(tr('sr_started'));
      syncWake();
      poll();
      rafId = requestAnimationFrame(visualLoop);
      if (practiceEnd) { practiceId = setInterval(updatePractice, 250); updatePractice(); }
    };
    if (ctx.state === 'running') go();
    else if (ctx.resume) ctx.resume().then(go, function () { showHint(tr('no_audio')); });
    else go();
  }

  function stop(byPractice) {
    if (!running) return;
    running = false;
    clearTimeout(pollId);
    if (rafId) cancelAnimationFrame(rafId);
    if (practiceId) { clearInterval(practiceId); practiceId = null; }
    cancelFuture();
    sch = null;
    visual = [];
    practiceEnd = 0;
    for (var i = 0; i < ledNodes.length; i++) ledNodes[i].classList.remove('on', 'on-strong');
    liveBpm = settings.bpm;
    showBpm(settings.bpm, true);
    setText(el.bar, '');
    setText(el.prLeft, '');
    setHidden(el.prLeft, true);
    renderState();
    syncWake();
    if (byPractice) {
      playEndCue();
      announce(tr('practice_done'));
      showHint(tr('practice_done'));
    } else {
      announce(tr('sr_stopped'));
    }
  }

  function toggle() { if (running) stop(false); else start(); }

  function updatePractice() {
    if (!practiceEnd) return;
    var left = core.practiceRemaining(practiceEnd, Date.now());
    var secs = Math.ceil(left / 1000), m = Math.floor(secs / 60), s = secs % 60;
    setHidden(el.prLeft, false);
    setText(el.prLeft, tr('practice_left', {t: (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s}));
  }

  function renderState() {
    setText(el.main, tr(running ? 'btn_stop' : 'btn_start'));
    el.main.setAttribute('aria-pressed', running ? 'true' : 'false');
    el.card.setAttribute('data-state', running ? 'running' : 'idle');
    var lock = trainerLocked();
    [el.bpm, el.range, el.down, el.up, el.tap].forEach(function (n) { if (n.disabled !== lock) n.disabled = lock; });
    [el.trOn, el.trStart, el.trTarget, el.trEvery, el.trStep, el.prMin].forEach(function (n) {
      var d = running; if (n.disabled !== d) n.disabled = d;
    });
    var tn = settings.trainer;
    setText(el.trNote, trainerOn() ? tr('trainer_note', {every: tn.every, step: tn.step, start: tn.start, target: tn.target}) : '');
    setHidden(el.trNote, !trainerOn());
  }

  /* ---------- 탭 템포 ---------- */
  function doTap() {
    var res = core.tapTempo(tapState, performance.now());
    tapState = {taps: res.taps};
    setText(el.tapInfo, tr('tap_count', {n: res.taps.length}));
    setHidden(el.tapInfo, false);
    clearTimeout(tapTimer);
    tapTimer = setTimeout(function () { setHidden(el.tapInfo, true); }, 2000);
    if (res.bpm !== null) setBpm(res.bpm);
  }

  /* ---------- 화면 꺼짐 방지 ---------- */
  var wakeLock = null, wakePending = false;
  function syncWake() {
    if (!navigator.wakeLock) return;
    var want = settings.wake && running && !doc.hidden;
    if (want && !wakeLock && !wakePending) {
      wakePending = true;
      navigator.wakeLock.request('screen').then(function (l) {
        wakePending = false;
        wakeLock = l;
        l.addEventListener('release', function () { if (wakeLock === l) wakeLock = null; });
        if (!settings.wake || !running) { try { l.release(); } catch (e) { /* 무시 */ } wakeLock = null; }
      }).catch(function () { wakePending = false; });
    } else if (!want && wakeLock) {
      try { wakeLock.release(); } catch (e) { /* 무시 */ }
      wakeLock = null;
    }
  }

  /* ---------- 입력 연결 ---------- */
  function fillInputs() {
    el.bpm.value = settings.bpm;
    el.range.value = settings.bpm;
    el.sig.value = settings.sig;
    el.custom.value = settings.customBeats;
    el.sub.value = settings.sub;
    el.accent.checked = settings.accent;
    el.sound.value = settings.sound;
    el.volume.value = settings.volume;
    el.trOn.checked = settings.trainer.on;
    el.trStart.value = settings.trainer.start;
    el.trTarget.value = settings.trainer.target;
    el.trEvery.value = settings.trainer.every;
    el.trStep.value = settings.trainer.step;
    el.prMin.value = settings.practiceMin;
    el.wake.checked = settings.wake;
    setHidden(el.customWrap, settings.sig !== 'custom');
  }

  function readTrainer() {
    settings.trainer = core.normalizeTrainer({
      on: el.trOn.checked, start: el.trStart.value, target: el.trTarget.value, every: el.trEvery.value, step: el.trStep.value
    });
    save();
    renderState();
  }

  function bind() {
    el.main.addEventListener('click', toggle);
    el.tap.addEventListener('click', doTap);
    el.down.addEventListener('click', function (e) { setBpm(settings.bpm - (e.shiftKey ? 5 : 1)); });
    el.up.addEventListener('click', function (e) { setBpm(settings.bpm + (e.shiftKey ? 5 : 1)); });

    el.bpm.addEventListener('input', function () {
      var n = parseInt(el.bpm.value, 10);
      if (n >= core.BPM_MIN && n <= core.BPM_MAX && !trainerLocked()) {
        settings.bpm = n;
        liveBpm = n;
        el.range.value = n;
        var id = core.termForBpm(n);
        setText(el.term, id.charAt(0).toUpperCase() + id.slice(1) + ' · ' + tr('term_' + id));
        if (sch) sch.setBpm(n);
        save();
      }
    });
    el.bpm.addEventListener('change', function () { setBpm(el.bpm.value); el.bpm.value = settings.bpm; });
    el.bpm.addEventListener('keydown', function (e) {
      if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && e.shiftKey) {
        e.preventDefault();
        setBpm(settings.bpm + (e.key === 'ArrowUp' ? 5 : -5));
        el.bpm.value = settings.bpm;
      }
    });
    el.bpm.addEventListener('wheel', function (e) {
      if (doc.activeElement !== el.bpm) return;          // 포커스가 있을 때만(페이지 스크롤을 가로채지 않는다)
      e.preventDefault();
      setBpm(settings.bpm + (e.deltaY < 0 ? 1 : -1) * (e.shiftKey ? 5 : 1));
    }, {passive: false});
    el.range.addEventListener('input', function () { setBpm(el.range.value); });

    el.sig.addEventListener('change', function () {
      settings.sig = el.sig.value;
      setHidden(el.customWrap, settings.sig !== 'custom');
      applyMeter();
    });
    el.custom.addEventListener('input', function () {
      settings.customBeats = core.clampInt(el.custom.value, 1, 16, 5);
      applyMeter();
    });
    el.sub.addEventListener('change', function () { settings.sub = el.sub.value; if (sch) sch.setSub(settings.sub); save(); });
    el.accent.addEventListener('change', function () { settings.accent = el.accent.checked; if (sch) sch.accentOn = settings.accent; save(); });
    el.sound.addEventListener('change', function () { settings.sound = el.sound.value; save(); preview(); });
    el.volume.addEventListener('input', function () {
      settings.volume = core.clampInt(el.volume.value, 0, 100, 80);
      if (master) master.gain.value = volGain();
      save();
    });

    [el.trOn, el.trStart, el.trTarget, el.trEvery, el.trStep].forEach(function (n) {
      n.addEventListener('input', readTrainer);
      n.addEventListener('change', readTrainer);
    });
    el.prMin.addEventListener('input', function () { settings.practiceMin = core.clampInt(el.prMin.value, 0, 180, 0); save(); });
    el.wake.addEventListener('change', function () { settings.wake = el.wake.checked; save(); syncWake(); });

    doc.addEventListener('visibilitychange', function () { syncWake(); });

    doc.addEventListener('keydown', function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      var tg = e.target, tag = tg && tg.tagName;
      var textual = tag === 'TEXTAREA' || tag === 'SELECT' || (tag === 'INPUT' && tg.type !== 'range' && tg.type !== 'checkbox');
      if (textual) return;                                  // 입력칸 안에서는 기본 동작을 존중
      if (e.key === ' ' || e.code === 'Space') {
        if (tag === 'BUTTON' || tag === 'SUMMARY' || (tag === 'INPUT' && tg.type === 'checkbox')) return;   // 눌린 버튼이 알아서 처리
        e.preventDefault();
        toggle();
      } else if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && tag !== 'BUTTON' && !(tag === 'INPUT' && tg.type === 'range')) {
        e.preventDefault();
        setBpm(settings.bpm + (e.key === 'ArrowUp' ? 1 : -1) * (e.shiftKey ? 5 : 1));
      } else if (e.key === 't' || e.key === 'T') {
        if (trainerLocked()) return;
        e.preventDefault();
        doTap();
      }
    });
  }

  function applyMeter() {
    buildLeds();
    if (sch) sch.setMeter(meter());
    save();
  }

  function preview() {
    if (running) return;
    if (!ensureAudio()) return;
    var go = function () { var t = {time: ctx.currentTime + 0.02, accent: 'strong'}; playTick(t); };
    if (ctx.state === 'running') go();
  }

  function init() {
    if (!navigator.wakeLock) setHidden(el.wakeRow, true);
    fillInputs();
    buildLeds();
    showBpm(settings.bpm, true);
    renderState();
    bind();
  }
  init();
})();
