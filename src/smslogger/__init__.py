import settings as items_settings
import sql_queries as items_queries


class DynamicSettings(type):
    ITEMS = {}

    def __call__(cls, *args, **kwargs):
        for item in dir(cls.ITEMS):
                if item.isupper():
                    setattr(cls, item, getattr(cls.ITEMS, item))
        return cls


class Settings(object):
    ITEMS = items_settings

    __metaclass__ = DynamicSettings

settings = Settings()


class Queries(object):
    ITEMS = items_queries

    __metaclass__ = DynamicSettings

queries = Queries()
