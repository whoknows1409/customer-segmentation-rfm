"""Run the SQL layer of the analysis with DuckDB and save every named query to outputs/.

Usage (from the repo root):
    python src/run_sql.py

Each .sql file in sql/ runs in order. 01_clean.sql builds the tables; in the other
files, every query that starts with a `-- name: <name>` comment is saved to
outputs/<name>.csv.
"""
from pathlib import Path
import re

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"
DB_PATH = ROOT / "retail.duckdb"


def named_queries(sql_text: str):
    """Yield (name, query) for each block that starts with '-- name: <name>'."""
    parts = re.split(r"^--\s*name:\s*(\w+)\s*$", sql_text, flags=re.MULTILINE)
    # parts = [preamble, name1, body1, name2, body2, ...]
    for name, body in zip(parts[1::2], parts[2::2]):
        query = body.strip().rstrip(";").strip()
        if query:
            yield name, query


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    # read_csv paths in the SQL are relative to the repo root
    con.execute(f"SET file_search_path = '{ROOT.as_posix()}'")

    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        text = sql_file.read_text()
        queries = list(named_queries(text))
        if not queries:  # setup script, e.g. 01_clean.sql
            con.execute(text)
            print(f"ran     {sql_file.name}")
            continue
        for name, query in queries:
            df = con.execute(query).df()
            df.to_csv(OUT_DIR / f"{name}.csv", index=False)
            print(f"saved   outputs/{name}.csv  ({len(df)} rows)")

    con.close()


if __name__ == "__main__":
    main()
