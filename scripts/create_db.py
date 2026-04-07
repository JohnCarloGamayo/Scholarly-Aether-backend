import psycopg2

conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5432/postgres")
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='ai_research'")
if cur.fetchone() is None:
    cur.execute("CREATE DATABASE ai_research")
    print("Created database ai_research")
else:
    print("Database ai_research already exists")
cur.close()
conn.close()
