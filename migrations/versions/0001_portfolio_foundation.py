"""Create the initial multi-asset portfolio ledger schema."""
from alembic import op
from alphafund.storage import Base
import alphafund.storage

revision = "0001_portfolio_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
