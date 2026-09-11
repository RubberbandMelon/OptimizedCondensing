from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from execute import CondenserController, configure_logger

from loguru import logger

# =========================================================
# Response models
# =========================================================

class StatusResponse(BaseModel):
    state: str
    condense_running: bool
    waiting_for_confirmation: bool

    temp_1k: float
    temp_sorb: float

    sorb_setpoint: float
    heater_range: int


class CommandResponse(BaseModel):
    success: bool
    message: str


# =========================================================
# FastAPI lifespan
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    configure_logger()

    # executed once when FastAPI starts
    controller = CondenserController()
    controller.start()

    app.state.controller = controller

    logger.info("Condenser API ready")

    try:
        yield

    finally:

        # executed when uvicorn/systemd shuts down
        logger.info("Shutting down condenser API")
        controller.stop()


# =========================================================
# FastAPI application
# =========================================================

app = FastAPI(
    title="Condenser Control API",
    version="1.0",
    lifespan=lifespan
)


def get_controller(request: Request) -> CondenserController:
    return request.app.state.controller


# =========================================================
# STATUS
# =========================================================

@app.get(
    "/status",
    response_model=StatusResponse
)
def get_status(request: Request):

    controller = get_controller(request)

    return controller.get_status()


# =========================================================
# START
# =========================================================

@app.post(
    "/condense/start",
    response_model=CommandResponse
)
def start_condensation(request: Request):

    controller = get_controller(request)

    success = controller.start_condense()

    if not success:
        raise HTTPException(
            status_code=409,
            detail="Condensation is already running"
        )

    return {
        "success": True,
        "message": "Condensation started"
    }


# =========================================================
# CONFIRM
# =========================================================

@app.post(
    "/condense/confirm",
    response_model=CommandResponse
)
def confirm_valves(request: Request):

    controller = get_controller(request)

    success = controller.confirm()

    if not success:
        raise HTTPException(
            status_code=409,
            detail="Condensation is not waiting for confirmation"
        )

    return {
        "success": True,
        "message": "Valve state confirmed"
    }


# =========================================================
# ABORT
# =========================================================

@app.post(
    "/condense/abort",
    response_model=CommandResponse
)
def abort_condensation(request: Request):

    controller = get_controller(request)

    success = controller.abort_condense()

    if not success:
        raise HTTPException(
            status_code=409,
            detail="No condensation is currently running"
        )

    return {
        "success": True,
        "message": "Abort requested"
    }