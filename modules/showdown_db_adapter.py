import os
import sqlite3
import zipfile
import json
import pandas as pd
import tempfile
import shutil

def _sqlite_table_names(input_path):
    conn = sqlite3.connect(input_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()

def _read_sqlite_table(input_path, table_name):
    conn = sqlite3.connect(input_path)
    try:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()

def extract_from_sqlite_db(input_path):
    table_names = _sqlite_table_names(input_path)
    required_tables = {"battles", "battle_events"}
    missing_tables = sorted(required_tables - table_names)
    if missing_tables:
        raise ValueError(
            "SQLite DB is missing required table(s): "
            + ", ".join(missing_tables)
        )

    battles_df = _read_sqlite_table(input_path, "battles")
    events_df = _read_sqlite_table(input_path, "battle_events")
    rosters_df = None
    if "battle_roster_pokemon" in table_names:
        rosters_df = _read_sqlite_table(input_path, "battle_roster_pokemon")

    return battles_df, events_df, rosters_df

def extract_from_zip_or_dir(input_path):
    is_temp = False
    base_dir = input_path

    if os.path.isfile(input_path) and input_path.lower().endswith('.db'):
        return extract_from_sqlite_db(input_path)
    
    if os.path.isfile(input_path) and input_path.lower().endswith('.zip'):
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(input_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        is_temp = True
        base_dir = temp_dir

    battles_df = None
    events_df = None
    rosters_df = None

    # Handle optional subdirectory inside zip
    target_dir = base_dir
    files_in_base = os.listdir(base_dir)
    if len(files_in_base) == 1 and os.path.isdir(os.path.join(base_dir, files_in_base[0])):
        target_dir = os.path.join(base_dir, files_in_base[0])

    battles_path = os.path.join(target_dir, 'battles.csv')
    events_path = os.path.join(target_dir, 'battle_events.csv')
    rosters_path = os.path.join(target_dir, 'battle_roster_pokemon.csv')

    if os.path.exists(battles_path):
        battles_df = pd.read_csv(battles_path)
    if os.path.exists(events_path):
        events_df = pd.read_csv(events_path)
    if os.path.exists(rosters_path):
        rosters_df = pd.read_csv(rosters_path)

    if is_temp:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return battles_df, events_df, rosters_df

def _normalize_species(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text == "nan":
        return ""
    # Showdown pokemon_name may be "Breloom, F" or "Garchomp, M".
    return text.split(",", 1)[0].strip()

def convert_to_battle_log(battles_df, events_df, rosters_df=None):
    if battles_df is None or events_df is None:
        raise ValueError("battles_df or events_df is missing in the extract.")

    battle_info = {}
    winner_sides = {}
    for _, row in battles_df.iterrows():
        b_id = str(row['battle_id'])
        w_side = str(row.get('winner_side', 'p1'))
        battle_info[b_id] = {
            'winner_side': w_side
        }
        winner_sides[b_id] = w_side

    global_winner_side = "p1"
    if len(winner_sides) == 1:
        global_winner_side = list(winner_sides.values())[0]

    out_rows = []
    
    participant_count = 0
    roster_only_entities = []
    
    # 1. Generate Participant rows
    if 'battle_id' not in events_df.columns:
        raise ValueError("battle_events.csv must contain 'battle_id' column")
        
    battle_entities_seen = {} # b_id -> set of entity_ids
    battle_species_seen = {} # b_id -> set of (side, normalized_species)
    
    for b_id, group in events_df.groupby('battle_id'):
        b_info = battle_info.get(str(b_id), {'winner_side': 'p1'})
        ally_side = 'p1'
        winner_side = b_info['winner_side']
        ally_win = 1 if winner_side == ally_side else 0
        
        entities_seen = set()
        species_seen = set()
        first_p1_active = False
        first_p2_active = False
        
        group = group.sort_values(by='seq')
        
        for _, row in group.iterrows():
            if str(row.get('event_type', '')) == 'PokemonSwitched':
                side = str(row.get('actor_side', 'nan'))
                name = str(row.get('actor_name', 'nan'))
                if side == 'nan' or name == 'nan':
                    continue
                entity_id = f"{side}:{name}"
                
                if entity_id not in entities_seen:
                    entities_seen.add(entity_id)
                    
                    species_raw = row.get('pokemon_name', name)
                    norm_spec = _normalize_species(species_raw)
                    if norm_spec:
                        species_seen.add((side, norm_spec))
                        
                    team = 'ally' if side == 'p1' else 'enemy'
                    result = ally_win # Fix 1: result = ally_win for BOTH sides
                    
                    initial = False
                    if side == 'p1' and not first_p1_active:
                        initial = True
                        first_p1_active = True
                    elif side == 'p2' and not first_p2_active:
                        initial = True
                        first_p2_active = True
                        
                    hp_max_val = row.get('hp_max', None)
                    if pd.isna(hp_max_val): hp_max_val = 100
                        
                    out_rows.append({
                        'battle_id': b_id,
                        'seq': -1, 
                        'turn_no': 0,
                        'row_kind': 'participant',
                        'team': team,
                        'entity_id': entity_id,
                        'name': name,
                        'species': str(row.get('pokemon_name', name)),
                        'HP': hp_max_val,
                        'result': result,
                        'initial_on_field': initial,
                    })
                    participant_count += 1
        battle_entities_seen[str(b_id)] = entities_seen
        battle_species_seen[str(b_id)] = species_seen

    # Compute roster_only_entities
    if rosters_df is not None and not rosters_df.empty:
        def _first_existing_column(df, candidates):
            for col in candidates:
                if col in df.columns:
                    return col
            return None

        species_col = _first_existing_column(rosters_df, ['species', 'pokemon_name', 'name'])

        if 'battle_id' in rosters_df.columns and 'side' in rosters_df.columns and species_col:
            for _, r_row in rosters_df.iterrows():
                b_id_str = str(r_row['battle_id'])
                side = str(r_row['side'])
                species_val = r_row[species_col]
                
                species = _normalize_species(species_val)
                if not species:
                    continue
                    
                seen_species = battle_species_seen.get(b_id_str, set())
                
                if (side, species) not in seen_species:
                    roster_only_entities.append({
                        "battle_id": b_id_str,
                        "side": side,
                        "species": species
                    })
    
    # 2. Generate Trace Rows
    events_df = events_df.sort_values(by=['battle_id', 'seq'])
    
    move_count = 0
    state_event_count = 0
    damage_event_count = 0
    unknown_damage_actor_count = 0
    
    for b_id, group in events_df.groupby('battle_id'):
        last_move = None
        last_hp_by_entity = {}
        last_hp_max_by_entity = {}
        
        for _, row in group.iterrows():
            etype = str(row.get('event_type', ''))
            seq = row.get('seq', 0)
            turn = row.get('turn_no', 0)
            
            # Move Row
            if etype == 'MoveUsed':
                move_count += 1
                actor_side = str(row.get('actor_side', 'nan'))
                actor_name = str(row.get('actor_name', 'nan'))
                tgt_side = str(row.get('target_side', 'nan'))
                tgt_name = str(row.get('target_name', 'nan'))
                
                m_actor_id = f"{actor_side}:{actor_name}" if actor_side != 'nan' else ""
                m_tgt_id = f"{tgt_side}:{tgt_name}" if tgt_side != 'nan' else ""
                
                last_move = {
                    "turn_no": turn,
                    "actor_id": m_actor_id,
                    "target_id": m_tgt_id,
                    "seq": seq
                }
                
                out_rows.append({
                    'battle_id': b_id,
                    'seq': seq,
                    'turn_no': turn,
                    'row_kind': 'move',
                    'move_actor_id': m_actor_id,
                    'move_target_id': m_tgt_id,
                    'move_name': str(row.get('move_name', '')),
                    'move_order': seq,
                })
            
            # State Row
            state_triggers = ['PokemonSwitched', 'DamageApplied', 'HealApplied', 'StatusApplied', 'StatusCured', 'PokemonFainted']
            if etype in state_triggers:
                state_event_count += 1
                actor_side = str(row.get('actor_side', 'nan'))
                actor_name = str(row.get('actor_name', 'nan'))
                if actor_side != 'nan' and actor_name != 'nan':
                    s_entity_id = f"{actor_side}:{actor_name}"
                    
                    hp_curr = row.get('hp_current', None)
                    hp_max = row.get('hp_max', None)
                    
                    # Fix 2: Do not force hp_curr to 0 if NaN.
                    if pd.isna(hp_curr): 
                        hp_curr = None
                    else:
                        last_hp_by_entity[s_entity_id] = float(hp_curr)
                        
                    if pd.isna(hp_max):
                        hp_max = last_hp_max_by_entity.get(s_entity_id, None)
                    else:
                        last_hp_max_by_entity[s_entity_id] = float(hp_max)
                    
                    fainted = False
                    if etype == 'PokemonFainted':
                        fainted = True
                        if hp_curr is None:
                            hp_curr = 0 # Fainted with no HP implies 0
                    elif hp_curr is not None and float(hp_curr) <= 0:
                        fainted = True
                        
                    hp_status = str(row.get('hp_status', ''))
                    effect = str(row.get('effect', ''))
                    
                    if hp_status == 'nan': hp_status = ""
                    if effect == 'nan': effect = ""
                    
                    if etype == 'StatusApplied':
                        if not hp_status:
                            hp_status = effect
                    elif etype == 'StatusCured':
                        hp_status = "" # Cured status implies no status
                    
                    out_rows.append({
                        'battle_id': b_id,
                        'seq': seq,
                        'turn_no': turn,
                        'row_kind': 'state',
                        'state_entity_id': s_entity_id,
                        'hp_current': hp_curr,
                        'hp_max': hp_max,
                        'hp_status': hp_status,
                        'fainted': fainted,
                        'state_event_type': etype,
                        'state_effect': effect,
                        'state_source': str(row.get('source', '')),
                        'state_details_json': str(row.get('details_json', '{}')),
                        'state_raw_line': str(row.get('raw_line', '')),
                        'state_delta_hp': row.get('delta_hp', 0.0) if not pd.isna(row.get('delta_hp', 0.0)) else 0.0
                    })
            
            # Damage Row
            if etype == 'DamageApplied':
                damage_event_count += 1
                actor_side = str(row.get('actor_side', 'nan'))
                actor_name = str(row.get('actor_name', 'nan'))
                d_tgt_id = f"{actor_side}:{actor_name}" if actor_side != 'nan' else ""
                
                delta_hp = row.get('delta_hp', 0)
                if pd.isna(delta_hp): delta_hp = 0
                damage_val = abs(float(delta_hp))
                
                source = str(row.get('source', ''))
                if source == 'nan': source = ''
                
                details_json = str(row.get('details_json', '{}'))
                if details_json == 'nan': details_json = '{}'
                
                try:
                    details = json.loads(details_json)
                except:
                    details = {}
                    
                d_actor_id = ""
                d_source_kind = "other"
                
                if not source:
                    d_source_kind = "direct_move"
                    # Fix 3: Require turn and target matching
                    if last_move and last_move['turn_no'] == turn and last_move['target_id'] == d_tgt_id:
                        d_actor_id = last_move['actor_id']
                elif source.startswith('item:'):
                    d_source_kind = "item"
                elif source.startswith('ability:'):
                    d_source_kind = "ability"
                elif source == 'Stealth Rock':
                    d_source_kind = "hazard"
                elif source in ['sandstorm', 'hail']:
                    d_source_kind = "weather"
                elif source in ['psn', 'brn', 'tox']:
                    d_source_kind = "status"
                else:
                    d_source_kind = "other"
                    
                if not d_actor_id and "of" in details and details["of"]:
                    parts = details["of"].split(': ')
                    if len(parts) >= 2:
                        d_actor_id = f"{parts[0][:2]}:{parts[1]}"
                    else:
                        d_actor_id = details["of"]
                        
                if not d_actor_id:
                    unknown_damage_actor_count += 1
                    
                out_rows.append({
                    'battle_id': b_id,
                    'seq': seq,
                    'turn_no': turn,
                    'row_kind': 'damage',
                    'damage_target_id': d_tgt_id,
                    'damage_value': damage_val,
                    'damage_source': source,
                    'damage_source_kind': d_source_kind,
                    'damage_actor_id': d_actor_id,
                    'effect': str(row.get('effect', '')),
                    'source': source,
                    'raw_line': str(row.get('raw_line', '')),
                    'details_json': details_json
                })
                
    res_df = pd.DataFrame(out_rows)
    
    report = {
        "source_kind": "pokemon_showdown_db_extract",
        "battle_count": len(battle_info),
        "event_count": len(events_df),
        "participant_count": participant_count,
        "move_count": move_count,
        "state_event_count": state_event_count,
        "damage_event_count": damage_event_count,
        "winner_side": global_winner_side, # Fix 4
        "winner_sides": winner_sides,      # Fix 4
        "warnings": [],
        "roster_only_entities": roster_only_entities, # Fix 5
        "unknown_damage_actor_count": unknown_damage_actor_count
    }
    
    return res_df, report

def generate_schema():
    return {
        "system_stats": ["HP"],
        "system_gimmicks": ["species"],
        "health_stat": "HP",
        "target_col": "result",
        "battle_size": 2,
        "global_damage_formula": "0",
        "sim_max_turns": 100,
        "log_schema": {
            "battle_id_col": "battle_id",
            "team_col": "team",
            "entity_id_col": "entity_id",
            "sort_cols": ["seq"],
            "result_mode": "battle_level",
            "ally_values": ["ally"],
            "enemy_values": ["enemy"],

            "initial_on_field_enabled": True,
            "initial_on_field_col": "initial_on_field",
            "initial_on_field_values": ["true", "1", "yes", "lead", True],

            "trace_moves_enabled": True,
            "turn_col": "turn_no",
            "actor_id_col": "move_actor_id",
            "target_id_col": "move_target_id",
            "move_name_col": "move_name",
            "move_order_col": "move_order",
            "move_order_direction": "ascending_first",
            "action_col": "row_kind",
            "move_action_values": ["move"],

            "state_trace_enabled": True,
            "state_turn_col": "turn_no",
            "state_entity_id_col": "state_entity_id",
            "state_hp_col": "hp_current",
            "state_status_col": "hp_status",
            "state_fainted_col": "fainted",
            "state_hp_mode": "absolute",
            "state_hp_tolerance": 0.0,

            "damage_trace_enabled": False,

            "observed_status_trace_enabled": True,
            "status_event_type_col": "state_event_type",
            "status_entity_id_col": "state_entity_id",
            "status_value_col": "hp_status",
            "status_effect_col": "state_effect",
            "status_turn_col": "turn_no",

            "observed_hp_trace_enabled": True,
            "hp_event_type_col": "state_event_type",
            "hp_entity_id_col": "state_entity_id",
            "hp_value_col": "hp_current",
            "hp_max_col": "hp_max",
            "hp_fainted_col": "fainted",
            "hp_turn_col": "turn_no",
            "hp_order_col": "seq",

            "observed_switch_trace_enabled": True,
            "switch_event_type_col": "state_event_type",
            "switch_entity_id_col": "state_entity_id",
            "switch_turn_col": "turn_no",
            "switch_order_col": "seq"
        }
    }
