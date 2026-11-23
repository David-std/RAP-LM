"""Cloud-demo settings (render.yaml): driver normalisation and allowed origins."""

from raster_api.config import Settings


def test_managed_database_url_uses_psycopg_driver():
    s = Settings(database_url="postgresql://raplm_reader:x@host:5432/raplm?sslmode=require")
    assert s.sqlalchemy_url.startswith("postgresql+psycopg://raplm_reader:x@host")
    local = Settings(database_url="postgresql+psycopg://u:p@127.0.0.1:5433/raplm")
    assert local.sqlalchemy_url == local.database_url


def test_web_origin_host_becomes_https_origin():
    s = Settings(web_origin_host="raplm-web.onrender.com")
    assert "https://raplm-web.onrender.com" in s.allowed_origins
    assert Settings().allowed_origins == Settings().cors_origins
