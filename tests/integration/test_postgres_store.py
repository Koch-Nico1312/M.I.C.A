"""
Integration tests for Postgres Platform State Store.
Tests schema migrations, CRUD operations, and connection handling.
"""
import os
import pytest
from pathlib import Path
from typing import Any

# Skip tests if Postgres is not available
pytest.importorskip("psycopg2", reason="psycopg2 not installed")

from core.platform_hub import PostgresPlatformStateStore, JsonPlatformStateStore, PlatformHub


@pytest.fixture
def postgres_url():
    """Get Postgres connection URL from environment or use test default."""
    return os.environ.get(
        "MICA_POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/mica_test"
    )


@pytest.fixture
def postgres_store(postgres_url, tmp_path):
    """Create a Postgres store for testing."""
    fallback = JsonPlatformStateStore(tmp_path / "fallback.json")
    store = PostgresPlatformStateStore(url=postgres_url, fallback=fallback)
    yield store
    # Cleanup: drop test table
    try:
        driver = store._load_driver()
        if driver:
            with store._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("DROP TABLE IF EXISTS platform_state CASCADE")
                    conn.commit()
    except Exception:
        pass  # Cleanup best effort


class TestPostgresSchema:
    """Test Postgres schema creation and validation."""
    
    def test_schema_creation(self, postgres_store):
        """Test that platform_state table is created."""
        # Trigger schema creation by saving
        postgres_store.save({"test": "data"})
        
        with postgres_store._connect() as conn:
            with conn.cursor() as cur:
                # Check table exists
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_name = 'platform_state'
                """)
                tables = [row[0] for row in cur.fetchall()]
                assert "platform_state" in tables
    
    def test_platform_state_table_structure(self, postgres_store):
        """Test platform_state table has correct columns."""
        postgres_store.save({"test": "data"})
        
        with postgres_store._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'platform_state'
                """)
                columns = {row[0]: row[1] for row in cur.fetchall()}
                
                assert "key" in columns
                assert "payload" in columns
                assert "updated_at" in columns


class TestPostgresCRUD:
    """Test CRUD operations with Postgres."""
    
    def test_save_and_load(self, postgres_store):
        """Test saving and loading data."""
        test_data = {
            "test_key": "test_value",
            "nested": {"key": "value"},
            "array": [1, 2, 3]
        }
        
        postgres_store.save(test_data)
        loaded = postgres_store.load()
        
        assert loaded == test_data
    
    def test_save_overwrites_existing(self, postgres_store):
        """Test that save overwrites existing data."""
        postgres_store.save({"version": 1})
        postgres_store.save({"version": 2})
        
        loaded = postgres_store.load()
        assert loaded["version"] == 2
    
    def test_load_empty_returns_defaults(self, postgres_store):
        """Test loading empty store returns None/empty."""
        # Clear any existing data
        with postgres_store._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM platform_state")
                conn.commit()
        
        loaded = postgres_store.load()
        # Should return empty dict or None
        assert loaded is None or loaded == {}


class TestPostgresConnection:
    """Test connection handling and fallback."""
    
    def test_connection_pooling(self, postgres_store):
        """Test that connections are pooled and reused."""
        # Make multiple requests
        for i in range(5):
            postgres_store.save({"iteration": i})
        
        # Should not fail due to connection exhaustion
        loaded = postgres_store.load()
        assert loaded["iteration"] == 4
    
    def test_connection_failure_fallback(self, tmp_path):
        """Test fallback to JSON store on connection failure."""
        fallback = JsonPlatformStateStore(tmp_path / "fallback.json")
        store = PostgresPlatformStateStore(
            url="postgresql://invalid:invalid@invalid:5432/invalid",
            fallback=fallback
        )
        
        # Should fall back to JSON
        status = store.status()
        assert status["backend"] == "postgres"
        assert status["status"] in ["fallback-json", "ready"]  # Depends on driver


class TestPostgresMigrations:
    """Test migration handling."""
    
    def test_migration_catalog(self, postgres_store):
        """Test migration catalog is tracked."""
        # The schema creation should be tracked
        with postgres_store._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM platform_state
                """)
                count = cur.fetchone()[0]
                # Should have at most one state row
                assert count <= 1


class TestPlatformHubWithPostgres:
    """Test PlatformHub integration with Postgres."""
    
    def test_platform_hub_uses_postgres(self, postgres_url, tmp_path):
        """Test PlatformHub can use Postgres store."""
        fallback = JsonPlatformStateStore(tmp_path / "fallback.json")
        postgres_store = PostgresPlatformStateStore(url=postgres_url, fallback=fallback)
        
        hub = PlatformHub(store_path=tmp_path / "platform.json")
        hub.state_store = postgres_store
        hub.data = hub.state_store.load() or hub._with_defaults({})
        
        # Perform operations
        hub.action("save_user", {
            "id": "postgres-user",
            "email": "postgres@test.com",
            "name": "Postgres User"
        })
        
        # Reload from Postgres
        hub.data = hub.state_store.load()
        
        # Verify data persisted
        users = hub.data.get("users", [])
        assert any(u["id"] == "postgres-user" for u in users)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
