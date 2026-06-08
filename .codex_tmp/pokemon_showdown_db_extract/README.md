# Pokemon Showdown Replay DB Extract

Source file: `Gen5OU-2015-05-11-reymedy-leftiez.html`
Battle ID: `smogtours-gen5ou-59402`
Winner: `Reymedy` (p1)
Total turns: 27
Exported at: 2026-06-08T03:17:27+09:00

This package is structured like a practical database export:

- `schema.sql`: DDL for the normalized relational schema
- `battles.csv`: one row per battle/replay
- `battle_players.csv`: players/sides
- `battle_rules.csv`: rules declared by the replay
- `battle_roster_pokemon.csv`: team preview roster rows
- `battle_events.csv`: ordered event stream with raw command line preserved
- `export_manifest.json`: row counts and column lists

Primary ordering key for replay reconstruction:

```sql
SELECT *
FROM battle_events
WHERE battle_id = 'smogtours-gen5ou-59402'
ORDER BY seq;
```

Useful examples:

```sql
-- Damage events only
SELECT turn_no, seq, actor_side, actor_name, target_side, target_name, delta_hp, raw_line
FROM battle_events
WHERE event_type = 'DamageApplied'
ORDER BY seq;

-- Moves by turn
SELECT turn_no, seq, actor_name, move_name, target_name
FROM battle_events
WHERE event_type = 'MoveUsed'
ORDER BY seq;
```
