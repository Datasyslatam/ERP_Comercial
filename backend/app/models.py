"""Registro único de modelos: importarlo garantiza que Base.metadata contenga todas las tablas."""
from app.core.db import Base  # noqa: E402
from app.modules.accounting.models import *  # noqa: F401,F403
from app.modules.documents.models import *  # noqa: F401,F403
from app.modules.einvoicing.models import *  # noqa: F401,F403
from app.modules.iam.models import *  # noqa: F401,F403
from app.modules.imports.models import *  # noqa: F401,F403
from app.modules.inventory.models import *  # noqa: F401,F403
from app.modules.kpi.models import *  # noqa: F401,F403
from app.modules.logistics.models import *  # noqa: F401,F403
from app.modules.masters.models import *  # noqa: F401,F403
from app.modules.operations.models import *  # noqa: F401,F403
from app.modules.org.models import *  # noqa: F401,F403
from app.modules.purchasing.models import *  # noqa: F401,F403
from app.modules.quality.models import *  # noqa: F401,F403
from app.modules.sales.models import *  # noqa: F401,F403

metadata = Base.metadata
