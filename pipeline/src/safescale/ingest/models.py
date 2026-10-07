"""Pydantic models for raw CPSC Recalls API records (only the fields we use)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Raw(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RawNamed(_Raw):
    Name: str = ""


class RawProduct(_Raw):
    Name: str = ""
    Type: str = ""
    NumberOfUnits: str = ""


class RawCountry(_Raw):
    Country: str = ""


class RawRecall(_Raw):
    RecallID: int
    RecallNumber: str | None = None
    RecallDate: datetime
    LastPublishDate: datetime | None = None
    Title: str = Field(pattern=r"\S")
    Description: str | None = None
    URL: str = Field(pattern=r"\S")
    Products: list[RawProduct] = []
    Hazards: list[RawNamed] = []
    Injuries: list[RawNamed] = []
    Remedies: list[RawNamed] = []
    ManufacturerCountries: list[RawCountry] = []
