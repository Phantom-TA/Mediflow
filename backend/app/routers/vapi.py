import json
import logging
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import get_settings
from app.schemas.tools import (
    VapiWebhookRequest,
    VapiWebhookResponse,
    VapiToolResult,
    APIResponse,
    FindDoctorsRequest,
    CheckAvailabilityRequest,
    RecommendAlternativesRequest,
    BookAppointmentRequest,
    RescheduleAppointmentRequest,
    CancelAppointmentRequest,
    FindPatientAppointmentsRequest,
)

# Reuse the endpoint logic inside routers/tools.py to execute the calls
from app.routers.tools import (
    find_doctors,
    check_availability,
    recommend_alternatives,
    book_appointment_endpoint,
    reschedule_appointment_endpoint,
    cancel_appointment_endpoint,
    find_patient_appointments,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def log_webhook_to_db(db: Session, headers: dict, payload: dict, response: dict | None = None, error: str | None = None):
    try:
        query = text("""
            INSERT INTO webhook_logs (headers, payload, response, error)
            VALUES (:headers, :payload, :response, :error)
        """)
        db.execute(query, {
            "headers": json.dumps(headers),
            "payload": json.dumps(payload),
            "response": json.dumps(response) if response else None,
            "error": error
        })
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log webhook to db: {e}")


@router.post("/tool")
async def vapi_tool_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_vapi_secret: str | None = Header(None, alias="X-Vapi-Secret")
):
    """
    Unified Vapi webhook handler for tool calls.
    Logs every request and response to a persistent DB table for remote diagnostics.
    """
    headers = dict(request.headers)
    
    body_bytes = b""
    # 1. Parse Raw Body
    try:
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        payload = json.loads(body_str) if body_str else {}
    except Exception as e:
        raw_body = body_bytes.decode("utf-8", errors="ignore")
        log_webhook_to_db(db, headers, {"raw": raw_body}, error=f"JSON Parse Error: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={"success": False, "error_code": "BAD_REQUEST", "error_message": "Invalid JSON payload"}
        )

    # 2. Verify Secret
    settings = get_settings()
    if settings.vapi_secret and x_vapi_secret != settings.vapi_secret:
        err_msg = f"Unauthorized: X-Vapi-Secret header '{x_vapi_secret}' does not match expected secret."
        log_webhook_to_db(db, headers, payload, error=err_msg)
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "error_message": "Invalid X-Vapi-Secret header value.",
                "data": None
            }
        )

    # 3. Check message type
    message = payload.get("message", {})
    message_type = message.get("type")
    
    if message_type != "tool-calls":
        # Log and ignore other message types (speech-update, status-update, assistant.started, etc.)
        log_webhook_to_db(db, headers, payload, response={"success": True})
        return JSONResponse(status_code=200, content={"success": True})

    # 4. Validate request schema
    try:
        req = VapiWebhookRequest(**payload)
    except Exception as e:
        err_msg = f"Request validation failed: {str(e)}"
        log_webhook_to_db(db, headers, payload, error=err_msg)
        return JSONResponse(
            status_code=422,
            content={"success": False, "error_code": "VALIDATION_ERROR", "error_message": err_msg}
        )

    # 4. Execute tool calls
    results = []
    call_id = req.message.call.id
    phone_number = req.message.call.phoneNumber

    for tool_call in req.message.toolCallList:
        func_name = tool_call.function.name
        arg_val = tool_call.function.arguments
        
        logger.info(f"Processing Vapi tool call {tool_call.id}: {func_name} with args {arg_val}")

        # Parse arguments safely
        if isinstance(arg_val, dict):
            args = arg_val
        else:
            try:
                args = json.loads(arg_val) if arg_val else {}
            except Exception as e:
                err_resp = APIResponse(
                    success=False,
                    error_code="VALIDATION_ERROR",
                    error_message=f"Failed to parse arguments: {str(e)}",
                )
                results.append(VapiToolResult(toolCallId=tool_call.id, result=err_resp.model_dump_json()))
                continue

        # Inject call_id if missing or empty
        if not args.get("call_id") and call_id:
            args["call_id"] = call_id

        # Execute router logic
        try:
            if func_name == "find_doctors":
                req_obj = FindDoctorsRequest(**args)
                resp = find_doctors(req_obj, db)

            elif func_name == "check_availability":
                req_obj = CheckAvailabilityRequest(**args)
                resp = check_availability(req_obj, db)

            elif func_name == "recommend_alternatives":
                req_obj = RecommendAlternativesRequest(**args)
                resp = recommend_alternatives(req_obj, db)

            elif func_name == "book_appointment":
                # Inject caller phone if missing
                if not args.get("patient_phone") and phone_number:
                    args["patient_phone"] = phone_number
                req_obj = BookAppointmentRequest(**args)
                resp = book_appointment_endpoint(req_obj, db)

            elif func_name == "reschedule_appointment":
                if not args.get("patient_phone") and phone_number:
                    args["patient_phone"] = phone_number
                req_obj = RescheduleAppointmentRequest(**args)
                resp = reschedule_appointment_endpoint(req_obj, db)

            elif func_name == "cancel_appointment":
                if not args.get("patient_phone") and phone_number:
                    args["patient_phone"] = phone_number
                req_obj = CancelAppointmentRequest(**args)
                resp = cancel_appointment_endpoint(req_obj, db)

            elif func_name == "find_patient_appointments":
                if not args.get("patient_phone") and phone_number:
                    args["patient_phone"] = phone_number
                req_obj = FindPatientAppointmentsRequest(**args)
                resp = find_patient_appointments(req_obj, db)

            else:
                resp = APIResponse(
                    success=False,
                    error_code="VALIDATION_ERROR",
                    error_message=f"Unknown function: {func_name}",
                )

        except Exception as e:
            # Catch standard HTTPException or database/validation error
            if hasattr(e, "detail") and isinstance(e.detail, dict):
                err_resp = APIResponse(
                    success=False,
                    error_code=e.detail.get("error_code", "INTERNAL_ERROR"),
                    error_message=e.detail.get("error_message", str(e)),
                )
            else:
                err_code = "INTERNAL_ERROR"
                if hasattr(e, "status_code") and e.status_code == 422:
                    err_code = "VALIDATION_ERROR"
                err_resp = APIResponse(
                    success=False,
                    error_code=err_code,
                    error_message=str(e),
                )
            results.append(VapiToolResult(toolCallId=tool_call.id, result=err_resp.model_dump_json()))
            continue

        # Append successful result
        results.append(VapiToolResult(toolCallId=tool_call.id, result=resp.model_dump_json()))

    resp_obj = VapiWebhookResponse(results=results)
    
    # 5. Log success response to DB
    log_webhook_to_db(db, headers, payload, response=resp_obj.model_dump())
    
    return resp_obj
