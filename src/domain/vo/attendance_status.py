from enum import StrEnum


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    BONUS = "bonus"
    EXCUSED = "excused"

    @property
    def display_symbol(self) -> str:
        return {
            self.PRESENT: "+",
            self.ABSENT: "Н",
            self.BONUS: "Б",
            self.EXCUSED: "У",
        }[self]

    @property
    def sheet_symbol(self) -> str:
        return "✓" if self is self.PRESENT else self.display_symbol
