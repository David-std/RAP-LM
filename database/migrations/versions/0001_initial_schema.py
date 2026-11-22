"""Initial PostGIS schema for published analytical results.

WBS 3.1.4 / 3.3.2, HT-04 / HT-10 (RT-03, RD-03, RD-04). Implements the entities
of docs/contracts/persistence-and-publication.md. Public geometry is stored in
EPSG:4326 (the common SRID served as GeoJSON); analysis happens in EPSG:32718
inside the batch pipeline and is recorded per spatial representation.

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE = r"""
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE district (
    district_id   varchar(6) PRIMARY KEY CHECK (district_id ~ '^1501[0-9]{2}$'),
    name          text NOT NULL,
    area_km2      double precision NOT NULL CHECK (area_km2 > 0),
    geom          geometry(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(geom))
);
CREATE INDEX district_geom_gist ON district USING gist (geom);

CREATE TABLE spatial_representation (
    representation_id  varchar(40) PRIMARY KEY,
    unit_type          varchar(10) NOT NULL CHECK (unit_type IN ('cell', 'district')),
    label              text NOT NULL,
    resolution_m       integer,
    analysis_crs       varchar(20) NOT NULL,
    grid_spec          jsonb,
    district_relation_rule text NOT NULL
);

CREATE TABLE spatial_unit (
    representation_id varchar(40) NOT NULL REFERENCES spatial_representation,
    unit_id        varchar(20) NOT NULL,
    unit_type      varchar(10) NOT NULL CHECK (unit_type IN ('cell', 'district')),
    display_name   text NOT NULL,
    district_id    varchar(6) NOT NULL REFERENCES district,
    grid_row       integer,
    grid_col       integer,
    area_km2       double precision NOT NULL CHECK (area_km2 > 0),
    geom           geometry(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    PRIMARY KEY (representation_id, unit_id)
);
CREATE INDEX spatial_unit_geom_gist ON spatial_unit USING gist (geom);
CREATE INDEX spatial_unit_district ON spatial_unit (representation_id, district_id);

CREATE TABLE unit_district_relation (
    representation_id varchar(40) NOT NULL,
    unit_id       varchar(20) NOT NULL,
    district_id   varchar(6) NOT NULL REFERENCES district,
    area_fraction double precision NOT NULL CHECK (area_fraction > 0 AND area_fraction <= 1),
    PRIMARY KEY (representation_id, unit_id, district_id),
    FOREIGN KEY (representation_id, unit_id) REFERENCES spatial_unit
);

CREATE TABLE analysis_period (
    period_id    varchar(24) PRIMARY KEY,
    year         integer NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    day_type     varchar(10) NOT NULL CHECK (day_type IN ('weekday', 'weekend')),
    time_band    smallint NOT NULL CHECK (time_band BETWEEN 0 AND 3),
    start_date   date NOT NULL,
    end_date     date NOT NULL,
    start_hour   smallint NOT NULL,
    end_hour     smallint NOT NULL,
    granularity  text NOT NULL,
    label        text NOT NULL,
    CHECK (end_date > start_date),
    UNIQUE (year, day_type, time_band)
);

CREATE TABLE source_snapshot (
    source_id        varchar(60) PRIMARY KEY,
    publisher        text NOT NULL,
    name             text NOT NULL,
    url              text,
    licence          text NOT NULL,
    captured_at      date,
    sha256           varchar(64),
    coverage_start   date,
    coverage_end     date,
    spatial_coverage text NOT NULL,
    population       text NOT NULL,
    incorporated     boolean NOT NULL,
    exclusion_reason text,
    CHECK (incorporated OR exclusion_reason IS NOT NULL)
);

CREATE TABLE dataset_version (
    dataset_version_id varchar(40) PRIMARY KEY,
    manifest           jsonb NOT NULL,
    manifest_sha256    varchar(64) NOT NULL,
    created_at         timestamptz NOT NULL
);

CREATE TABLE variable (
    variable_id     varchar(40) PRIMARY KEY,
    label           text NOT NULL,
    concept_group   varchar(12) NOT NULL
        CHECK (concept_group IN ('occurrence', 'severity', 'exposure', 'context')),
    unit            text NOT NULL,
    source_id       varchar(60) REFERENCES source_snapshot,
    reference_period text NOT NULL,
    description     text NOT NULL,
    incorporated    boolean NOT NULL
);

CREATE TABLE limitation (
    limitation_id varchar(40) PRIMARY KEY,
    dimension     text NOT NULL,
    description   text NOT NULL
);

CREATE TABLE target_definition (
    target_definition_id varchar(40) PRIMARY KEY,
    population   text NOT NULL,
    definition   text NOT NULL,
    value_unit   text NOT NULL,
    index_method text NOT NULL
);

CREATE TABLE threshold_set (
    threshold_set_id varchar(40) PRIMARY KEY,
    version     text NOT NULL,
    low_max     double precision NOT NULL,
    medium_max  double precision NOT NULL,
    method      text NOT NULL,
    frozen_at   timestamptz NOT NULL,
    CHECK (0 < low_max AND low_max < medium_max AND medium_max < 100)
);

CREATE TABLE model_run (
    run_id               varchar(60) PRIMARY KEY,
    status               varchar(12) NOT NULL
        CHECK (status IN ('staged', 'published', 'rejected', 'superseded')),
    is_demo              boolean NOT NULL DEFAULT false,
    dataset_version_id   varchar(40) NOT NULL REFERENCES dataset_version,
    target_definition_id varchar(40) NOT NULL REFERENCES target_definition,
    threshold_set_id     varchar(40) NOT NULL REFERENCES threshold_set,
    model_family         text NOT NULL,
    code_commit_sha      varchar(40) NOT NULL,
    seed                 integer NOT NULL,
    config               jsonb NOT NULL,
    split                jsonb NOT NULL,
    metrics              jsonb NOT NULL,
    artifact_sha256      varchar(64) NOT NULL,
    results_sha256       varchar(64) NOT NULL,
    created_at           timestamptz NOT NULL,
    published_at         timestamptz
);

CREATE TABLE run_source (
    run_id    varchar(60) REFERENCES model_run ON DELETE CASCADE,
    source_id varchar(60) REFERENCES source_snapshot,
    PRIMARY KEY (run_id, source_id)
);
CREATE TABLE run_variable (
    run_id      varchar(60) REFERENCES model_run ON DELETE CASCADE,
    variable_id varchar(40) REFERENCES variable,
    PRIMARY KEY (run_id, variable_id)
);
CREATE TABLE run_limitation (
    run_id        varchar(60) REFERENCES model_run ON DELETE CASCADE,
    limitation_id varchar(40) REFERENCES limitation,
    PRIMARY KEY (run_id, limitation_id)
);
CREATE TABLE run_period (
    run_id     varchar(60) REFERENCES model_run ON DELETE CASCADE,
    period_id  varchar(24) REFERENCES analysis_period,
    partition  varchar(10) NOT NULL CHECK (partition IN ('train', 'validation', 'test', 'context')),
    observing_sources text[] NOT NULL,
    PRIMARY KEY (run_id, period_id)
);

CREATE TABLE risk_result (
    run_id            varchar(60) NOT NULL REFERENCES model_run ON DELETE CASCADE,
    representation_id varchar(40) NOT NULL,
    unit_id           varchar(20) NOT NULL,
    period_id         varchar(24) NOT NULL REFERENCES analysis_period,
    availability      varchar(30) NOT NULL
        CHECK (availability IN ('estimated', 'no_result', 'outside_source_coverage')),
    indicator_value   double precision CHECK (indicator_value IS NULL OR indicator_value >= 0),
    risk_index        double precision CHECK (risk_index IS NULL OR risk_index BETWEEN 0 AND 100),
    risk_level        varchar(6) CHECK (risk_level IN ('low', 'medium', 'high')),
    historical_average double precision,
    observed_events   double precision,
    observed_injured  integer,
    observed_deceased integer,
    PRIMARY KEY (run_id, representation_id, unit_id, period_id),
    FOREIGN KEY (representation_id, unit_id) REFERENCES spatial_unit,
    CHECK ((availability = 'estimated') = (indicator_value IS NOT NULL)),
    CHECK ((indicator_value IS NULL) = (risk_level IS NULL)),
    CHECK ((indicator_value IS NULL) = (risk_index IS NULL))
);
CREATE INDEX risk_result_run_period ON risk_result (run_id, representation_id, period_id);
CREATE INDEX risk_result_run_unit ON risk_result (run_id, representation_id, unit_id);

CREATE TABLE publication_pointer (
    pointer_key  varchar(10) PRIMARY KEY CHECK (pointer_key = 'active'),
    run_id       varchar(60) NOT NULL REFERENCES model_run,
    activated_at timestamptz NOT NULL
);

CREATE TABLE publication_log (
    log_id     bigserial PRIMARY KEY,
    run_id     varchar(60) NOT NULL,
    action     text NOT NULL,
    detail     jsonb NOT NULL,
    logged_at  timestamptz NOT NULL DEFAULT now()
);

-- Only a run that is 'published' can be the active one.
CREATE FUNCTION check_active_run() RETURNS trigger AS $$
BEGIN
    IF (SELECT status FROM model_run WHERE run_id = NEW.run_id) <> 'published' THEN
        RAISE EXCEPTION 'run % is not published', NEW.run_id;
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER publication_pointer_published
    BEFORE INSERT OR UPDATE ON publication_pointer
    FOR EACH ROW EXECUTE FUNCTION check_active_run();
"""

GRANTS = r"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'raplm_reader') THEN
        GRANT USAGE ON SCHEMA public TO raplm_reader;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO raplm_reader;
        REVOKE SELECT ON publication_log FROM raplm_reader;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'raplm_publisher') THEN
        GRANT USAGE ON SCHEMA public TO raplm_publisher;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO raplm_publisher;
        GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO raplm_publisher;
    END IF;
END $$;
"""

DOWNGRADE = r"""
DROP TABLE IF EXISTS publication_log, publication_pointer, risk_result, run_period,
    run_limitation, run_variable, run_source, model_run, threshold_set, target_definition,
    limitation, variable, dataset_version, source_snapshot, analysis_period,
    unit_district_relation, spatial_unit, spatial_representation, district CASCADE;
DROP FUNCTION IF EXISTS check_active_run();
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute(DOWNGRADE)
