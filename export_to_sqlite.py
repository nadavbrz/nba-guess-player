import sqlite3
import pyodbc

# 1. התחברות ל-SQL Server
sql_conn_str = r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=NBA_Project;Trusted_Connection=yes;'
sql_conn = pyodbc.connect(sql_conn_str)
sql_cursor = sql_conn.cursor()

# 2. התחברות ל-SQLite
sqlite_conn = sqlite3.connect('nba_data.db')
sqlite_cursor = sqlite_conn.cursor()

# טבלאות להעברה
tables = ['View_PlayerStats_Formatted', 'Awards', 'AllStars']

print("🚀 מתחיל בהעברה מהירה (Batch Fetch)...")

for table in tables:
    print(f"מעביר את {table}...")

    sql_cursor.execute(f"SELECT * FROM {table}")
    columns = [column[0] for column in sql_cursor.description]

    # יצירת הטבלה ב-SQLite
    sqlite_cursor.execute(f"DROP TABLE IF EXISTS {table}")
    cols_str = ", ".join([f'"{col}" TEXT' for col in columns])
    sqlite_cursor.execute(f"CREATE TABLE {table} ({cols_str})")

    placeholders = ", ".join(["?"] * len(columns))
    insert_query = f"INSERT INTO {table} VALUES ({placeholders})"

    # שליפה בקבוצות של 1,000 שורות כדי למנוע תקיעה
    total_rows = 0
    while True:
        rows = sql_cursor.fetchmany(1000)
        if not rows:
            break
        clean_rows = [tuple(str(val) if val is not None else None for val in row) for row in rows]
        sqlite_cursor.executemany(insert_query, clean_rows)
        total_rows += len(rows)
        print(f"   -> הועברו {total_rows} שורות...")

    sqlite_conn.commit()
    print(f"✅ {table} הושלמה! ({total_rows} שורות)")

# יצירת טבלת הלידרבורד
sqlite_cursor.execute("""
CREATE TABLE IF NOT EXISTS DailyLeaderboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    completion_time_seconds REAL,
    penalties INTEGER,
    total_score_seconds REAL,
    date_played TEXT,
    user_ip TEXT
);
""")
sqlite_conn.commit()

print("\n✨ הסיום בהצלחה! הקובץ nba_data.db מוכן ומלא!")

sql_conn.close()
sqlite_conn.close()