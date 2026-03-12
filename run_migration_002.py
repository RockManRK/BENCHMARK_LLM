#!/usr/bin/env python3
"""Script para executar a migração 002_remove_reviewed_by.sql."""

import sqlite3
from pathlib import Path

DB_PATH = Path("./data/benchmark.db")
MIGRATION_PATH = Path("./migrations/002_remove_reviewed_by.sql")


def run_migration() -> None:
    """Executar a migração no banco de dados."""
    if not MIGRATION_PATH.exists():
        print(f"Erro: Arquivo de migração não encontrado: {MIGRATION_PATH}")
        return

    if not DB_PATH.exists():
        print(f"Erro: Banco de dados não encontrado: {DB_PATH}")
        return

    print(f"Banco de dados: {DB_PATH}")
    print(f"Migração: {MIGRATION_PATH}")
    print("-" * 60)

    # Ler o script de migração
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    # Conectar e executar
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # Executar todo o script SQL
        cursor.executescript(migration_sql)
        conn.commit()

        # Verificar resultado
        cursor.execute("SELECT COUNT(*) FROM responses")
        count = cursor.fetchone()[0]
        print(f"\n✅ Migração concluída com sucesso!")
        print(f"   Total de respostas na tabela: {count}")

        # Verificar estrutura da tabela
        print("\nEstrutura da tabela responses:")
        cursor.execute("PRAGMA table_info(responses)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")

        # Verificar se reviewed_by foi removida
        column_names = [col[1] for col in columns]
        if "reviewed_by" not in column_names:
            print("\n✅ reviewed_by foi removida com sucesso!")
        else:
            print("\n❌ reviewed_by ainda existe na tabela!")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"\n❌ Erro na migração: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
