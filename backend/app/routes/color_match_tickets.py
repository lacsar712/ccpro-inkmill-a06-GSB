import re
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.color_match_ticket import MATCH_RESULTS, PASS_MAX_DELTA_E, ColorMatchTicket
from app.models.mill import Mill
from app.serializers import color_match_ticket_json
from app.utils import error

bp = Blueprint("color_match_tickets", __name__, url_prefix="/api/color-match-tickets")

HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _norm_hex(value: object) -> str:
    """归一化为 #RRGGBB(大写)。调用前须已过 _validate。"""
    return "#" + str(value).strip().lstrip("#").upper()


def _expected_result(delta_e: Decimal) -> str:
    return "pass" if delta_e <= PASS_MAX_DELTA_E else "fail"


def _parse_mill_id(body: dict) -> int | None:
    raw = body.get("millId")
    if raw in (None, "", 0):
        return None
    return int(raw)


def _validate(body: dict) -> str | None:
    ticket_no = str(body.get("ticketNo", "")).strip()
    if not ticket_no:
        return "比对单号不能为空"

    if not HEX_RE.match(str(body.get("targetHex", "")).strip()):
        return "目标色须为 #RRGGBB 六位十六进制格式"
    if not HEX_RE.match(str(body.get("sampleHex", "")).strip()):
        return "小样色须为 #RRGGBB 六位十六进制格式"

    try:
        delta_e = Decimal(str(body.get("deltaE")))
    except (InvalidOperation, ValueError, TypeError):
        return "ΔE 必须为数字"
    if delta_e.is_nan() or delta_e.is_infinite():
        return "ΔE 必须为有限数字"
    if delta_e < 0:
        return "ΔE 不能为负数"

    result = str(body.get("result", "")).strip().lower()
    if result not in MATCH_RESULTS:
        return "判定结果须为 pass 或 fail"
    expected = _expected_result(delta_e)
    if result != expected:
        if expected == "pass":
            return "ΔE ≤ 2 时判定必须为 pass"
        return "ΔE > 2 时判定必须为 fail"

    try:
        mill_id = _parse_mill_id(body)
    except (ValueError, TypeError):
        return "研磨机选择无效"
    if mill_id is not None:
        if mill_id <= 0:
            return "研磨机选择无效"
        db = SessionLocal()
        try:
            if not db.get(Mill, mill_id):
                return "研磨机不存在"
        finally:
            db.close()

    return None


@bp.get("")
@jwt_required()
def list_tickets():
    result = str(request.args.get("result", "")).strip().lower()
    db = SessionLocal()
    try:
        query = db.query(ColorMatchTicket)
        if result:
            if result not in MATCH_RESULTS:
                return error("result 参数须为 pass 或 fail", 400)
            query = query.filter(ColorMatchTicket.result == result)
        rows = query.order_by(
            ColorMatchTicket.created_at.desc(), ColorMatchTicket.id.desc()
        ).all()
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
        row = ColorMatchTicket(
            ticket_no=str(body["ticketNo"]).strip(),
            target_hex=_norm_hex(body["targetHex"]),
            sample_hex=_norm_hex(body["sampleHex"]),
            delta_e=Decimal(str(body["deltaE"])),
            result=str(body["result"]).strip().lower(),
            mill_id=_parse_mill_id(body),
        )
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

        row.ticket_no = str(body["ticketNo"]).strip()
        row.target_hex = _norm_hex(body["targetHex"])
        row.sample_hex = _norm_hex(body["sampleHex"])
        row.delta_e = Decimal(str(body["deltaE"]))
        row.result = str(body["result"]).strip().lower()
        row.mill_id = _parse_mill_id(body)
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
