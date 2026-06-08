import streamlit as st
import pandas as pd
import json
import io

# ── 지원 확장자 ──
_SUPPORTED_TYPES = ["csv", "xlsx", "xls", "json", "tsv", "txt", "parquet", "db", "zip"]


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
    warning_msg = "⚠️ 전투 데이터 파일을 업로드해야 합니다."

    st.subheader("전투 데이터 업로드")
    uploaded_file = st.file_uploader(
        "전투 데이터 파일",
        type=_SUPPORTED_TYPES,
        help="지원 형식: CSV, Excel, JSON, TSV, TXT, Parquet, DB, ZIP",
    )

    if uploaded_file:
        name_lower = uploaded_file.name.lower()
        if name_lower.endswith(".db") or name_lower.endswith(".zip"):
            # DB Corpus Flow
            already_processed = (
                st.session_state.get("current_file_name") == uploaded_file.name
                and "db_corpus_adapter_report" in st.session_state
            )
            
            if not already_processed:
                with st.spinner("데이터 추출 및 변환 중... (데이터 크기에 따라 다소 시간이 걸릴 수 있습니다)"):
                    try:
                        from modules.ui_db_corpus_helper import process_db_corpus_upload
                        
                        df, report, schema, raw_tables = process_db_corpus_upload(uploaded_file.read(), uploaded_file.name)
                        
                        st.session_state["df"] = df
                        st.session_state["current_file_name"] = uploaded_file.name
                        st.session_state["db_corpus_adapter_report"] = report
                        st.session_state["db_corpus_schema"] = schema
                        st.session_state["bb_last_corpus_schema"] = schema
                        st.session_state["bb_last_log_schema"] = schema["log_schema"]
                        st.session_state["db_corpus_last_backtest_has_run"] = False
                        st.session_state["db_corpus_raw_tables"] = raw_tables
                        st.session_state["structured_package_mode"] = True
                        
                        # 자동 매핑 적용 (schema 기반)
                        st.session_state["target_col"] = schema.get("target_col", "result")
                        
                        # Default stats: search for base stat columns in raw roster, fallback to system_stats or HP
                        rosters_df = raw_tables.get("battle_roster_pokemon")
                        base_stats_inferred = []
                        if rosters_df is not None:
                            stat_candidates = ['hp_base', 'atk_base', 'def_base', 'spatk_base', 'spdef_base', 'spd_base', 'hp', 'atk', 'def', 'spa', 'spd', 'spe']
                            base_stats_inferred = [c for c in stat_candidates if c in rosters_df.columns]
                        if not base_stats_inferred:
                            base_stats_inferred = schema.get("system_stats", ["HP"])
                        
                        st.session_state["system_stats"] = base_stats_inferred
                        
                        # Default gimmicks: species, type, ability, item from roster
                        gimmicks_inferred = []
                        if rosters_df is not None:
                            gimmick_candidates = ['species', 'type1', 'type2', 'ability', 'item', 'level', 'player']
                            gimmicks_inferred = [c for c in gimmick_candidates if c in rosters_df.columns]
                        if not gimmicks_inferred:
                            gimmicks_inferred = schema.get("system_gimmicks", [])
                            
                        st.session_state["system_gimmicks"] = gimmicks_inferred
                        
                        # Default health stat
                        health_stat = "HP"
                        if rosters_df is not None and "hp_base" in rosters_df.columns:
                            health_stat = "hp_base"
                        elif schema.get("health_stat"):
                            health_stat = schema.get("health_stat")
                        st.session_state["health_stat"] = health_stat
                        
                        st.session_state["input_mode"] = "structured_battle_package"
                        
                        # Schema-Agnostic 초기 정보 저장 (호환성 유지)
                        st.session_state["char_col"] = df.columns[0]
                        st.session_state["numeric_cols_raw"] = (
                            df.select_dtypes(include=["int64", "float64"]).columns.tolist()
                        )
                        
                        if "combat_flow" in st.session_state:
                            del st.session_state["combat_flow"]
                            
                        st.success(f"✅ 전투 데이터 파일 변환 완료! (총 {len(df)}행, {len(df.columns)}열)")
                        
                    except Exception as e:
                        st.error(f"❌ DB 변환 중 오류가 발생했습니다: {e}")
                        with st.expander("에러 상세 내역"):
                            import traceback
                            st.code(traceback.format_exc(), language="python")
            
            if st.session_state.get("db_corpus_adapter_report") and st.session_state.get("current_file_name") == getattr(uploaded_file, "name", None):
                report = st.session_state["db_corpus_adapter_report"]
                can_proceed = True
                warning_msg = ""
                
                st.success("✅ Step 6: 백테스트 단계에서 즉시 실행이 가능합니다.")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Battles", report.get("battle_count", 0))
                col2.metric("Participants", report.get("participant_count", 0))
                col3.metric("State Events", report.get("state_event_count", 0))
                col4.metric("Damage Events", report.get("damage_event_count", 0))
                
                col5, col6, col7, _ = st.columns(4)
                col5.metric("Events", report.get("event_count", 0))
                col6.metric("Unknown Dmg Actors", report.get("unknown_damage_actor_count", 0))
                col7.metric("Roster-only", len(report.get("roster_only_entities", [])))
                
                warn_cnt = len(report.get("warnings", []))
                if warn_cnt > 0:
                    with st.expander(f"⚠️ 변환 중 {warn_cnt}개의 경고가 발생했습니다"):
                        for w in report.get("warnings", []):
                            st.text(w)

        else:
            # Standard Log Flow
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
                    # 기존 DB 코퍼스 세션 데이터 초기화
                    for k in ["db_corpus_adapter_report", "db_corpus_schema", "bb_last_corpus_schema", "bb_last_log_schema", "db_corpus_last_backtest_has_run", "input_mode"]:
                        if k in st.session_state:
                            del st.session_state[k]
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
                with st.expander("에러 상세 내역"):
                    import traceback
                    st.code(traceback.format_exc(), language="python")

    st.markdown("---")
    
    st.subheader("무브 로그 업로드 (선택)")
    st.info("📌 무브 단위 데이터가 있는 경우 업로드하세요. 없으면 건너뛰고 다음 단계로 진행할 수 있습니다.")
    attack_file = st.file_uploader(
        "무브 로그 파일",
        type=["csv", "xlsx", "xls", "json", "tsv", "txt", "parquet"],
        help="무브별 행이 담긴 파일. 지원 형식: CSV · Excel · JSON · TSV · TXT · Parquet",
        key="ui_attack_log_step1",
    )
    if attack_file is not None:
        try:
            attack_df = _parse_log_file(attack_file)
            st.session_state["attack_log_df"] = attack_df
            st.success(f"✅ 무브 로그 파싱 완료! ({len(attack_df)}행, {len(attack_df.columns)}열)")
            with st.expander("무브 로그 미리보기", expanded=False):
                col_cfg = {}
                for c in attack_df.columns:
                    if pd.api.types.is_numeric_dtype(attack_df[c]):
                        col_cfg[c] = st.column_config.NumberColumn(c, format="%.1f")
                    else:
                        col_cfg[c] = st.column_config.TextColumn(c)
                st.dataframe(attack_df.head(100), use_container_width=True, height=300, column_config=col_cfg)
        except Exception as e:
            st.error(f"❌ 어택 로그 파싱 오류: {e}")
    elif st.session_state.get("attack_log_df") is not None:
        _atk = st.session_state["attack_log_df"]
        st.caption(f"📦 세션에 저장된 무브 로그 ({len(_atk)}행) 사용 중")

    st.markdown("---")
    st.subheader("저장한 매핑 불러오기 (선택)")
    preset_file = st.file_uploader(
        "매핑 프리셋 파일 (JSON)",
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
