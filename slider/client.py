from .game_mode import GameMode


class Client:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_user(self,
                 user,
                 *,
                 mode=GameMode.standard,
                 type_=None,
                 event_days=1):
        pass
