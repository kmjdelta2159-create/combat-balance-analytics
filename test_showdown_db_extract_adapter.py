import os
import tempfile
import shutil
import json
import zipfile
import sqlite3
import pandas as pd

from convert_showdown_db_extract import extract_from_zip_or_dir, convert_to_battle_log, generate_schema
from modules.per_battle_backtest import build_battles_from_log_schema

def create_mock_showdown_db_extract(base_dir):
    battles_data = {
        "battle_id": ["mock_battle_1", "mock_battle_2", "mock_battle_3"],
        "source_system": ["showdown"] * 3,
        "source_replay_id": ["1", "2", "3"],
        "title": ["Mock Battle"] * 3,
        "game_type": ["singles"] * 3,
        "generation": [5] * 3,
        "tier": ["gen5ou"] * 3,
        "winner_side": ["p1", "p2", "p1"],
        "winner_name": ["Player1", "Player2", "Player1"],
        "total_turns": [5] * 3,
        "imported_at": ["2023-01-01T00:00:00Z"] * 3
    }
    
    events_data = {
        "event_id": list(range(1, 16)),
        "battle_id": [
            "mock_battle_1", "mock_battle_1", "mock_battle_1", "mock_battle_1", "mock_battle_1", # 1-5
            "mock_battle_2", "mock_battle_2", # 6-7
            "mock_battle_3", "mock_battle_3", "mock_battle_3", "mock_battle_3", "mock_battle_3", "mock_battle_3", "mock_battle_3", "mock_battle_3" # 8-15
        ],
        "seq": [1, 2, 3, 4, 5, 1, 2, 1, 2, 3, 4, 5, 6, 7, 8],
        "turn_no": [0, 0, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
        "phase": ["switch", "switch", "move", "damage", "faint", "switch", "switch", "switch", "switch", "move", "damage", "state", "state", "damage", "damage"],
        "event_type": [
            "PokemonSwitched", "PokemonSwitched", "MoveUsed", "DamageApplied", "PokemonFainted", # 1
            "PokemonSwitched", "PokemonSwitched", # 2
            "PokemonSwitched", "PokemonSwitched", "MoveUsed", "DamageApplied", "StatusApplied", "StatusCured", "DamageApplied", "DamageApplied" # 3
        ],
        "command": [""] * 15,
        "actor_id": [
            "p2:Politoed", "p1:Tyranitar", "p1:Tyranitar", "p2:Politoed", "p2:Politoed", # 1
            "p1:Gengar", "p2:Alakazam", # 2
            "p1:A", "p2:B", "p1:A", "p2:B", "p2:B", "p2:B", "p1:A", "p1:A" # 3
        ],
        "actor_side": [
            "p2", "p1", "p1", "p2", "p2",
            "p1", "p2",
            "p1", "p2", "p1", "p2", "p2", "p2", "p1", "p1"
        ],
        "actor_slot": [1]*15,
        "actor_name": [
            "Politoed", "Tyranitar", "Tyranitar", "Politoed", "Politoed",
            "Gengar", "Alakazam",
            "A", "B", "A", "B", "B", "B", "A", "A"
        ],
        "target_id": [
            "", "", "p2:Politoed", "", "",
            "", "",
            "", "", "p2:B", "", "", "", "", ""
        ],
        "target_side": [
            "", "", "p2", "", "",
            "", "",
            "", "", "p2", "", "", "", "", ""
        ],
        "target_slot": [""]*15,
        "target_name": [
            "", "", "Politoed", "", "",
            "", "",
            "", "", "B", "", "", "", "", ""
        ],
        "move_name": ["", "", "Crunch", "", "", "", "", "", "", "Tackle", "", "", "", "", ""],
        "pokemon_name": ["Politoed", "Tyranitar", "", "", "", "Gengar", "Alakazam", "A", "B", "", "", "", "", "", ""],
        "hp_current": [
            100, 100, "", 0, 0,
            100, 100,
            100, 100, "", 50, "", "", 80, 60
        ],
        "hp_max": [
            100, 100, "", 100, 100,
            100, 100,
            100, 100, "", 100, "", "", 100, 100
        ],
        "hp_status": [""]*15,
        "delta_hp": [
            0, 0, "", -100, 0,
            0, 0,
            0, 0, "", -50, "", "", -20, -20
        ],
        "effect": [
            "", "", "", "", "",
            "", "",
            "", "", "", "", "slp", "", "", ""
        ],
        "source": [
            "", "", "", "", "",
            "", "",
            "", "", "", "", "", "", "psn", "" # 14: damage from poison, 15: direct damage mismatch
        ],
        "details_json": ["{}"]*15,
        "raw_args_json": ["[]"]*15,
        "raw_line": [""]*15
    }
    
    roster_data = {
        "battle_id": ["mock_battle_1", "mock_battle_1", "mock_battle_2", "mock_battle_3"],
        "side": ["p1", "p2", "p2", "p1"],
        "slot_index": [1, 1, 1, 1],
        "species": ["Tyranitar", "Politoed", "UnusedMon", "A"]
    }
    
    pd.DataFrame(battles_data).to_csv(os.path.join(base_dir, "battles.csv"), index=False)
    pd.DataFrame(events_data).to_csv(os.path.join(base_dir, "battle_events.csv"), index=False)
    pd.DataFrame(roster_data).to_csv(os.path.join(base_dir, "battle_roster_pokemon.csv"), index=False)


def create_sqlite_db_from_extract(extract_dir, db_path):
    table_files = {
        "battles": "battles.csv",
        "battle_events": "battle_events.csv",
        "battle_roster_pokemon": "battle_roster_pokemon.csv",
    }
    conn = sqlite3.connect(db_path)
    try:
        for table_name, filename in table_files.items():
            csv_path = os.path.join(extract_dir, filename)
            if os.path.exists(csv_path):
                pd.read_csv(csv_path).to_sql(table_name, conn, index=False)
    finally:
        conn.close()


def test_showdown_db_extract_adapter():
    temp_dir = tempfile.mkdtemp()
    
    try:
        mock_folder = os.path.join(temp_dir, "mock_extract")
        os.makedirs(mock_folder)
        create_mock_showdown_db_extract(mock_folder)
        
        battles_df, events_df, rosters_df = extract_from_zip_or_dir(mock_folder)
        battle_log_df, report = convert_to_battle_log(battles_df, events_df, rosters_df)
        
        schema = generate_schema()
        
        built_battles = build_battles_from_log_schema(
            df=battle_log_df,
            target_col=schema["target_col"],
            system_stats=schema["system_stats"],
            system_gimmicks=schema["system_gimmicks"],
            health_stat=schema["health_stat"],
            log_schema=schema["log_schema"]
        )
            
        b1_logs = battle_log_df[battle_log_df['battle_id'] == 'mock_battle_1']
        b2_logs = battle_log_df[battle_log_df['battle_id'] == 'mock_battle_2']
        b3_logs = battle_log_df[battle_log_df['battle_id'] == 'mock_battle_3']
        
        # 1. enemy-first result guard
        b1_parts = b1_logs[b1_logs['row_kind'] == 'participant']
        assert all(b1_parts['result'] == 1) # p1 is winner, result=1 for all participants
        b1_built = built_battles[0]
        assert b1_built[2] is True # ally_wins
        
        # 2. p2 winner guard
        b2_parts = b2_logs[b2_logs['row_kind'] == 'participant']
        assert all(b2_parts['result'] == 0) # p2 is winner, result=0
        b2_built = built_battles[1]
        assert b2_built[2] is False # ally_wins = False
        assert report["winner_sides"]["mock_battle_2"] == "p2"
        
        # 3. status event must not faint
        b3_states = b3_logs[b3_logs['row_kind'] == 'state']
        status_app = b3_states[b3_states['seq'] == 5].iloc[0] # seq=5 is StatusApplied
        assert pd.isna(status_app['hp_current']) or status_app['hp_current'] is None
        assert status_app['fainted'] is False
        assert status_app['hp_status'] == 'slp'
        
        status_cur = b3_states[b3_states['seq'] == 6].iloc[0] # seq=6 is StatusCured
        assert status_cur['hp_status'] == ''
        assert status_cur['fainted'] is False
        
        # 4. direct damage target matching
        b3_damages = b3_logs[b3_logs['row_kind'] == 'damage']
        direct_dmg = b3_damages[b3_damages['seq'] == 4].iloc[0]
        assert direct_dmg['damage_source_kind'] == 'direct_move'
        assert direct_dmg['damage_actor_id'] == 'p1:A' # successfully connected to previous move
        
        psn_dmg = b3_damages[b3_damages['seq'] == 7].iloc[0]
        assert psn_dmg['damage_source_kind'] == 'status'
        assert psn_dmg['damage_actor_id'] == '' # could not infer actor
        
        mismatch_damage = b3_damages[b3_damages['seq'] == 8].iloc[0]
        assert mismatch_damage['damage_source_kind'] == 'direct_move'
        assert mismatch_damage['damage_actor_id'] == ''
        assert mismatch_damage['damage_target_id'] == 'p1:A'
        
        # 5. roster_only_entities report
        roster_only = report["roster_only_entities"]
        assert len(roster_only) == 1
        assert roster_only[0]["species"] == "UnusedMon"
        assert roster_only[0]["side"] == "p2"
        
    finally:
        shutil.rmtree(temp_dir)

def test_roster_pokemon_name_fallback():
    # Test that if 'species' is missing, it falls back to 'pokemon_name'
    battles_df = pd.DataFrame({
        "battle_id": ["fb_1"],
        "winner_side": ["p1"]
    })
    events_df = pd.DataFrame({
        "battle_id": ["fb_1"],
        "event_type": ["PokemonSwitched"],
        "actor_side": ["p1"],
        "actor_name": ["Charizard"],
        "pokemon_name": ["Charizard"],
        "seq": [1],
        "turn_no": [0]
    })
    rosters_df = pd.DataFrame({
        "battle_id": ["fb_1"],
        "side": ["p2"],
        "pokemon_name": ["Blastoise"] # No species column
    })
    
    battle_log_df, report = convert_to_battle_log(battles_df, events_df, rosters_df)
    
    roster_only = report["roster_only_entities"]
    assert len(roster_only) == 1
    assert roster_only[0]["species"] == "Blastoise"
    assert roster_only[0]["side"] == "p2"

def test_roster_only_uses_species_not_actor_nickname():
    battles_df = pd.DataFrame({
        "battle_id": ["nick_1"],
        "winner_side": ["p1"],
    })
    events_df = pd.DataFrame({
        "battle_id": ["nick_1", "nick_1"],
        "seq": [1, 2],
        "turn_no": [0, 0],
        "event_type": ["PokemonSwitched", "PokemonSwitched"],
        "actor_side": ["p1", "p2"],
        "actor_name": ["Gengen", "Rotom-Wash"],
        "pokemon_name": ["Breloom, F", "Rotom-Wash"],
        "hp_current": [100, 100],
        "hp_max": [100, 100],
    })
    rosters_df = pd.DataFrame({
        "battle_id": ["nick_1", "nick_1", "nick_1"],
        "side": ["p1", "p2", "p2"],
        "species": ["Breloom", "Rotom-Wash", "UnusedMon"],
    })

    _, report = convert_to_battle_log(battles_df, events_df, rosters_df)

    assert report["roster_only_entities"] == [
        {"battle_id": "nick_1", "side": "p2", "species": "UnusedMon"}
    ]

def test_sqlite_db_input_matches_folder_extract():
    temp_dir = tempfile.mkdtemp()

    try:
        mock_folder = os.path.join(temp_dir, "mock_extract")
        os.makedirs(mock_folder)
        create_mock_showdown_db_extract(mock_folder)

        db_path = os.path.join(temp_dir, "mock_extract.db")
        create_sqlite_db_from_extract(mock_folder, db_path)

        folder_frames = extract_from_zip_or_dir(mock_folder)
        sqlite_frames = extract_from_zip_or_dir(db_path)

        assert len(folder_frames[0]) == len(sqlite_frames[0])
        assert len(folder_frames[1]) == len(sqlite_frames[1])
        assert sqlite_frames[2] is not None
        assert len(folder_frames[2]) == len(sqlite_frames[2])

        folder_log_df, folder_report = convert_to_battle_log(*folder_frames)
        sqlite_log_df, sqlite_report = convert_to_battle_log(*sqlite_frames)

        assert len(folder_log_df) == len(sqlite_log_df)
        for key in [
            "battle_count",
            "event_count",
            "participant_count",
            "move_count",
            "state_event_count",
            "damage_event_count",
            "unknown_damage_actor_count",
        ]:
            assert folder_report[key] == sqlite_report[key]

        assert folder_report["winner_sides"] == sqlite_report["winner_sides"]
        assert folder_report["roster_only_entities"] == sqlite_report["roster_only_entities"]
    finally:
        shutil.rmtree(temp_dir)

def test_sqlite_db_input_missing_required_table():
    temp_dir = tempfile.mkdtemp()

    try:
        db_path = os.path.join(temp_dir, "missing_events.db")
        conn = sqlite3.connect(db_path)
        try:
            pd.DataFrame({
                "battle_id": ["missing_1"],
                "winner_side": ["p1"],
            }).to_sql("battles", conn, index=False)
        finally:
            conn.close()

        try:
            extract_from_zip_or_dir(db_path)
            assert False, "Expected missing battle_events table to raise ValueError"
        except ValueError as exc:
            assert "battle_events" in str(exc)
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_showdown_db_extract_adapter()
    test_roster_pokemon_name_fallback()
    test_roster_only_uses_species_not_actor_nickname()
    test_sqlite_db_input_matches_folder_extract()
    test_sqlite_db_input_missing_required_table()
    print("All showdown db extract adapter tests passed.")
