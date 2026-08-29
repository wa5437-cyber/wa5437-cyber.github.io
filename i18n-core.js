/*!
 * Shared i18n engine for Sound Engineer Tools pages.
 * Each page defines `window.I18N_DATA = {...}` (translation dictionary)
 * BEFORE including this script, then optionally reads `window.i18n.t(key)`
 * inside its own JS for dynamically-generated text.
 *
 * Usage in HTML:
 *   <div id="langSwitchMount"></div>   <!-- anywhere in the nav/topbar -->
 *   ...
 *   <script>window.I18N_DATA = { key: {ko:"...", en:"...", ja:"...", es:"...", zh:"..."}, ... };</script>
 *   <script src="i18n-core.js"></script>
 */
(function(){
  "use strict";

  var SUPPORTED_LANGS = ["ko","en","ja","es","zh"];
  var LANG_LABELS = { ko:"한국어", en:"English", ja:"日本語", es:"Español", zh:"简体中文" };
  var LANG_FLAGS  = { ko:"🇰🇷", en:"🇺🇸", ja:"🇯🇵", es:"🇪🇸", zh:"🇨🇳" };

  function currentLang(){ return window.i18n ? window.i18n.lang : "ko"; }

  function t(key){
    var data = window.I18N_DATA || {};
    var entry = data[key];
    if (!entry) return key;
    return entry[currentLang()] || entry.ko || key;
  }

  function tpl(key, vars){
    var s = t(key);
    if (vars) {
      Object.keys(vars).forEach(function(k){
        s = s.split('{' + k + '}').join(vars[k]);
      });
    }
    return s;
  }

  function applyLang(lang){
    if (SUPPORTED_LANGS.indexOf(lang) === -1) lang = "ko";
    window.i18n = window.i18n || {};
    window.i18n.lang = lang;
    window.i18n.t = t;
    window.i18n.tpl = tpl;

    document.documentElement.lang = (lang === "zh" ? "zh-Hans" : lang);

    var data = window.I18N_DATA || {};
    var nodes = document.querySelectorAll('[data-i18n]');
    for (var i=0; i<nodes.length; i++){
      var el = nodes[i];
      var key = el.getAttribute('data-i18n');
      var entry = data[key];
      if (!entry) continue;
      var val = entry[lang] || entry.ko;
      if (val == null) continue;
      if (el.hasAttribute('data-i18n-html')) el.innerHTML = val;
      else if (el.hasAttribute('data-i18n-placeholder')) el.setAttribute('placeholder', val);
      else el.textContent = val;
    }

    var langBtns = document.querySelectorAll('[data-lang-btn]');
    for (var j=0; j<langBtns.length; j++){
      langBtns[j].classList.toggle('active', langBtns[j].getAttribute('data-lang-btn') === lang);
    }
    var label = document.getElementById('langSwitchLabel');
    if (label) label.textContent = LANG_LABELS[lang];

    try { localStorage.setItem('siteLang', lang); } catch(e) {}

    document.dispatchEvent(new CustomEvent('i18nchange', { detail: { lang: lang } }));
  }

  function detectLang(){
    try {
      var saved = localStorage.getItem('siteLang');
      if (saved && SUPPORTED_LANGS.indexOf(saved) !== -1) return saved;
    } catch(e) {}
    var nav = ((navigator.language || navigator.userLanguage || 'ko') + '').toLowerCase();
    if (nav.indexOf('ko') === 0) return 'ko';
    if (nav.indexOf('ja') === 0) return 'ja';
    if (nav.indexOf('es') === 0) return 'es';
    if (nav.indexOf('zh') === 0) return 'zh';
    if (nav.indexOf('en') === 0) return 'en';
    return 'ko';
  }

  function buildSwitcher(mount){
    mount.classList.add('lang-switch');
    var html = '';
    html += '<button class="lang-switch-btn" id="langSwitchBtn" type="button" aria-haspopup="true" aria-expanded="false">🌐 <span id="langSwitchLabel">한국어</span> ▾</button>';
    html += '<div class="lang-switch-menu" id="langSwitchMenu">';
    SUPPORTED_LANGS.forEach(function(l){
      html += '<button type="button" data-lang-btn="' + l + '">' + LANG_FLAGS[l] + ' ' + LANG_LABELS[l] + '</button>';
    });
    html += '</div>';
    mount.innerHTML = html;

    var btn = document.getElementById('langSwitchBtn');
    var menu = document.getElementById('langSwitchMenu');
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      var open = menu.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('click', function(e){
      if (!menu.contains(e.target) && e.target !== btn) {
        menu.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
      }
    });
    var langBtns = menu.querySelectorAll('[data-lang-btn]');
    for (var i=0; i<langBtns.length; i++){
      langBtns[i].addEventListener('click', function(ev){
        applyLang(ev.currentTarget.getAttribute('data-lang-btn'));
        menu.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    var mount = document.getElementById('langSwitchMount');
    if (mount) buildSwitcher(mount);
    applyLang(detectLang());
  });

  window.i18n = { lang: 'ko', t: t, tpl: tpl, apply: applyLang };
})();
