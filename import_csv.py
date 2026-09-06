"""
One-time import script: reads a CSV export and loads it into assets.db.
Usage: python import_csv.py assets.csv
"""

import csv
import sqlite3
import sys
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets.db')
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')

COLUMN_MAP = [
    (0, 'serial'), (1, 'mac'), (2, 'model'), (3, 'keyboard'), (4, 'mouse'),
    (5, 'monitor_left'), (6, 'monitor_right'), (7, 'power_adapter'), (8, 'vga'),
    (9, 'headset'), (10, 'location'), (11, 'sub_location'), (12, 'area'),
    (13, 'sub_area'), (14, 'qeid'), (15, 'pein'), (16, 'user'), (17, 'site'),
    (18, 'po_number'), (19, 'image'), (20, 'hpdm_hostname'), (21, 'tag_number'),
    (22, 'date_deployed'), (23, 'date_returned'), (24, 'warranty_start'),
    (25, 'warranty_end'), (26, 'status'),
]


def init_db(conn):
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.commit()


def import_csv(csv_path, conn):
    inserted, skipped, blank_serial = 0, 0, 0

    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)  # skip header row

        for row_num, row in enumerate(reader, start=2):
            if len(row) < 27:
                print(f"  Row {row_num}: skipped (only {len(row)} columns, expected 27)")
                skipped += 1
                continue

            values = {name: row[idx].strip() for idx, name in COLUMN_MAP}

            if not values['serial']:
                print(f"  Row {row_num}: skipped (blank serial)")
                blank_serial += 1
                continue

            columns = ', '.join(values.keys())
            placeholders = ', '.join('?' for _ in values)
            sql = f"INSERT OR IGNORE INTO assets ({columns}) VALUES ({placeholders})"

            try:
                conn.execute(sql, list(values.values()))
                inserted += 1
            except sqlite3.IntegrityError as e:
                print(f"  Row {row_num}: skipped ({e})")
                skipped += 1

    conn.commit()
    return inserted, skipped, blank_serial


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_csv.py <path_to_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    print(f"Importing {csv_path} into {DB_PATH} ...")
    inserted, skipped, blank_serial = import_csv(csv_path, conn)

    total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    conn.close()

    print("\nDone.")
    print(f"  Inserted:            {inserted}")
    print(f"  Skipped (bad row):   {skipped}")
    print(f"  Skipped (no serial): {blank_serial}")
    print(f"  Total rows in DB:    {total}")


if __name__ == '__main__':
    main()