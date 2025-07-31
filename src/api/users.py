from .auth import authenticate


class UserManager:
    def login(self, username, password):
        token = authenticate(username, password)
        # TODO: Store session
        return token
