-- Pokemon Showdown replay normalized DB schema
-- Generated as a production-style relational extract

CREATE TABLE battle_events (
    event_id TEXT PRIMARY KEY,
    battle_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    turn_no INTEGER,
    phase TEXT,
    event_type TEXT NOT NULL,
    command TEXT,
    actor_id TEXT,
    actor_side TEXT,
    actor_slot TEXT,
    actor_name TEXT,
    target_id TEXT,
    target_side TEXT,
    target_slot TEXT,
    target_name TEXT,
    move_name TEXT,
    pokemon_name TEXT,
    hp_current INTEGER,
    hp_max INTEGER,
    hp_status TEXT,
    delta_hp INTEGER,
    effect TEXT,
    source TEXT,
    details_json TEXT,
    raw_args_json TEXT,
    raw_line TEXT NOT NULL,
    FOREIGN KEY (battle_id) REFERENCES battles(battle_id),
    UNIQUE (battle_id, seq)
);

CREATE TABLE battle_players (
    player_id TEXT PRIMARY KEY,
    battle_id TEXT NOT NULL,
    side TEXT NOT NULL,
    username TEXT NOT NULL,
    avatar TEXT,
    FOREIGN KEY (battle_id) REFERENCES battles(battle_id)
);

CREATE TABLE battle_roster_pokemon (
    roster_id TEXT PRIMARY KEY,
    battle_id TEXT NOT NULL,
    side TEXT NOT NULL,
    slot_index INTEGER NOT NULL,
    species TEXT NOT NULL,
    gender TEXT,
    raw_pokemon_text TEXT,
    FOREIGN KEY (battle_id) REFERENCES battles(battle_id),
    UNIQUE (battle_id, side, slot_index)
);

CREATE TABLE battle_rules (
    battle_id TEXT NOT NULL,
    rule_order INTEGER NOT NULL,
    rule_name TEXT NOT NULL,
    rule_description TEXT,
    PRIMARY KEY (battle_id, rule_order),
    FOREIGN KEY (battle_id) REFERENCES battles(battle_id)
);

CREATE TABLE battles (
    battle_id TEXT PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_replay_id TEXT,
    title TEXT,
    game_type TEXT,
    generation INTEGER,
    tier TEXT,
    winner_side TEXT,
    winner_name TEXT,
    total_turns INTEGER,
    imported_at TEXT NOT NULL
);

CREATE INDEX idx_battle_events_actor ON battle_events(actor_side, actor_name);

CREATE INDEX idx_battle_events_battle_seq ON battle_events(battle_id, seq);

CREATE INDEX idx_battle_events_target ON battle_events(target_side, target_name);

CREATE INDEX idx_battle_events_turn ON battle_events(battle_id, turn_no, seq);

CREATE INDEX idx_battle_events_type ON battle_events(event_type);

