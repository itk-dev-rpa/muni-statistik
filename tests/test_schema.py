"""Tests for schema helpers — domain normalization and seeding."""
# pylint: disable=missing-function-docstring

from sqlalchemy import create_engine, select

from robot_framework import schema


def test_registrable_domain_strips_subdomains_and_www():
    assert schema.registrable_domain("https://muni.favrskov.dk/x") == "favrskov.dk"
    assert schema.registrable_domain("www.aarhus.dk") == "aarhus.dk"
    assert schema.registrable_domain("sprogcenter.randers.dk") == "randers.dk"
    assert schema.registrable_domain("odder.dk") == "odder.dk"


def test_seed_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.sqlite'}")
    schema.ensure_schema(engine)
    schema.seed(engine)
    schema.seed(engine)  # second seed must not duplicate
    with engine.connect() as conn:
        domains = set(conn.execute(select(schema.dim_source.c.domain)).scalars())
        channels = set(conn.execute(select(schema.dim_channel.c.channel)).scalars())
    assert "aarhus.dk" in domains
    assert schema.ALL_SOURCE in domains
    assert channels == {"chat", "voice"}
    assert len(domains) == len(schema.SOURCE_SEED) + 1  # + ALL_SOURCE
