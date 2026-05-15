"""Schema consistency check script for CI/CD pipelines."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemaforge.convert import convert_schema
from schemaforge.check import check_directory


def main():
    """Check that all fixtures can be converted to all formats."""
    fixture_dir = os.path.join(os.path.dirname(__file__), "..", "fixtures")
    sql_path = os.path.join(fixture_dir, "sample.sql")

    if not os.path.exists(sql_path):
        print(f"Fixture not found: {sql_path}")
        return 1

    with open(sql_path) as f:
        sql = f.read()

    failures = 0
    formats = ["prisma", "drizzle", "typeorm", "django", "sqlalchemy", "json_schema", "graphql"]

    for fmt in formats:
        try:
            result = convert_schema(sql, "sql", fmt)
            out_path = os.path.join("/tmp", f"sample.{fmt}")
            with open(out_path, "w") as f:
                f.write(result)
            print(f"  OK: sql -> {fmt}")
        except Exception as e:
            print(f"  FAIL: sql -> {fmt}: {e}")
            failures += 1

    if failures:
        print(f"\n{failures} conversion(s) failed")
        return 1

    print("\nAll format conversions successful")
    return 0


if __name__ == "__main__":
    sys.exit(main())
