import psycopg2
conn = psycopg2.connect('postgresql://postgres:1234@localhost:5432/library_db')
cur = conn.cursor()
cur.execute("SELECT tablename FROM pg_catalog.pg_tables;")
tables = [row[0] for row in cur.fetchall() if row[0] in ['students', 'attendance_logs', 'student']]
print("Tables in library_db:", tables)
