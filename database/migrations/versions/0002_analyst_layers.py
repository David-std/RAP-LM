"""Analyst layers: street corridors, unit explanations and model card (decision D-09).

All tables hold batch outputs of a published run; the API only reads them.

Revision ID: 0002
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UPGRADE = r"""
CREATE TABLE corridor (
    run_id          varchar(60) NOT NULL REFERENCES model_run ON DELETE CASCADE,
    corridor_id     varchar(80) NOT NULL,
    district_id     varchar(6) NOT NULL REFERENCES district,
    street          text NOT NULL,
    length_km       double precision NOT NULL CHECK (length_km > 0),
    events          double precision NOT NULL CHECK (events >= 0),
    events_per_km   double precision NOT NULL CHECK (events_per_km >= 0),
    rank            integer NOT NULL,
    cumulative_event_share double precision NOT NULL,
    injured         double precision NOT NULL,
    deceased        double precision NOT NULL,
    mean_risk_index double precision,
    by_family       jsonb NOT NULL,
    by_year         jsonb NOT NULL,
    by_subperiod    jsonb NOT NULL,
    located_via     jsonb NOT NULL,
    geom            geometry(MultiLineString, 4326) NOT NULL,
    PRIMARY KEY (run_id, corridor_id)
);
CREATE INDEX corridor_geom_gist ON corridor USING gist (geom);
CREATE INDEX corridor_rank ON corridor (run_id, rank);

CREATE TABLE unit_explanation (
    run_id            varchar(60) NOT NULL REFERENCES model_run ON DELETE CASCADE,
    representation_id varchar(40) NOT NULL,
    unit_id           varchar(20) NOT NULL,
    expected_events   jsonb NOT NULL,   -- aligned with model_card.series_years
    observed_events   jsonb NOT NULL,
    attribution       jsonb NOT NULL,   -- aligned with model_card.attribution_groups
    whatif            jsonb,            -- district partial dependence, null for cells
    PRIMARY KEY (run_id, representation_id, unit_id),
    FOREIGN KEY (representation_id, unit_id) REFERENCES spatial_unit
);

CREATE TABLE model_card (
    run_id              varchar(60) PRIMARY KEY REFERENCES model_run ON DELETE CASCADE,
    card                jsonb NOT NULL,
    series_years        jsonb NOT NULL,
    observing_family    jsonb NOT NULL,
    attribution_year    integer NOT NULL,
    attribution_groups  jsonb NOT NULL,
    whatif_factors      jsonb NOT NULL,
    whatif_variables    jsonb NOT NULL,
    corridor_summary    jsonb
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'raplm_reader') THEN
        GRANT SELECT ON corridor, unit_explanation, model_card TO raplm_reader;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'raplm_publisher') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON corridor, unit_explanation, model_card
            TO raplm_publisher;
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS corridor, unit_explanation, model_card CASCADE;")
