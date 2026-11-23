"""One-step-ahead forecast of the published network (decision D-11).

Rows are batch outputs of ``ml.fused.forecast`` for the year after the last
observed one; they carry no observed record because none exists yet.

Revision ID: 0005
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

UPGRADE = r"""
CREATE TABLE forecast (
    run_id            varchar(60) NOT NULL REFERENCES model_run ON DELETE CASCADE,
    representation_id varchar(40) NOT NULL,
    unit_id           varchar(20) NOT NULL,
    horizon_year      integer NOT NULL,
    day_type          varchar(10) NOT NULL CHECK (day_type IN ('weekday', 'weekend')),
    band              smallint NOT NULL CHECK (band BETWEEN 0 AND 3),
    risk_index        double precision NOT NULL CHECK (risk_index BETWEEN 0 AND 100),
    risk_level        varchar(10) NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    index_low         double precision NOT NULL,
    index_high        double precision NOT NULL,
    previous_index    double precision NOT NULL,
    expected_events   double precision,
    PRIMARY KEY (run_id, representation_id, unit_id, horizon_year, day_type, band),
    FOREIGN KEY (representation_id, unit_id) REFERENCES spatial_unit,
    CHECK (index_low <= risk_index + 1e-6 AND risk_index <= index_high + 1e-6)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'raplm_reader') THEN
        GRANT SELECT ON forecast TO raplm_reader;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'raplm_publisher') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON forecast TO raplm_publisher;
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS forecast CASCADE;")
