import sqlite3
import pandas as pd

conn = sqlite3.connect('C:/Users/kmjde/Downloads/pokemon_showdown_production_style.db')
tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
print(tables)
for t in tables['name']:
    print(t, pd.read_sql_query(f'SELECT * FROM {t} LIMIT 1', conn).columns.tolist())
