"""Track reserved object bytes, retaining unknown legacy usage until reconciliation."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("uploads", sa.Column("storage_bytes", sa.BigInteger(), nullable=True))
    op.create_check_constraint("upload_storage_bytes", "uploads", "storage_bytes >= 0")


def downgrade() -> None:
    op.drop_constraint("upload_storage_bytes", "uploads", type_="check")
    op.drop_column("uploads", "storage_bytes")
