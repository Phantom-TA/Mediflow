import json
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.tools import verify_vapi_secret
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


@router.post("/tool", response_model=VapiWebhookResponse, dependencies=[Depends(verify_vapi_secret)])
def vapi_tool_webhook(req: VapiWebhookRequest, db: Session = Depends(get_db)):
    """
    Unified Vapi webhook handler for tool calls.
    Parses arguments, routes internally, captures exceptions, and returns the Vapi-expected response envelope.
    """
    results = []
    call_id = req.message.call.id
    phone_number = req.message.call.phoneNumber

    for tool_call in req.message.toolCallList:
        func_name = tool_call.function.name
        arg_str = tool_call.function.arguments
        
        logger.info(f"Processing Vapi tool call {tool_call.id}: {func_name} with args {arg_str}")

        # Parse arguments safely
        try:
            args = json.loads(arg_str) if arg_str else {}
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
                # Standard APIResponse exception raised by endpoints
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
        # resp is an APIResponse object, we serialize it to json string
        results.append(VapiToolResult(toolCallId=tool_call.id, result=resp.model_dump_json()))

    return VapiWebhookResponse(results=results)
