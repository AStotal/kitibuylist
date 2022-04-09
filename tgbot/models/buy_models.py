from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field


class BuyItem(BaseModel):
    name: str
    is_taken: bool = False

    @property
    def status(self):
        return "✅" if self.is_taken else ""

    def switch(self):
        self.is_taken = not self.is_taken


class BuyList(BaseModel):
    name: str
    archived: bool = False
    items: Dict[str, BuyItem] = Field(default_factory=dict)

    @property
    def status(self):
        return "🔒" if self.archived else ""

    def get_item(self, name: str):
        return self.items.get(name)

    def delete(self, item):
        self.items.pop(item)

    def add_item(self, item):
        self.items[item.name] = item
