"""
DuckDB + LanceDB lakehouse setup for Intelli-Credit.
Provides unified SQL + vector query interface.
"""
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "storage" / "lakehouse.duckdb"


def get_connection(db_path: Optional[str] = None) -> duckdb.DuckDBPyConnection:
    """Get a DuckDB connection."""
    path = db_path or str(DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return duckdb.connect(path)


def init_schema(conn: Optional[duckdb.DuckDBPyConnection] = None) -> None:
    """Initialize the lakehouse schema."""
    if conn is None:
        conn = get_connection()

    conn.execute("""
    -- Documents table: raw document metadata
    CREATE TABLE IF NOT EXISTS documents (
        document_id VARCHAR PRIMARY KEY,
        source_file VARCHAR NOT NULL,
        document_type VARCHAR,
        company_name VARCHAR,
        upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        page_count INTEGER,
        file_size_bytes BIGINT,
        processing_status VARCHAR DEFAULT 'pending',
        metadata JSON
    );

    -- Extracted fields: individual field extractions with provenance
    CREATE TABLE IF NOT EXISTS extracted_fields (
        id INTEGER PRIMARY KEY DEFAULT(nextval('extracted_fields_seq')),
        document_id VARCHAR REFERENCES documents(document_id),
        field_name VARCHAR NOT NULL,
        field_value VARCHAR,
        field_type VARCHAR,
        page_number INTEGER,
        confidence DOUBLE,
        extraction_method VARCHAR,
        agent_id VARCHAR,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        provenance JSON
    );

    -- Entities: resolved entities (companies, people, GSTINs)
    CREATE TABLE IF NOT EXISTS entities (
        entity_id VARCHAR PRIMARY KEY,
        entity_type VARCHAR NOT NULL,  -- company, person, gstin, pan
        canonical_name VARCHAR NOT NULL,
        aliases JSON,  -- list of alternate names
        attributes JSON,  -- key-value pairs
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Transactions: financial transactions for graph construction
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id VARCHAR PRIMARY KEY,
        source_entity_id VARCHAR,
        target_entity_id VARCHAR,
        amount DOUBLE,
        currency VARCHAR DEFAULT 'INR',
        transaction_date DATE,
        transaction_type VARCHAR,
        document_id VARCHAR,
        provenance JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Risk scores: per-entity risk assessments
    CREATE TABLE IF NOT EXISTS risk_scores (
        id INTEGER PRIMARY KEY DEFAULT(nextval('risk_scores_seq')),
        entity_id VARCHAR,
        rule_id VARCHAR,
        rule_slug VARCHAR,
        risk_score DOUBLE,
        severity VARCHAR,
        flag_type VARCHAR,
        rationale TEXT,
        trace JSON,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Research findings: external research results
    CREATE TABLE IF NOT EXISTS research_findings (
        id INTEGER PRIMARY KEY DEFAULT(nextval('research_findings_seq')),
        entity_id VARCHAR,
        source_url VARCHAR,
        source_type VARCHAR,
        summary TEXT,
        sentiment_score DOUBLE,
        is_corroborated BOOLEAN DEFAULT FALSE,
        corroboration_sources JSON,
        provenance JSON,
        crawl_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Provenance log: append-only audit trail
    CREATE TABLE IF NOT EXISTS provenance_log (
        id INTEGER PRIMARY KEY DEFAULT(nextval('provenance_log_seq')),
        action VARCHAR NOT NULL,
        entity_type VARCHAR,
        entity_id VARCHAR,
        agent_id VARCHAR,
        details JSON,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- CAM outputs: generated Credit Appraisal Memos
    CREATE TABLE IF NOT EXISTS cam_outputs (
        cam_id VARCHAR PRIMARY KEY,
        entity_id VARCHAR,
        company_name VARCHAR,
        recommendation VARCHAR,  -- APPROVE, REJECT, CONDITIONAL
        loan_amount_recommended DOUBLE,
        risk_premium_bps INTEGER,
        five_cs JSON,
        rules_fired JSON,
        trace JSON,
        docx_path VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create sequences if they don't exist
    for seq in ['extracted_fields_seq', 'risk_scores_seq', 'research_findings_seq', 'provenance_log_seq']:
        try:
            conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1")
        except Exception:
            pass

    conn.commit()


def insert_document(conn, document_id: str, source_file: str,
                    document_type: str = None, company_name: str = None,
                    page_count: int = None, metadata: dict = None) -> None:
    """Insert a document record."""
    conn.execute("""
        INSERT INTO documents (document_id, source_file, document_type,
                              company_name, page_count, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [document_id, source_file, document_type, company_name,
          page_count, json.dumps(metadata) if metadata else None])


def insert_extracted_field(conn, document_id: str, field_name: str,
                           field_value: str, field_type: str = "string",
                           page_number: int = None, confidence: float = None,
                           extraction_method: str = None, agent_id: str = None,
                           provenance: dict = None) -> None:
    """Insert an extracted field record."""
    conn.execute("""
        INSERT INTO extracted_fields (document_id, field_name, field_value,
                                      field_type, page_number, confidence,
                                      extraction_method, agent_id, provenance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [document_id, field_name, field_value, field_type, page_number,
          confidence, extraction_method, agent_id,
          json.dumps(provenance) if provenance else None])


def log_provenance(conn, action: str, entity_type: str = None,
                   entity_id: str = None, agent_id: str = "system",
                   details: dict = None) -> None:
    """Append to the immutable provenance audit log."""
    conn.execute("""
        INSERT INTO provenance_log (action, entity_type, entity_id,
                                    agent_id, details)
        VALUES (?, ?, ?, ?, ?)
    """, [action, entity_type, entity_id, agent_id,
          json.dumps(details) if details else None])


def setup_lancedb(lance_dir: Optional[str] = None):
    """Initialize LanceDB for vector embeddings."""
    try:
        import lancedb
    except ImportError:
        print("LanceDB not installed. Install with: pip install lancedb")
        return None

    if lance_dir is None:
        lance_dir = str(PROJECT_ROOT / "storage" / "lancedb")

    os.makedirs(lance_dir, exist_ok=True)
    db = lancedb.connect(lance_dir)
    return db


def main():
    """Initialize the lakehouse schema."""
    print("Initializing DuckDB lakehouse...")
    conn = get_connection()
    init_schema(conn)
    print(f"Lakehouse initialized at: {DB_PATH}")

    # Show tables
    tables = conn.execute("SHOW TABLES").fetchall()
    print(f"Tables created: {[t[0] for t in tables]}")

    # Initialize LanceDB
    lance = setup_lancedb()
    if lance:
        print(f"LanceDB initialized at: {PROJECT_ROOT / 'storage' / 'lancedb'}")

    conn.close()


if __name__ == "__main__":
    main()
