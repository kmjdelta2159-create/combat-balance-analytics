# PR-F1 — Step 1 멀티 포맷 업로드 (CSV 외 전투로그 파일 형식 확장)

> **목표**: `modules/step1_upload.py`의 전투로그 업로더가 CSV 외에
> xlsx·xls·json·tsv·txt·parquet를 모두 받도록 확장한다.
> `requirements.txt`에 `openpyxl`·`pyarrow` 추가.

---

## 1. requirements.txt — 2줄 추가

파일 끝에 아래 두 줄을 추가한다.

```
openpyxl
pyarrow
```

---

## 2. step1_upload.py 전체 교체

현재 파일(65줄)을 아래 내용으로 **전체 교체**한다.
로직 설명은 인라인 주석으로 충분하다 — 별도 서술 생략.

```python
import streamlit as st
import pandas as pd
import json
import io

# ── 지원 확장자 ──
_SUPPORTED_TYPES = ["csv", "xlsx", "xls", "json", "tsv", "txt", "parquet"]


def _parse_log_file(uploaded_file) -> pd.DataFrame:
    """업로드 파일을 확장자별로 파싱해 DataFrame을 반환한다.
    파싱 실패 시 ValueError를 raise한다."""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    uploaded_file.seek(0)  # 후속 read를 위해 리셋

    # ── CSV ──
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(raw))

    # ── TSV / TXT ──
    if name.endswith(".tsv") or name.endswith(".txt"):
        # 탭 구분자 시도 → 실패 시 쉼표 → 실패 시 공백
        for sep in ("\t", ",", r"\s+"):
            try:
                df = pd.read_csv(io.BytesIO(raw), sep=sep, engine="python")
                if df.shape[1] > 1:
                    return df
            except Exception:
                continue
        raise ValueError("TSV/TXT 구분자를 감지할 수 없습니다.")

    # ── Excel ──
    if name.endswith(".xlsx") or name.endswith(".xls"):
        xf = pd.ExcelFile(io.BytesIO(raw))
        if len(xf.sheet_names) == 1:
            return xf.parse(xf.sheet_names[0])
        # 시트가 여러 개면 selectbox로 선택
        sheet = st.selectbox(
            "📋 시트 선택 (Excel 파일에 시트가 여러 개 있습니다)",
            xf.sheet_names,
            key="ui_excel_sheet_select",
        )
        return xf.parse(sheet)

    # ── JSON ──
    if name.endswith(".json"):
        raw_str = raw.decode("utf-8", errors="replace")
        # 1순위: 배열·레코드 형식 (직접 테이블)
        try:
            df = pd.read_json(io.BytesIO(raw))
            if isinstance(df, pd.DataFrame) and df.shape[0] > 0:
                return df
        except Exception:
            pass
        # 2순위: JSONL (줄마다 JSON 객체)
        try:
            df = pd.read_json(io.BytesIO(raw), lines=True)
            if isinstance(df, pd.DataFrame) and df.shape[0] > 0:
                return df
        except Exception:
            pass
        # 3순위: 중첩 객체 → 첫 번째 list 값을 json_normalize
        try:
            obj = json.loads(raw_str)
            if isinstance(obj, dict):
                for key, val in obj.items():
                    if isinstance(val, list) and len(val) > 0:
                        df = pd.json_normalize(val)
                        if df.shape[0] > 0:
                            st.info(
                                f"💡 JSON 중첩 구조에서 `{key}` 배열을 테이블로 변환했습니다."
                            )
                            return df
        except Exception:
            pass
        raise ValueError(
            "JSON을 테이블로 변환할 수 없습니다. "
            "배열-of-objects 형식이거나 JSONL 형식이어야 합니다."
        )

    # ── Parquet ──
    if name.endswith(".parquet"):
        return pd.read_parquet(io.BytesIO(raw))

    raise ValueError(f"지원하지 않는 파일 형식입니다: {name}")


def render_upload():
    can_proceed = False
    warning_msg = "⚠️ 다음 단계로 이동하려면 전투 로그 파일을 업로드해야 합니다."

    st.subheader("새로운 전투 로그 업로드")
    uploaded_file = st.file_uploader(
        "Upload Combat Logs",
        type=_SUPPORTED_TYPES,
        help="지원 형식: CSV · Excel(xlsx/xls) · JSON · TSV · TXT · Parquet",
    )

    if uploaded_file:
        try:
            df = _parse_log_file(uploaded_file)
            st.session_state["df"] = df

            # Schema-Agnostic 초기 정보 저장
            st.session_state["char_col"] = df.columns[0]
            st.session_state["numeric_cols_raw"] = (
                df.select_dtypes(include=["int64", "float64"]).columns.tolist()
            )

            if st.session_state.get("current_file_name") != uploaded_file.name:
                st.session_state["current_file_name"] = uploaded_file.name
                st.session_state["mapping_approved"] = False
                st.session_state["formula_input_ui"] = ""
                if "combat_flow" in st.session_state:
                    del st.session_state["combat_flow"]

            st.success(f"✅ 데이터가 성공적으로 파싱되었습니다! (총 {len(df)}행, {len(df.columns)}열)")

            with st.expander("원본 데이터 미리보기", expanded=False):
                col_config = {}
                for c in df.columns:
                    if pd.api.types.is_numeric_dtype(df[c]):
                        col_config[c] = st.column_config.NumberColumn(c, format="%.1f")
                    else:
                        col_config[c] = st.column_config.TextColumn(c)
                st.dataframe(
                    df.head(100),
                    use_container_width=True,
                    height=400,
                    column_config=col_config,
                )

            can_proceed = True
            warning_msg = ""
        except Exception as e:
            st.error(f"❌ 파일 파싱 중 오류가 발생했습니다: {e}")
            return False, "올바르지 않은 파일입니다."

    st.markdown("---")
    st.subheader("또는 이전 맵핑 프리셋(JSON) 불러오기")
    preset_file = st.file_uploader(
        "Upload Mapping Preset (JSON)",
        type=["json"],
        help="저장된 매핑 설정을 불러와 즉시 복원합니다.",
    )

    if preset_file and "df" in st.session_state:
        try:
            preset_data = json.load(preset_file)
            st.session_state["mapping_approved"] = True
            st.session_state["global_damage_formula"] = preset_data.get(
                "global_damage_formula", ""
            )
            st.session_state["target_col"] = preset_data.get("target_col")
            st.session_state["system_stats"] = preset_data.get("base_stats_list", [])
            st.session_state["system_gimmicks"] = preset_data.get("gimmick_list", [])
            st.session_state["has_ml_data"] = (
                True
                if preset_data.get("target_col")
                and preset_data.get("target_col") != "None"
                else False
            )
            st.session_state["formula_input_ui"] = preset_data.get(
                "global_damage_formula", ""
            )
            st.success("✅ JSON 매핑 프리셋이 성공적으로 로드되었습니다!")
        except Exception as e:
            st.error(f"❌ JSON 파싱 중 오류가 발생했습니다: {e}")

    return can_proceed, warning_msg
```

---

## 3. 변경 요약

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 지원 형식 | csv | csv · xlsx · xls · json · tsv · txt · parquet |
| 파서 | `pd.read_csv` 직접 호출 | `_parse_log_file()` 분기 |
| Excel 멀티시트 | 없음 | 시트 selectbox |
| JSON | 없음 (하단 프리셋 전용) | 배열·JSONL·중첩 객체 3단계 시도 |
| requirements.txt | — | openpyxl · pyarrow 추가 |

---

## 4. 검증 (앱사이드)

1. **앱 로드 에러 없음** — `streamlit run main.py` 정상 기동.
2. **CSV 기존 동작 무변** — 기존 CSV 업로드 후 step 2 진입 정상.
3. **Excel** — 단일 시트 xlsx 업로드 → 파싱 성공. 멀티 시트 xlsx → 시트 selectbox 표시.
4. **JSON 배열** — `[{"col1":1,...},...]` 형식 json → 테이블 로드.
5. **TSV** — 탭 구분 파일 → 정상 파싱.
6. **run_b4.py 회귀0** — 골든 수치 무변.
