import bcrypt

passwords = ["demo123", "manager123", "finops123"]

for p in passwords:
    hashed = bcrypt.hashpw(p.encode(), bcrypt.gensalt())
    print(p, "->", hashed)
