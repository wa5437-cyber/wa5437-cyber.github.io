## 앱 상세 작성 공통 지침 (T6~T15 가 모두 따른다; 위 `_TEMPLATE.md` 의 내용)

한 앱 = 한 작업. **수정 허용 범위는 아래 두 곳뿐**이다: `_src/content/apps/<slug>.json` 의 `detail` 키(그리고 `store` 는 `pull_store.py` 로만), `img/apps/<slug>/`. 다른 파일은 건드리지 않는다(앱끼리 병렬로 돌리므로). **커밋하지 말고** 끝나면 파일만 남긴다(컨트롤러가 검토 뒤 커밋).

1. 준비: `python3 _src/tools/pull_store.py <slug>` 를 먼저 실행해 `store`(ko/en 포함 공개 문구)를 받는다. 그 앱의 ko·en 스토어 설명이 **사실의 1차 출처**다. 2차 출처는 그 앱 프로젝트 문서(아래 표의 폴더)와 `~/.claude/projects/-Users-michaellee-Documents/memory/` 의 해당 메모.
2. `detail` 은 `apps/stage-sound.json` 의 `detail` 과 **같은 키·모양**으로 쓴다: `price`(선택), `lead`, `platforms`, `bullets`(ko/en 각 5개), `facts`(ko/en 각 3~4개), `hero_img`, `blocks`(3개; `img` 는 문자열 또는 `{"ko":…,"en":…}`, `alt`/`title`/`text` ko·en), `steps`(ko/en 각 3~5단계: `{"t","d"}`), `related`(실제로 `guides/<slug>.html` 이 존재하는 가이드 slug 만 0~3개). **`bullets` 에 ko·en 이 모두 있어야** 해당 언어 전체 구성 페이지가 만들어진다.
3. 사실 규칙: 가격 확인 못 하면 `price` 키를 **쓰지 않는다**. 오프라인/광고/AI/정확도 주장은 스토어 문구나 프로젝트 문서에 있을 때만. 정확도가 낮은 기능은 "참고용" 명시. 지어낸 수치·후기 금지. 출시 전·심사 중인 기능은 쓰지 않는다(`pull_store` 가 공개 문구만 줘서 대체로 안전하지만, 프로젝트 문서에서 가져올 때 주의).
4. 화면 캡처: 아래 표의 폴더에서 그 앱의 **iPhone 한국어 세트와 영어 세트**를 찾아 `Read` 로 직접 보고(이미지를 눈으로 확인) 대표 1장 + 기능 블록 3장을 고른다. 한국어 화면은 `…_ko.jpg`, 영어 화면은 `…_en.jpg` 로 `python3 _src/tools/prep_shot.py <원본> img/apps/<slug>/<이름>_<lang>.jpg` 로 만든다(파일 이름은 영문 소문자·숫자·밑줄만). 영어 세트가 없으면 `hero_img`/`img` 를 문자열 하나로 쓰고 ko 이미지를 공용으로 쓴다(보고서에 적는다). 실존 앨범 커버·타 브랜드 로고가 보이는 캡처는 피한다. 이미지 합계는 앱당 약 1MB 이하.
5. 글쓰기 문체: ko 는 존댓말 "~합니다/~할 수 있습니다", 짧은 문장, 마케팅 과장 금지("최고", "혁신" 등 금지). en 은 평이한 현재형. 블록 `title` 은 한 줄, `text` 는 1~2문장. 제목·문장은 공백으로 끊어 읽기 좋게(한글 낱말이 한 줄에 쪼개져도 CSS 가 막아 주지만 지나치게 긴 낱말은 피함).
6. 마무리 점검(직접 실행해 결과를 보고서에 붙인다): `python3 -m unittest discover -s _src/tests` 통과, `python3 _src/build.py`, `python3 _src/build.py --check | grep "✗" | grep -v -E "/(plugins|studio|about|privacy|contact)/"` 출력 없음, `ls img/apps/<slug>/` 에 JSON 이 참조하는 파일이 전부 있음.
7. 보고서(`.superpowers/sdd/<plan>/task-N-report.md`) 형식: Status / 쓴 파일 / 출처 표(주장별: 문구가 어디서 나왔는지) / 확인 못 해서 뺀 것 / 가져온 언어 목록 / 우려.

| slug | 프로젝트 폴더·캡처 위치(힌트) | 주의 |
|---|---|---|
| ear-trainer | `~/Documents/EarTrainer/`(`build/screenshots`, 맥은 `build/screenshots-mac`) | 앱 이름 AudioEngineer Ear Trainer. 이펙트 리스닝 탭 폐지·모의고사 모듈 최종 구조 반영(메모리 `eartrainer-drill-architecture-project`) |
| spl-rta | `~/Documents/SPL Meter & RTA/appstore/screenshots` | 소음원 AI·하울링은 "참고용"; 심사 중 1.2 기능은 쓰지 않음 |
| toolkit | `~/Documents/AudioEngineerToolkit/`(캡처 폴더는 직접 찾기), 스테이징 `~/Documents/localization-staging/Toolkit` | 4종 계산기(딜레이·음향·전기·템포/피치) |
| aet-quiz | `~/Documents/localization-staging/AETQuiz/shots`, 프로젝트 폴더는 메모리 `audio-engineer-toolkit-project` | 무료 앱 |
| keymap | `~/Documents/DAWShortcuts/screenshots`, `fastlane/screenshots` | 이름 "DAW 단축키 — KeyMap". **키 눌러 찾기 기능은 미출시이므로 쓰지 않는다** |
| patchio | `~/Documents/PatchIO/store/screenshots`(맥은 `screenshots-flat-mac`) | `legal` = `/patchio_legal.html` |
| nora | `~/Documents/커버곡 프로젝트/nora-electron`, `~/Documents/NORA` | **먼저 확인**: ASC 에서 공개(READY_FOR_SALE)된 상태인가? 아니면(리젝/준비 중) 이 작업을 중단하고 보고만 한다 |
| yul | `~/Documents/GugakTuner/build/screenshots` | ko/en/ja 문구가 있을 것. 국악 용어는 스토어 문구 그대로 |
| sheetscope | `~/Documents/SheetScope/`, 스테이징 `SheetScope` | 변환 정확도는 "참고용"(악보 인식) |
| temposcope | `~/Documents/TempoScope/build/screenshots`, 엔진 `~/Documents/mae/` | 템포·키·코드 감지는 "참고용"; 1.4(녹음→MIDI)는 공개 전이면 쓰지 않음 |
