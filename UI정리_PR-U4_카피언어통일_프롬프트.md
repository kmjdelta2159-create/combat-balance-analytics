# PR-U4 — 카피/언어 통일 + 레이아웃 가독성 정리 (Step 1·2)

> 대상: `modules/step1_upload.py`, `modules/step2_system_definition.py`
> 성격: **카피(문구) + 표시조건/높이만**. 기능 로직·변수·session_state 키·반환값 불변.
> session_state 키 `attack_log_df`는 **그대로 유지**(표시 텍스트만 "무브 로그"로). 
> 검증: `ast.parse` 통과 + 앱 Step1/Step2 캡처.

---

## A. 카피 find→replace (제로 리스크 — 문자열만 교체)

### A-1. `modules/step1_upload.py`
| 현재 | 변경 |
|---|---|
| `st.file_uploader("Upload Combat Logs",` | `st.file_uploader("전투 로그 파일",` |
| `st.subheader("어택 로그 업로드 (선택)")` | `st.subheader("무브 로그 업로드 (선택)")` |
| `st.file_uploader("Attack Log",` | `st.file_uploader("무브 로그 파일",` |
| `st.success(f"✅ 어택 로그 파싱 완료! ({len(attack_df)}행, {len(attack_df.columns)}열)")` | `st.success(f"✅ 무브 로그 파싱 완료! ({len(attack_df)}행, {len(attack_df.columns)}열)")` |
| `with st.expander("어택 로그 미리보기", expanded=False):` | `with st.expander("무브 로그 미리보기", expanded=False):` |
| `st.error(f"❌ 어택 로그 파싱 오류: {e}")` | `st.error(f"❌ 무브 로그 파싱 오류: {e}")` |
| `st.caption(f"📦 세션에 저장된 어택 로그 ({len(_atk)}행) 사용 중")` | `st.caption(f"📦 세션에 저장된 무브 로그 ({len(_atk)}행) 사용 중")` |
| `st.subheader("또는 이전 맵핑 프리셋(JSON) 불러오기")` | `st.subheader("저장한 매핑 불러오기 (선택)")` |
| `st.file_uploader(\n        "Upload Mapping Preset (JSON)",` | `st.file_uploader(\n        "매핑 프리셋 파일 (JSON)",` |

(info 문구 "📌 무브 단위 데이터가 있는 경우 업로드하세요…"는 이미 적절 — 유지.)

### A-2. `modules/step2_system_definition.py`
| 현재 | 변경 |
|---|---|
| `st.markdown("## 🔍 Data Mapping & Live Formula Validator")` | `st.markdown("## 🔍 데이터 매핑 & 공식 검증")` |
| `st.markdown("#### 1. 🎯 Target Variable (승패 결과)")` | `st.markdown("#### 1. 🎯 타깃 변수 (승패 결과)")` |
| `st.markdown("#### 2. 📊 Base Stats & Gimmicks")` | `st.markdown("#### 2. 📊 기본 스탯 & 기믹")` |
| `st.markdown("#### 2-1. 🛡️ Auto-Imputation (결측치 방어)")` | `st.markdown("#### 2-1. 🛡️ 결측치 채우기")` |
| `st.markdown("#### 3. ⚔️ Live Formula Validator")` | `st.markdown("#### 3. ⚔️ 공식 검증기")` |
| `st.caption(f"📦 Step 1에서 업로드된 attack_log ({len(attack_log_df)}행) 사용 중")` | `st.caption(f"📦 Step 1에서 업로드된 무브 로그 ({len(attack_log_df)}행) 사용 중")` |
| `st.caption("ℹ️ attack_log 없음 — Step 1에서 어택 로그를 업로드하면 무브 분석이 활성화됩니다.")` | `st.caption("ℹ️ 무브 로그 없음 — Step 1에서 무브 로그를 업로드하면 무브 분석이 활성화됩니다.")` |
| `st.info("📎 메인 로그에 무브 컬럼이 없어 attack_log에서 추출합니다.")` | `st.info("📎 메인 로그에 무브 컬럼이 없어 무브 로그에서 추출합니다.")` |
| `st.markdown("#### 🔯 타입 상성표 (Type Effectiveness)")` | `st.markdown("#### 🔯 타입 상성표")` |
| `st.success("✅ System Definition 완료! 백그라운드에서 AI 데이터 전처리 및 ML 파이프라인 연산이 수행되었습니다.")` | `st.success("✅ 시스템 정의 완료! 전투 데이터 전처리와 승률 예측 모델 학습을 마쳤습니다.")` |
| `st.success("✅ 로지스틱 회귀 및 앙상블 모델 기반 심층 분석이 완료되었습니다!")` | `st.success("✅ 승률 예측 모델 학습이 완료되었습니다!")` |

> 위 표의 "현재" 문자열은 Read로 정확히 대조 후 교체. 줄바꿈이 있는 file_uploader는 첫 인자
> 문자열만 바꾸면 된다.

---

## B. 타입 상성표 — 화면 압도 완화 (저위험, 표시만)

대상: `step2_system_definition.py` 타입 상성표 블록(현 L387~392).
타입표는 이미 Move System expander **안**이라 expander로 또 감쌀 수 없다(중첩 위반).
대신 (1) data_editor 높이 고정으로 스크롤 박스화, (2) 카피 완화.

### B-1. data_editor 높이 고정
현재:
```python
            move_type_table_edited = st.data_editor(
                _tt_init, use_container_width=True, key="ui_type_table_editor")
```
변경(파라미터 `height=320` 추가만):
```python
            move_type_table_edited = st.data_editor(
                _tt_init, use_container_width=True, height=320, key="ui_type_table_editor")
```

### B-2. 카피 완화 (겁주지 않게)
현재:
```python
                st.caption(f"{len(_type_roster)}개 타입 — 공격(행) × 방어(열) 배율표. "
                           f"기본 1.0(무영향) · 효과적 2.0 · 반감 0.5 · 무효 0.0. "
                           f"게임의 상성표는 전문가가 직접 입력합니다.")
```
변경:
```python
                st.caption(f"{len(_type_roster)}개 타입 — 공격(행) × 방어(열) 배율표. "
                           f"기본값 1.0(무영향)이니 **효과적(2.0)·반감(0.5)·무효(0.0)인 칸만** "
                           f"바꾸면 됩니다.")
```

---

## C. 데미지 공식 자동 추정 — 안 되는 데이터일 때 숨김 (중위험·들여쓰기 주의)

대상: Symbolic Regression 블록(현 L262~298). 현재 데미지 컬럼이 없으면 헤더 + "자동 추측
불가" 안내만 항상 노출된다 → 안 되는 기능을 상시 노출. **데미지 컬럼이 감지될 때만** 이 섹션을
렌더한다.

### 변경 명세
1. 검출을 헤더 **앞**으로 올리고, 사용 가능할 때만 전체 블록을 렌더하는 가드로 감싼다.
2. "gplearn 미설치"·"자동 추측 불가" 두 caption(현 L272·L274)은 **제거**(불필요한 노이즈).

현재(요지):
```python
                # ── Phase 7: 데미지 공식 자동 추측 (Symbolic Regression) ──
                st.markdown("##### 🔮 데미지 공식 자동 추측 (Symbolic Regression)")

                def _sr_apply(_formula):
                    ...
                _sr_dmg_col = detect_damage_column(df, base_stats, selected_target)
                if not gplearn_available():
                    st.caption("⚠️ gplearn 미설치 — ...")
                elif _sr_dmg_col is None:
                    st.caption("로그에 데미지(연속 숫자) 컬럼이 없어 자동 추측 불가 — ...")
                else:
                    st.caption(f"데미지 컬럼 `{_sr_dmg_col}` 감지 — ...")
                    if st.button("🔮 공식 자동 추측 실행", ...):
                        ...
                    _sr_cands = st.session_state.get('sr_candidates')
                    if _sr_cands:
                        ...
                    elif _sr_cands == []:
                        st.info("공식 후보를 찾지 못했습니다 ...")
```
변경 후(요지):
```python
                # ── Phase 7: 데미지 공식 자동 추정 — 데미지 컬럼 있을 때만 노출 ──
                _sr_dmg_col = detect_damage_column(df, base_stats, selected_target)
                if gplearn_available() and _sr_dmg_col is not None:
                    st.markdown("##### 🔮 데미지 공식 자동 추정")

                    def _sr_apply(_formula):
                        ...
                    st.caption(f"데미지 컬럼 `{_sr_dmg_col}` 감지 — 기호 회귀로 공식 후보를 추정합니다.")
                    if st.button("🔮 공식 자동 추정 실행", use_container_width=True, key="sr_run_btn"):
                        ...
                    _sr_cands = st.session_state.get('sr_candidates')
                    if _sr_cands:
                        ...
                    elif _sr_cands == []:
                        st.info("공식 후보를 찾지 못했습니다 (데이터 부족 또는 적합 실패).")
                # 데미지 컬럼 없으면 섹션 자체를 숨김(위 공식 검증기로 직접 입력).
```
- 즉 기존 `if not gplearn_available()/elif/else` 3분기를 **단일 가드 `if gplearn_available()
  and _sr_dmg_col is not None:`** 로 바꾸고, `else` 본문(L276~298)을 그 가드 안으로 한 단계
  들여 옮긴다. `_sr_apply` def·button·결과 표시 로직은 **그대로**(문구의 "추측"→"추정"만).

### 안전 대안 (들여쓰기 확신 안 서면)
C가 부담되면 **C는 생략**하고, 최소한 헤더·문구만 바꿔라(B·A는 그대로 진행):
`st.markdown("##### 🔮 데미지 공식 자동 추정 (Symbolic Regression)")` → 영어 빼고
`"##### 🔮 데미지 공식 자동 추정"`, "자동 추측 불가" → "자동 추정 불가". 숨김은 다음 PR로.

---

## D. 절대 건드리지 말 것 (회귀0)
- 데이터 매핑·공식 검증·무브 추출·타입표 캡처(`move_type_table_edited`)·승인 버튼·ML 학습 로직.
- session_state 키(`attack_log_df` 등) — 표시 텍스트만 변경.
- 동적 메커니즘·채널 매핑·실행 순서 로직.

---

## E. 검증
1. `python -c "import ast; ast.parse(open('modules/step1_upload.py').read()); ast.parse(open('modules/step2_system_definition.py').read())"` — 둘 다 통과.
2. `streamlit run main.py`:
   - Step1: "무브 로그 업로드 (선택)"·한국어 업로더 라벨·"저장한 매핑 불러오기 (선택)".
   - Step2: 헤더 한국어("데이터 매핑 & 공식 검증" 등), 타입표가 320px 박스로 스크롤(페이지 안
     늘어남), 데미지 컬럼 없는 데이터에선 "데미지 공식 자동 추정" 섹션이 안 보임(C 적용 시),
     승인 후 "✅ 시스템 정의 완료! …승률 예측 모델 학습…" 문구.
3. 맵핑 승인 → mapping_approved 분기·로스터/모델 학습 정상(카피 변경이 흐름 안 깸).

`ast.parse`(1번)가 C의 들여쓰기 사고를 잡는 1차 게이트.

---

## F. 적용 후 보고
- 수정 파일·라인, `wc -l`/`tail` 무결성.
- Step1·Step2 캡처(한국어 통일·타입표 박스화·자동추정 숨김 확인).
