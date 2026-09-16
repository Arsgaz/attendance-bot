import hashlib
import json


def lesson_row_fingerprint(
    *,
    date_value: object,
    subject: object,
    subgroup: object,
    sequence_number: int,
) -> str:
    canonical = json.dumps(
        [
            _normalize(date_value),
            _normalize(subject),
            _normalize(subgroup),
            str(sequence_number),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _normalize(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).strip().split()).casefold()
