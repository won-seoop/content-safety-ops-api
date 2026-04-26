from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.rule import Rule


SEED_RULES = [
    {
        "rule_name": "PREPAYMENT_KEYWORD",
        "keyword": "선입금",
        "score": 40,
        "action": "REVIEW",
        "category": "FRAUD",
    },
    {
        "rule_name": "EXTERNAL_CONTACT_KAKAO",
        "keyword": "카톡",
        "score": 30,
        "action": "REVIEW",
        "category": "EXTERNAL_CONTACT",
    },
    {
        "rule_name": "BANK_ACCOUNT_KEYWORD",
        "keyword": "계좌",
        "score": 30,
        "action": "REVIEW",
        "category": "FRAUD",
    },
    {
        "rule_name": "TOO_CHEAP_KEYWORD",
        "keyword": "급처",
        "score": 20,
        "action": "REVIEW",
        "category": "SPAM",
    },
    {
        "rule_name": "ILLEGAL_KEYWORD",
        "keyword": "불법",
        "score": 80,
        "action": "BLOCK",
        "category": "ILLEGAL",
    },
]


def seed_rules(db: Session) -> None:
    for rule_data in SEED_RULES:
        exists = db.query(Rule).filter(Rule.rule_name == rule_data["rule_name"]).first()
        if not exists:
            db.add(Rule(**rule_data))
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed_rules(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()

