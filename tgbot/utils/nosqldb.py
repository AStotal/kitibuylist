from typing import Dict, List, Optional

from tinydb import TinyDB, JSONStorage, Query
from tinydb.middlewares import CachingMiddleware

from tgbot.models.buy_models import BuyList, BuyItem


class Database:

    def __init__(self, filename):
        kwd = dict(
            sort_keys=True,
            indent=4,
            separators=(',', ': ')
        )
        self.db = TinyDB(filename, **kwd)
        self.db_lists = None
        self.q = Query()
        self.db_lists = self.db.table("buy_lists")
        self.items_editing = False
        self.lists_editing = False

    def full_initialize(self):
        self.db.drop_tables()
        self.db_lists = self.db.table("buy_lists")
        _id = self.create_list("Ololo")
        self.create_item("Cabbage", _id)
        self.create_item("Potato", _id)
        self.create_item("Flugengekhaimen", _id)

    def create_list(self, name: Optional[str]=None) -> int:
        if name is None:
            name = f"New list {len(self.db_lists) + 1}"
        new_list = BuyList(name=name, editing=True)

        return self.db_lists.insert(new_list.dict())

    def delete_list(self, list_id: int) -> List[int]:
        return self.db_lists.remove(doc_ids=[list_id])

    def create_item(self, name: str, list_id: int):
        active_list = self.list(list_id)
        active_list.add_item(BuyItem(name=name))
        self._update_list(active_list, list_id)

    def delete_item(self, name: str, list_id: int):
        active_list = self.list(list_id)
        active_list.delete(name)
        self._update_list(active_list, list_id)

    def switch_item(self, name: str, list_id: int):
        active_list = self.list(list_id)
        active_list.items[name].switch()
        self._update_list(active_list, list_id)

    def unarchive_list(self, list_id: int):
        active_list = self.list(list_id)
        active_list.archived = False
        self._update_list(active_list, list_id)

    def archive_list(self, list_id: int):
        active_list = self.list(list_id)
        active_list.archived = True
        self._update_list(active_list, list_id)

    def _update_list(self, buy_list: BuyList, doc_id: int):
        self.db_lists.update(buy_list.dict(), doc_ids=[doc_id])

    def lists(self) -> Dict[int, BuyList]:
        return {item.doc_id: BuyList(**item) for item in self.db_lists.all()}

    def list(self, list_id: int) -> Optional[BuyList]:
        result = self.db_lists.get(doc_id=list_id)
        if not result:
            return None
        return BuyList(**result)


if __name__ == '__main__':
    db = Database("db.json")
    db.initialize()
    l1 = db.create_list("List1")
    l2 = db.create_list("List2")
    db.create_item("it1", l1)
    db.create_item("it2", l2)
    db.switch_item("it2", l2)
    print(1)
