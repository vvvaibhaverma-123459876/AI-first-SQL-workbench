"""Create deterministic synthetic analytics demo data and metadata DB."""
from __future__ import annotations
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
ANALYTICS_DB = DATA_DIR / "demo_analytics.db"
METADATA_DB = DATA_DIR / "app_metadata.db"

FIRST_NAMES = ["Ava", "Noah", "Liam", "Mia", "Emma", "Arjun", "Sophia", "Ivy", "Kai", "Zara", "Lucas", "Nina"]
LAST_NAMES = ["Patel", "Kim", "Brown", "Singh", "Lopez", "Garcia", "Taylor", "Chen", "Martin", "Reed"]
COUNTRIES = ["India", "United States", "United Kingdom", "Singapore", "Germany"]
CARD_TYPES = ["standard", "gold", "platinum"]
TXN_TYPES = ["purchase", "refund", "billpay", "cashback"]
TXN_STATUS = ["success", "failed", "pending"]
CHANNELS = ["organic", "search", "partner", "influencer", "referral"]
EVENT_STEPS = ["signup", "phone_verify", "kyc_start", "kyc_complete", "card_approved", "card_shipped"]
TICKET_CATEGORIES = ["payments", "kyc", "card", "app", "charges"]
TICKET_STATUS = ["open", "resolved", "waiting"]


def build():
    random.seed(42)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ANALYTICS_DB.exists():
        ANALYTICS_DB.unlink()
    if METADATA_DB.exists():
        METADATA_DB.unlink()

    conn = sqlite3.connect(ANALYTICS_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            country TEXT NOT NULL,
            signup_date TEXT NOT NULL,
            marketing_channel TEXT NOT NULL,
            is_active INTEGER NOT NULL
        );

        CREATE TABLE cards (
            card_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            card_type TEXT NOT NULL,
            status TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            credit_limit REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE referrals (
            referral_id INTEGER PRIMARY KEY,
            referrer_user_id INTEGER NOT NULL,
            referred_user_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (referrer_user_id) REFERENCES users(user_id),
            FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
        );

        CREATE TABLE transactions (
            transaction_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            card_id INTEGER,
            transaction_type TEXT NOT NULL,
            status TEXT NOT NULL,
            amount REAL NOT NULL,
            merchant TEXT NOT NULL,
            transaction_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (card_id) REFERENCES cards(card_id)
        );

        CREATE TABLE onboarding_events (
            event_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            status TEXT NOT NULL,
            event_at TEXT NOT NULL,
            metadata_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE support_tickets (
            ticket_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        """
    )

    start_date = datetime.now() - timedelta(days=210)
    user_count = 900
    card_id = 1
    txn_id = 1
    event_id = 1
    ticket_id = 1
    referral_id = 1

    for user_id in range(1, user_count + 1):
        full_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        email = f"user{user_id}@example.com"
        signup_dt = start_date + timedelta(days=random.randint(0, 180), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        channel = random.choice(CHANNELS)
        country = random.choice(COUNTRIES)
        is_active = 1 if random.random() > 0.12 else 0
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, full_name, email, country, signup_dt.isoformat(), channel, is_active),
        )

        if user_id > 20 and random.random() < 0.35:
            referrer = random.randint(1, user_id - 1)
            cur.execute(
                "INSERT INTO referrals VALUES (?, ?, ?, ?, ?)",
                (referral_id, referrer, user_id, channel, (signup_dt - timedelta(days=random.randint(0, 10))).isoformat()),
            )
            referral_id += 1

        issued_at = signup_dt + timedelta(days=random.randint(1, 21))
        card_count = 1 if random.random() > 0.22 else 0
        user_card_ids: list[int] = []
        for _ in range(card_count):
            ctype = random.choice(CARD_TYPES)
            status = random.choice(["approved", "active", "blocked", "closed"])
            limit_value = random.choice([5000, 10000, 20000, 50000, 75000])
            cur.execute(
                "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?)",
                (card_id, user_id, ctype, status, issued_at.isoformat(), limit_value),
            )
            user_card_ids.append(card_id)
            card_id += 1

        last_event_time = signup_dt
        for step in EVENT_STEPS:
            last_event_time += timedelta(hours=random.randint(1, 72))
            status = "success" if random.random() > 0.15 else "failed"
            cur.execute(
                "INSERT INTO onboarding_events VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, user_id, step, status, last_event_time.isoformat(), '{"source": "seed"}'),
            )
            event_id += 1
            if status == "failed" and random.random() > 0.5:
                break

        txn_count = random.randint(5, 35)
        for _ in range(txn_count):
            txn_at = signup_dt + timedelta(days=random.randint(0, 200), hours=random.randint(0, 23))
            amount = round(random.uniform(50, 25000), 2)
            t_status = random.choices(TXN_STATUS, weights=[0.82, 0.1, 0.08])[0]
            t_type = random.choice(TXN_TYPES)
            merchant = random.choice(["Grocer", "Airline", "Coffee", "Pharmacy", "Marketplace", "TravelApp", "UtilityCo"])
            chosen_card = random.choice(user_card_ids) if user_card_ids else None
            cur.execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (txn_id, user_id, chosen_card, t_type, t_status, amount, merchant, txn_at.isoformat()),
            )
            txn_id += 1

        if random.random() < 0.35:
            for _ in range(random.randint(1, 3)):
                created_at = signup_dt + timedelta(days=random.randint(0, 180))
                status = random.choice(TICKET_STATUS)
                resolved_at = created_at + timedelta(days=random.randint(1, 6)) if status == "resolved" else None
                cur.execute(
                    "INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        ticket_id,
                        user_id,
                        random.choice(TICKET_CATEGORIES),
                        random.choice(["low", "medium", "high"]),
                        status,
                        created_at.isoformat(),
                        resolved_at.isoformat() if resolved_at else None,
                    ),
                )
                ticket_id += 1

    conn.commit()
    conn.close()

    meta = sqlite3.connect(METADATA_DB)
    meta.executescript(
        """
        CREATE TABLE saved_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sql_text TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sql_text TEXT NOT NULL,
            status TEXT NOT NULL,
            row_count INTEGER DEFAULT 0,
            execution_ms INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    meta.commit()
    meta.close()
    print(f"Seeded analytics DB at {ANALYTICS_DB}")
    print(f"Seeded metadata DB at {METADATA_DB}")


if __name__ == "__main__":
    build()
