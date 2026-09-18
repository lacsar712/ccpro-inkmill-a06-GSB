import re
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.color_match_ticket import (
    COLOR_MATCH_RESULTS,
    DELTA_E_PASS_THRESHOLD,
    ColorMatchTicket,
)
from app.models.mill import Mill
from app.serializers import color_match_ticket_json
from app.utils import error

bp = Blueprint("color_match_tickets", __name__, url_prefix="/api/color-match-tickets")

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _expected_result(delta_e: Decimal) -> str:
    return "pass" if delta_e <= DELTA_E_PASS_THRESHOLD else "fail"


def _parse_delta_e(raw) -> Decimal | None:
    """严格数值解析：拒绝非数值、NaN 与无穷。"""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None
    if value.is_nan() or value.is_infinite():
        return None
    return value


def _parse_mill_id(raw) -> int | None:
    """millId 可空；空值归一为 None，非法返回 0（视为无效）。"""
    if raw is None or raw == "":
        return None
    try:
        mill_id = int(raw)
    except (TypeError, ValueError):
        return 0
    return mill_id if mill_id > 0 else 0


def _validate(body: dict) -> str | None:
    ticket_no = str(body.get("ticketNo", "")).strip()
    if not ticket_no:
        return "比对单号不能为空"

    target_hex = str(body.get("targetHex", "")).strip()
    if not HEX_COLOR_RE.match(target_hex):
        return "目标色值格式应为 #RRGGBB"

    sample_hex = str(body.get("sampleHex", "")).strip()
    if not HEX_COLOR_RE.match(sample_hex):
        return "小样色值格式应为 #RRGGBB"

    delta_e = _parse_delta_e(body.get("deltaE"))
    if delta_e is None:
        return "ΔE 必须为数值"
    if delta_e < 0:
        return "ΔE 不能为负"

    result = str(body.get("result", "")).strip().lower()
    if result not in COLOR_MATCH_RESULTS:
        return "结果应为 pass 或 fail"
    if result != _expected_result(delta_e):
        return "结果与 ΔE 不一致：ΔE ≤ 2 必须为 pass，ΔE > 2 必须为 fail"

    mill_id = _parse_mill_id(body.get("millId"))
    if mill_id == 0:
        return "研磨机无效"
    if mill_id is not None:
        db = SessionLocal()
        try:
            if not db.get(Mill, mill_id):
                return "研磨机不存在"
        finally:
            db.close()

    return None


def _apply_body(row: ColorMatchTicket, body: dict) -> None:
    row.ticket_no = str(body["ticketNo"]).strip()
    row.target_hex = str(body["targetHex"]).strip().upper()
    row.sample_hex = str(body["sampleHex"]).strip().upper()
    row.delta_e = _parse_delta_e(body.get("deltaE"))
    row.result = str(body["result"]).strip().lower()
    row.mill_id = _parse_mill_id(body.get("millId"))


@bp.get("")
@jwt_required()
def list_tickets():
    result_filter = str(request.args.get("result", "")).strip().lower()
    if result_filter and result_filter not in COLOR_MATCH_RESULTS:
        return error("结果筛选应为 pass 或 fail", 400)

    db = SessionLocal()
    try:
        query = db.query(ColorMatchTicket)
        if result_filter:
            query = query.filter(ColorMatchTicket.result == result_filter)
        rows = query.order_by(ColorMatchTicket.id.desc()).all()
        return jsonify([color_match_ticket_json(r) for r in rows])
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_ticket():
    body = request.get_json(silent=True) or {}
    err = _validate(body)
    if err:
        return error(err, 400)

    db = SessionLocal()
    try:
        row = ColorMatchTicket()
        _apply_body(row, body)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return error("比对单号已存在", 400)
        db.refresh(row)
        return jsonify(color_match_ticket_json(row)), 201
    finally:
        db.close()


@bp.put("/<int:item_id>")
@jwt_required()
def update_ticket(item_id: int):
    body = request.get_json(silent=True) or {}
    err = _validate(body)
    if err:
        return error(err, 400)

    db = SessionLocal()
    try:
        row = db.get(ColorMatchTicket, item_id)
        if not row:
            return error("专色比对单不存在", 404)

        _apply_body(row, body)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return error("比对单号已存在", 400)
        db.refresh(row)
        return jsonify(color_match_ticket_json(row))
    finally:
        db.close()


@bp.delete("/<int:item_id>")
@jwt_required()
def delete_ticket(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(ColorMatchTicket, item_id)
        if not row:
            return error("专色比对单不存在", 404)
        db.delete(row)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
