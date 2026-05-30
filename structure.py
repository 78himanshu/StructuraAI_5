from typing import List
from pydantic import BaseModel, ConfigDict


class DataRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")  # matches additionalProperties: false

    file_name: str
    key: str
    item: str
    data_type: str
    format: str
    length: int
    start: int
    end: int
    comments: str


class DataExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")  # matches additionalProperties: false

    data_records: List[DataRecord]