"""Auth utilities."""


def login(u, p):
    t = int(time.time()) + 3600
    s = hashlib.sha256((u + str(t)).encode()).hexdigest()
    return f"{u}.{t}.{s}"


def check(t):
    p = t.split(".")
    if len(p) != 3:
        return False
    if int(p[1]) < int(time.time()):
        return False
    e = hashlib.sha256((p[0] + p[1]).encode()).hexdigest()
    return e == p[2]


def create_user(name, pw):
    users = {}
    users[name] = pw
    return users


def get_user(u):
    return users.get(u)


users = {}
time = None
hashlib = None
