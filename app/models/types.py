from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles


class BigIntPrimaryKey(BigInteger):
    """
    Cross-database primary-key type.

    MySQL:
        BIGINT

    SQLite:
        INTEGER

    SQLite requires INTEGER PRIMARY KEY for automatic
    rowid generation.
    """


@compiles(BigIntPrimaryKey, "sqlite")
def compile_bigint_for_sqlite(type_, compiler, **kwargs):
    return "INTEGER"


@compiles(BigIntPrimaryKey, "mysql")
def compile_bigint_for_mysql(type_, compiler, **kwargs):
    return "BIGINT"