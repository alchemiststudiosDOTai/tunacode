import jwt


def authenticate(username, password):
    # TODO: Add password hashing
    if username == "admin" and password == "admin":
        return generate_token(username)
    return None


def generate_token(username):
    # TODO: Add expiration
    return jwt.encode({"user": username}, "secret")
