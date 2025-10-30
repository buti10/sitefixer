from modules.common.db import get_session
from modules.users.models import User
from modules.common.security import hash_password

s = get_session()

# Prüfen ob User existiert
u = s.query(User).filter(User.email.ilike('admin@sitefixer.de')).one_or_none()
if not u:
    print("Lege neuen Admin-User an...")
    u = User(
        email='admin@sitefixer.de',
        full_name='Admin',
        is_active=True,
        password_hash=hash_password('Nila2025/')
    )
    s.add(u)
    s.commit()
    print("User erstellt, ID:", u.id)
else:
    print("Setze Passwort für bestehenden User zurück...")
    u.password_hash = hash_password('Nila2025/')
    u.is_active = True
    s.commit()
    print("User aktualisiert, ID:", u.id)

print("Fertig.")
