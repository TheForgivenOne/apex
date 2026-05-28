import sqlite3
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Set

_model_registry: Set[Type["Model"]] = set()


class Database:
    def __init__(self, path: str = "apex.db"):
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self):
        if self._conn is None:
            dirname = os.path.dirname(self.path)
            if dirname:
                Path(dirname).mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self.connect()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


_default_db = Database()


def get_db() -> Database:
    return _default_db


def set_db_path(path: str):
    _default_db.path = path


class Field:
    def __init__(self, sql_type: str, default: Any = None, nullable: bool = False, unique: bool = False, primary_key: bool = False, references: Optional[str] = None):
        self.sql_type = sql_type
        self.default = default
        self.nullable = nullable
        self.unique = unique
        self.primary_key = primary_key
        self.references = references

    def to_sql(self) -> str:
        parts = [self.sql_type]
        if self.primary_key:
            parts.append("PRIMARY KEY")
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.references:
            parts.append(f"REFERENCES {self.references}")
        if self.default is not None:
            if isinstance(self.default, str):
                if self.default.upper() == self.default and "(" in self.default:
                    parts.append(f"DEFAULT {self.default}")
                else:
                    parts.append(f"DEFAULT '{self.default}'")
            else:
                parts.append(f"DEFAULT {self.default}")
        return " ".join(parts)


TYPE_MAP = {
    str: "TEXT",
    int: "INTEGER",
    float: "REAL",
    bool: "INTEGER",
    bytes: "BLOB",
}


class ModelMeta(type):
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        if name == "Model":
            return cls
        fields = {}
        annotations = attrs.get("__annotations__", {})
        for key, value in attrs.items():
            if isinstance(value, Field):
                fields[key] = value
        for key, py_type in annotations.items():
            if key.startswith("_"):
                continue
            if key in fields:
                continue
            if key == "id":
                fields[key] = Field("INTEGER", primary_key=True)
            else:
                sql_type = TYPE_MAP.get(py_type)
                if sql_type:
                    fields[key] = Field(sql_type)
        if "id" not in fields:
            fields["id"] = Field("INTEGER", primary_key=True)
        if "created_at" not in fields:
            fields["created_at"] = Field("TEXT", default="CURRENT_TIMESTAMP")
        cls._fields = fields
        tablename = attrs.get("__tablename__")
        if tablename:
            cls._tablename = tablename
        elif not hasattr(cls, '_tablename') or not cls._tablename:
            cls._tablename = name.lower() + "s"
        if fields:
            _model_registry.add(cls)
        return cls


class Model(metaclass=ModelMeta):
    _fields: Dict[str, Field] = {}
    _tablename: str = ""

    def __init__(self, **kwargs):
        self._data: Dict[str, Any] = {}
        for key in self._fields:
            setattr(self, key, kwargs.get(key, self._fields[key].default))
            if key in kwargs:
                self._data[key] = kwargs[key]

    @classmethod
    def create_table(cls):
        db = get_db()
        columns = [f"  {name} {field.to_sql()}" for name, field in cls._fields.items()]
        sql = f"CREATE TABLE IF NOT EXISTS {cls._tablename} (\n" + ",\n".join(columns) + "\n)"
        db.conn.execute(sql)
        db.conn.commit()

    @classmethod
    def all(cls) -> List[Dict[str, Any]]:
        db = get_db()
        cursor = db.conn.execute(f"SELECT * FROM {cls._tablename}")
        return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def get(cls, **kwargs) -> Optional[Dict[str, Any]]:
        db = get_db()
        if not kwargs:
            cursor = db.conn.execute(f"SELECT * FROM {cls._tablename} LIMIT 1")
        else:
            where = " AND ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values())
            cursor = db.conn.execute(f"SELECT * FROM {cls._tablename} WHERE {where}", values)
        row = cursor.fetchone()
        return dict(row) if row else None

    @classmethod
    def filter(cls, **kwargs) -> List[Dict[str, Any]]:
        db = get_db()
        if not kwargs:
            cursor = db.conn.execute(f"SELECT * FROM {cls._tablename}")
        else:
            where = " AND ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values())
            cursor = db.conn.execute(f"SELECT * FROM {cls._tablename} WHERE {where}", values)
        return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def count(cls, **kwargs) -> int:
        db = get_db()
        if kwargs:
            where = " AND ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values())
            cursor = db.conn.execute(f"SELECT COUNT(*) as c FROM {cls._tablename} WHERE {where}", values)
        else:
            cursor = db.conn.execute(f"SELECT COUNT(*) as c FROM {cls._tablename}")
        return cursor.fetchone()["c"]

    @classmethod
    def create(cls, **kwargs) -> Dict[str, Any]:
        db = get_db()
        fields = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        values = list(kwargs.values())
        cursor = db.conn.execute(
            f"INSERT INTO {cls._tablename} ({fields}) VALUES ({placeholders})", values
        )
        db.conn.commit()
        row_id = cursor.lastrowid
        if "id" in cls._fields:
            return cls.get(id=row_id)
        return kwargs

    @classmethod
    def update(cls, where: Dict[str, Any], values: Dict[str, Any]):
        db = get_db()
        set_clause = ", ".join(f"{k} = ?" for k in values)
        where_clause = " AND ".join(f"{k} = ?" for k in where)
        params = list(values.values()) + list(where.values())
        db.conn.execute(f"UPDATE {cls._tablename} SET {set_clause} WHERE {where_clause}", params)
        db.conn.commit()

    @classmethod
    def delete(cls, **kwargs):
        db = get_db()
        where = " AND ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values())
        db.conn.execute(f"DELETE FROM {cls._tablename} WHERE {where}", values)
        db.conn.commit()

    @classmethod
    def raw(cls, sql: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        db = get_db()
        cursor = db.conn.execute(sql, params or [])
        return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def execute(cls, sql: str, params: List[Any] = None):
        db = get_db()
        db.conn.execute(sql, params or [])
        db.conn.commit()


def init_db():
    for model_cls in list(_model_registry):
        model_cls.create_table()


def clear_model_registry():
    _model_registry.clear()
