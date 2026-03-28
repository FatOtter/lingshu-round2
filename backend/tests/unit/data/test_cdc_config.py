"""Unit tests for Flink CDC configuration generator."""

import pytest

from lingshu.data.pipeline.cdc_config import CdcConfigGenerator, FlinkJobConfig


@pytest.fixture
def generator() -> CdcConfigGenerator:
    return CdcConfigGenerator(
        fdb_connection_string="fdb.cluster",
        iceberg_catalog="nessie_catalog",
        iceberg_warehouse="s3://warehouse/iceberg",
        doris_fe_host="doris-fe",
        doris_fe_port=8030,
        doris_user="root",
        doris_password="secret",
    )


class TestFdbToIcebergJob:
    def test_returns_flink_job_config(self, generator: CdcConfigGenerator) -> None:
        config = generator.generate_fdb_to_iceberg_job("tenant1.orders")
        assert isinstance(config, FlinkJobConfig)
        assert config.job_name == "fdb-to-iceberg-tenant1_orders"

    def test_sql_contains_source_and_sink(self, generator: CdcConfigGenerator) -> None:
        config = generator.generate_fdb_to_iceberg_job("tenant1.orders")
        combined = "\n".join(config.sql_statements)
        assert "foundationdb-cdc" in combined
        assert "iceberg" in combined
        assert "INSERT INTO" in combined

    def test_nessie_ref_propagated(self, generator: CdcConfigGenerator) -> None:
        config = generator.generate_fdb_to_iceberg_job("t.o", nessie_ref="dev-branch")
        combined = "\n".join(config.sql_statements)
        assert "'ref' = 'dev-branch'" in combined
        assert config.properties["nessie.ref"] == "dev-branch"

    def test_checkpointing_properties(self, generator: CdcConfigGenerator) -> None:
        config = generator.generate_fdb_to_iceberg_job("t.o")
        assert "execution.checkpointing.interval" in config.properties
        assert config.properties["execution.checkpointing.mode"] == "EXACTLY_ONCE"


class TestIcebergToDorisJob:
    def test_returns_flink_job_config(self, generator: CdcConfigGenerator) -> None:
        config = generator.generate_iceberg_to_doris_job("tenant1.orders", "ods_orders")
        assert isinstance(config, FlinkJobConfig)
        assert config.job_name == "iceberg-to-doris-tenant1_orders"

    def test_sql_contains_doris_connector(self, generator: CdcConfigGenerator) -> None:
        config = generator.generate_iceberg_to_doris_job("tenant1.orders", "ods_orders")
        combined = "\n".join(config.sql_statements)
        assert "'connector' = 'doris'" in combined
        assert "ods_orders" in combined
        assert "'username' = 'root'" in combined

    def test_doris_password_in_sink(self, generator: CdcConfigGenerator) -> None:
        config = generator.generate_iceberg_to_doris_job("t.o", "tbl")
        combined = "\n".join(config.sql_statements)
        assert "'password' = 'secret'" in combined

    def test_three_sql_statements(self, generator: CdcConfigGenerator) -> None:
        config = generator.generate_iceberg_to_doris_job("t.o", "tbl")
        assert len(config.sql_statements) == 3
