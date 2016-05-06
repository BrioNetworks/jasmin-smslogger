import settings as config


class Settings(object):
    def __init__(self):
        for setting in dir(config):
            if setting.isupper():
                setattr(self, setting, getattr(config, setting))

settings = Settings()
