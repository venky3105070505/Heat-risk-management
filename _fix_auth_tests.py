"""Update test_app.py login/signup helpers for email-based auth."""
with open("test_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix login helper: use email field instead of username
old_login = '''def login(client, username="admin", password="admin123"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


def login_as(client, role):
    """Log out then log in as a given role."""
    client.get("/logout", follow_redirects=True)  # ensure clean session
    creds = {
        "Administrator": ("admin",          "admin123"),
        "Health Officer": ("health_officer", "health123"),
        "Field Officer":  ("field_officer",  "field123"),
    }
    u, p = creds[role]
    return login(client, u, p)'''

new_login = '''def login(client, email="admin@healthdept.local", password=None):
    """Login with email. Password defaults to env var or the first-run generated one."""
    if password is None:
        # For tests, we need to know the admin password.
        # Use a test-only approach: create/reset admin via DB before tests.
        password = _ADMIN_PW
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=True)


def login_as(client, role):
    """Log out then log in as a pre-created test user for given role."""
    client.get("/logout", follow_redirects=True)
    creds = {
        "Administrator": ("admin@healthdept.local",       _ADMIN_PW),
        "Health Officer": ("test.health@healthdept.local", _STAFF_PW),
        "Field Officer":  ("test.field@healthdept.local",  _STAFF_PW),
    }
    em, pw = creds[role]
    return client.post("/login", data={"email": em, "password": pw},
                       follow_redirects=True)'''

content = content.replace(old_login, new_login)

# Fix test login assertions
content = content.replace(
    'assert b"Invalid" in resp.data or resp.status_code == 200',
    'assert b"Invalid" in resp.data or b"invalid" in resp.data or resp.status_code == 200'
)
content = content.replace(
    'data={"username": "admin", "password": "WRONG"}',
    'data={"email": "admin@healthdept.local", "password": "WRONG-PASSWORD"}'
)
content = content.replace(
    'data={"username": "", "password": ""}',
    'data={"email": "", "password": ""}'
)

with open("test_app.py", "w", encoding="utf-8") as f:
    f.write(content)

import ast
ast.parse(content)
print("test_app.py updated and syntax OK")
