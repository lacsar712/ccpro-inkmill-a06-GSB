from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

COLOR_MATCH_RESULTS = ("pass", "fail")

# ΔE ≤ 2 判合格(pass)，> 2 判不合格(fail)
DELTA_E_PASS_THRESHOLD = Decimal("2")


class ColorMatchTicket(Base):
    __tablename__ = "color_match_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    target_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    sample_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    delta_e: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    mill_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("mills.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    mill: Mapped["Mill | None"] = relationship("Mill", back_populates="color_match_tickets")
