"""The base of the generated models (`mise run generate-schema` names it).

`defer_build` leaves building a model's validator until it is first used, so importing the
generated module creates its classes and builds none of them: a command pays for the models it
reads, not for all of them (ADR 0497).
"""

from pydantic import BaseModel as _PydanticModel
from pydantic import ConfigDict


class BaseModel(_PydanticModel):
    model_config = ConfigDict(defer_build=True)
