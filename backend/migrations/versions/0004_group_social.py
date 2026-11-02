"""Private group welcome content, likes, comments and account tour progress."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("posts", "user_id", existing_type=sa.Uuid(), nullable=True)
    for column in (
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("posts.id")),
        sa.Column("title", sa.String(100)),
        sa.Column("seed_key", sa.String(80)),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    ):
        op.add_column("posts", column)
    op.create_index("ix_posts_parent_id", "posts", ["parent_id"])
    op.create_unique_constraint("uq_group_seed", "posts", ["group_id", "seed_key"])
    op.drop_constraint("post_source", "posts", type_="check")
    op.create_check_constraint(
        "post_source",
        "posts",
        "(source = 'capture' AND capture_id IS NOT NULL AND user_id IS NOT NULL) OR "
        "(source = 'gallery' AND capture_id IS NULL AND user_id IS NOT NULL) OR "
        "(source = 'system' AND capture_id IS NULL AND user_id IS NULL)",
    )
    op.create_table(
        "post_likes",
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("text", sa.String(500)),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("post_id", "user_id", "idempotency_key", name="uq_comment_retry"),
    )
    op.create_index("ix_comments_post_id", "comments", ["post_id"])
    op.create_index("ix_comments_page", "comments", ["post_id", "created_at", "id"])
    op.create_table(
        "tour_progress",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    # System content cannot safely be coerced into a member's post.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM posts WHERE source='system')")):
        raise RuntimeError("Remove system content explicitly before downgrading")
    op.drop_table("tour_progress")
    op.drop_table("comments")
    op.drop_table("post_likes")
    op.drop_constraint("post_source", "posts", type_="check")
    op.create_check_constraint(
        "post_source",
        "posts",
        "(source = 'capture' AND capture_id IS NOT NULL) OR (source = 'gallery' AND capture_id IS NULL)",
    )
    op.drop_constraint("uq_group_seed", "posts", type_="unique")
    op.drop_index("ix_posts_parent_id", "posts")
    for name in ("pinned", "seed_key", "title", "parent_id"):
        op.drop_column("posts", name)
    op.alter_column("posts", "user_id", existing_type=sa.Uuid(), nullable=False)
