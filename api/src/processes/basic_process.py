import os
from enum import Enum
from pathlib import Path
import json
import asyncio
from typing import Optional, Dict

from semantic_kernel.processes.local_runtime.local_kernel_process import start
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.processes.kernel_process import (
    KernelProcess, 
    KernelProcessEvent,
    KernelProcessStateMetadata
)

from semantic_kernel import Kernel
from medical_appointment_process import MedicalAppointmentProcess

STATEFUL_MEDICAL_APPOINTMENT_PROCESS_FILENAME = "stateful_medical_appointment_process.json"

# ============================================================================
# Mapping of Events to Medical Appointment Process Steps
# ============================================================================
STEP_TO_EVENT_MAPPING = {
    "GreetingStep": MedicalAppointmentProcess.MedicalAppointmentEvents.StartProcess,
    "ServiceSelectionStep": MedicalAppointmentProcess.MedicalAppointmentEvents.ServiceIdentified,
    "SpecialtySelectionStep": MedicalAppointmentProcess.MedicalAppointmentEvents.SpecialtySelected,
    "AvailabilitySearchStep": MedicalAppointmentProcess.MedicalAppointmentEvents.AvailabilityFound,
    "PatientDataStep": MedicalAppointmentProcess.MedicalAppointmentEvents.PatientDataCollected,
    "AppointmentConfirmationStep": MedicalAppointmentProcess.MedicalAppointmentEvents.AppointmentConfirmed,
    "ProcessComplete": MedicalAppointmentProcess.MedicalAppointmentEvents.ProcessComplete,
    "Exit": MedicalAppointmentProcess.MedicalAppointmentEvents.Exit
}

# ============================================================================
def _create_kernel_with_chat_completion(service_id: str) -> Kernel:
    kernel = Kernel()
    azure_openai_chat_service = AzureChatCompletion(
            service_id=service_id,
            deployment_name=os.getenv("AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION")
    )
    kernel.add_service(azure_openai_chat_service, overwrite=True)
    return kernel

# Execute a process with the provided state and kernel.
async def execute_process_with_state(
    process: KernelProcess,
    kernel: Kernel, 
    external_trigger_event: Enum,
    data: Optional[str] = None,
    existing_state: KernelProcessStateMetadata | None = None
    ) -> KernelProcess:
    """
    Starts the provided KernelProcess (with optional existing state),
    returns the updated state after the run.
    """
    print(f"=== {external_trigger_event.value} ===")
    event_data = [data] if data else []
    async with await start(
        process,
        kernel,
        KernelProcessEvent(id=external_trigger_event.value, data=event_data),
        state=existing_state
    ) as running_process:
        return await running_process.get_state()

# ============================================================================
BASE_DIR = Path(__file__).resolve().parent
PROCESS_STATE_DIRECTORY = BASE_DIR / "processes_states"
PROCESS_STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)

def dump_process_state_metadata_locally(process_state: KernelProcessStateMetadata, json_filename: str) -> None:
    """
    Saves the ProcessStateMetadata to a local JSON file in step03/processes_states,
    relative to the current script's grandparent folder.
    """
    file_path = PROCESS_STATE_DIRECTORY / json_filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(process_state.model_dump(exclude_none=True, by_alias=True, mode="json"), f, indent=4)
    print(f"Process state saved to '{file_path.resolve()}'")


def load_process_state_metadata(json_filename: str) -> KernelProcessStateMetadata | None:
    """
    Loads the ProcessStateMetadata from step03/processes_states if it exists.
    Returns None if the file doesn't exist or fails to parse.
    """
    file_path = PROCESS_STATE_DIRECTORY / json_filename
    if not file_path.exists():
        print(f"No such file: '{file_path.resolve()}'")
        return None

    try:
        with open(file_path, encoding="utf-8") as f:
            json_str = f.read()
            return KernelProcessStateMetadata.model_validate_json(json_str)
    except Exception as ex:
        print(f"Error reading state file '{file_path.resolve()}': {ex}")
        return None

def get_last_processed_step(previous_state: Dict[str, KernelProcessStateMetadata]) -> Dict[str, KernelProcessStateMetadata]:
    for step_name, step_metadata in reversed(previous_state.items()):
        last_step = {step_name: step_metadata}
        break
    return last_step 

# ============================================================================
async def resume_medical_appointment_process(
        user_message: Optional[str] = None
    ):
    """
    Resumes the Medical Appointment stateful process from a saved state.
    """
    kernel = _create_kernel_with_chat_completion("default")
    builder = MedicalAppointmentProcess.create_process()
    medical_appointment_process = builder.build()

    previous_state = load_process_state_metadata(STATEFUL_MEDICAL_APPOINTMENT_PROCESS_FILENAME)
    last_step_name = None
    if previous_state:
        last_step = get_last_processed_step(previous_state.steps_state)
        last_step_name = list(last_step.keys())[0]
        print(f"✅ Loaded previous state from step: {last_step_name}")

    print("=== Start resume_medical_appointment_process ===")
    event = STEP_TO_EVENT_MAPPING.get(last_step_name, MedicalAppointmentProcess.MedicalAppointmentEvents.StartProcess)
    final_state = await execute_process_with_state(
        medical_appointment_process,
        kernel,
        event,
        data={"last_step": last_step_name, "user_message": user_message}
    )

    process_state_metadata = final_state.to_process_state_metadata()
    dump_process_state_metadata_locally(process_state_metadata, STATEFUL_MEDICAL_APPOINTMENT_PROCESS_FILENAME)
    print("=== End resume_medical_appointment_process ===\n")

async def main():
    """
    Main function to run the stateful medical appointment process.
    """
    print("=== Starting stateful medical appointment process ===")
    await resume_medical_appointment_process('This is some data')
    print("=== Completed stateful medical appointment process ===")


if __name__ == "__main__":
    asyncio.run(main())