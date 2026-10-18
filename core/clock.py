from datetime import timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))  # India has no DST; avoids needing tzdata on Windows
