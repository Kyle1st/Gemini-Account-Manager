import secrets
import string


def generate_password(
    length: int = 16,
    use_uppercase: bool = True,
    use_lowercase: bool = True,
    use_digits: bool = True,
    use_special: bool = True,
) -> str:
    """Generate a cryptographically secure random password."""
    if length < 4:
        raise ValueError("Password length must be at least 4")

    char_pools = []
    required_chars = []

    if use_uppercase:
        pool = string.ascii_uppercase
        char_pools.append(pool)
        required_chars.append(secrets.choice(pool))
    if use_lowercase:
        pool = string.ascii_lowercase
        char_pools.append(pool)
        required_chars.append(secrets.choice(pool))
    if use_digits:
        pool = string.digits
        char_pools.append(pool)
        required_chars.append(secrets.choice(pool))
    if use_special:
        pool = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        char_pools.append(pool)
        required_chars.append(secrets.choice(pool))

    if not char_pools:
        raise ValueError("At least one character type must be enabled")

    all_chars = "".join(char_pools)
    remaining = length - len(required_chars)
    password_chars = required_chars + [secrets.choice(all_chars) for _ in range(remaining)]

    rng = secrets.SystemRandom()
    rng.shuffle(password_chars)

    return "".join(password_chars)
