"""Optional post captions and normalized-caption retry fingerprints."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("caption", sa.String(280), nullable=True))
    op.add_column("uploads", sa.Column("caption_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("uploads", "caption_hash")
    op.drop_column("posts", "caption")
