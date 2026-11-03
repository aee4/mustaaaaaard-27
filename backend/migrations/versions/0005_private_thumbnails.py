"""Private image derivatives and intrinsic dimensions; existing media retained."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("media_width", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("media_height", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("thumbnail_key", sa.String(255), nullable=True))
    op.add_column(
        "uploads",
        sa.Column("thumbnail_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_unique_constraint("uq_uploads_thumbnail_key", "uploads", ["thumbnail_key"])


def downgrade() -> None:
    op.drop_constraint("uq_uploads_thumbnail_key", "uploads", type_="unique")
    op.drop_column("uploads", "thumbnail_ready")
    op.drop_column("uploads", "thumbnail_key")
    op.drop_column("posts", "media_height")
    op.drop_column("posts", "media_width")
