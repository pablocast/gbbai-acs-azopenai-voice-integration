from enum import Enum
from semantic_kernel.processes import ProcessBuilder
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext
from typing import Optional, Dict
from dataclasses import dataclass
from semantic_kernel.functions import kernel_function

#============================================================================
# Data Model for Appointment
#============================================================================
@dataclass
class AppointmentData:
    patient_name: Optional[str] = None
    contact_number: Optional[str] = None
    specialty: Optional[str] = None
    insurance_type: Optional[str] = None
    clinic: Optional[str] = None
    doctor_name: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    notification_preference: Optional[str] = None

#============================================================================
# Mapping Scripted Responses
#============================================================================
SCRIPTED_RESPONSES = {
    "GreetingStep": "Bienvenido a la Red de Clínicas Bupa. ¿En qué podemos ayudarte hoy? ¿Desea agendar una hora médica, consultar una hora ya agendada, o necesita otra información?",
    "SpecialtySelectionStep": "¿Con qué tipo de especialista desea atenderse?",
    "ClinicSelectionStep": "¿En cuál de nuestras clínicas desea atenderse?",
    "AvailabilitySearchStep": "Tenemos una hora disponible con el Dr./Dra. {nombre} el {fecha} a las {hora}. ¿Le acomoda?",
    "PatientDataStep": "¿Cuál es su nombre completo y número de contacto? ¿Desea que le enviemos un recordatorio por SMS o correo electrónico?",
    "AppointmentConfirmationStep": "Su hora ha sido agendada para el {fecha} a las {hora} con el Dr./Dra. {nombre} en la Clínica {clinica}. Recibirá un mensaje de confirmación con los detalles.",
    "ClosingStep": "¿Hay algo más en lo que podamos ayudarle? Gracias por llamar a la Red de Clínicas Bupa. Que tenga un buen día."
}

#============================================================================
# Step 1: Greeting Step
#============================================================================
class GreetingStep(KernelProcessStep):
    class Functions(Enum):
        InitialGreeting = "InitialGreeting"

    class OutputEvents(Enum):
        ServiceRequested = "ServiceRequested"

    @kernel_function(name=Functions.InitialGreeting)
    async def initial_greeting(self, context: KernelProcessStepContext):
        greeting = SCRIPTED_RESPONSES["GreetingStep"]
        print(f"GREETING: {greeting}")
        
        appointment_data = AppointmentData()
        await context.emit_event(
            process_event=GreetingStep.OutputEvents.ServiceRequested,
            data={"prompt": greeting, "appointment_data": appointment_data}
        )

#============================================================================
# Step 2: Service Selection Step
#============================================================================
class ServiceSelectionStep(KernelProcessStep):
    class Functions(Enum):
        SelectService = "SelectService"

    class OutputEvents(Enum):
        ScheduleAppointment = "ScheduleAppointment"
        CheckAppointment = "CheckAppointment"
        OtherInformation = "OtherInformation"

    @kernel_function(name=Functions.SelectService)
    async def select_service(self, context: KernelProcessStepContext, appointment_data: AppointmentData, service_type: str):
        print(f"SERVICE_SELECTION: Patient requested '{service_type}'")
        
        if service_type == "book_appointment":
            await context.emit_event(
                process_event=ServiceSelectionStep.OutputEvents.ScheduleAppointment,
                data=appointment_data
            )
        elif service_type == "check_appointment":   
            await context.emit_event(
                process_event=ServiceSelectionStep.OutputEvents.CheckAppointment,
                data=appointment_data
            )
        else:
            await context.emit_event(
                process_event=ServiceSelectionStep.OutputEvents.OtherInformation,
                data=appointment_data
            )

#============================================================================
# Step 3: Specialty Selection Step
#============================================================================
class SpecialtySelectionStep(KernelProcessStep):
    class Functions(Enum):
        SelectSpecialty = "SelectSpecialty"

    class OutputEvents(Enum):
        SpecialtySelected = "SpecialtySelected"

    @kernel_function(name=Functions.SelectSpecialty)
    async def select_specialty(self, context: KernelProcessStepContext, appointment_data: AppointmentData):
        print(f"SPECIALTY_SELECTION: Patient selected '{appointment_data.specialty}'")
        await context.emit_event(
            process_event=SpecialtySelectionStep.OutputEvents.SpecialtySelected,
            data=appointment_data,
        )




#============================================================================
# Step N: Closing Step
#============================================================================
class ClosingStep(KernelProcessStep):
    class Functions(Enum):
        CloseCall = "CloseCall"

    class OutputEvents(Enum):
        CallClosed = "CallClosed"

    @kernel_function(name=Functions.CloseCall)
    async def close_call(self, context: KernelProcessStepContext, appointment_data: AppointmentData):
        closing_message = "¿Hay algo más en lo que podamos ayudarle? Gracias por llamar a la Red de Clínicas Bupa. Que tenga un buen día."
        print(f"CLOSING: {closing_message}")
        
        await context.emit_event(
            process_event=ClosingStep.OutputEvents.CallClosed,
            data=appointment_data
        )


#============================================================================
# PROCESS: Medical Appointment Process
#============================================================================
class MedicalAppointmentProcess:
    class MedicalAppointmentEvents(Enum):
        StartProcess = "StartProcess"
        UserInputReceived = "UserInputReceived"
        IntentIdentified = "IntentIdentified"
        ServiceIdentified = "ServiceIdentified"
        ContinueToNextStep = "ContinueToNextStep"
        SpecialtySelected = "SpecialtySelected"
        ClinicSelected = "ClinicSelected"
        AvailabilityFound = "AvailabilityFound"
        PatientDataCollected = "PatientDataCollected"
        AppointmentConfirmed = "AppointmentConfirmed"
        ProcessComplete = "ProcessComplete"
        Exit = "Exit"

    @staticmethod
    def create_process(process_name: str = "MedicalAppointmentProcess") -> ProcessBuilder:
        process_builder = ProcessBuilder(process_name)

        # Define steps
        greeting_step = process_builder.add_step(GreetingStep)
        service_selection_step = process_builder.add_step(ServiceSelectionStep)
        specialty_selection_step = process_builder.add_step(SpecialtySelectionStep)
        # clinic_selection_step = process_builder.add_step(ClinicSelectionStep)
        # availability_search_step = process_builder.add_step(AvailabilitySearchStep)
        # patient_data_step = process_builder.add_step(PatientDataStep)
        # appointment_confirmation_step = process_builder.add_step(AppointmentConfirmationStep)
        closing_step = process_builder.add_step(ClosingStep)

        # Define workflow connections
        process_builder.on_input_event(MedicalAppointmentProcess.MedicalAppointmentEvents.StartProcess).send_event_to(greeting_step)
        greeting_step.on_event(GreetingStep.OutputEvents.ServiceRequested).send_event_to(service_selection_step, parameter_name="appointment_data")
        service_selection_step.on_event(ServiceSelectionStep.OutputEvents.ScheduleAppointment).send_event_to(specialty_selection_step)
        service_selection_step.on_event(ServiceSelectionStep.OutputEvents.CheckAppointment).send_event_to(closing_step)
        service_selection_step.on_event(ServiceSelectionStep.OutputEvents.OtherInformation).send_event_to(closing_step)

        specialty_selection_step.on_event(SpecialtySelectionStep.OutputEvents.SpecialtySelected).send_event_to(closing_step)

        # clinic_selection_step.on_event(ClinicSelectionStep.OutputEvents.ClinicSelected).send_event_to(availability_search_step)

        # availability_search_step.on_event(AvailabilitySearchStep.OutputEvents.AvailabilityFound).send_event_to(patient_data_step)
        # availability_search_step.on_event(AvailabilitySearchStep.OutputEvents.NoAvailability).send_event_to(closing_step)

        # patient_data_step.on_event(PatientDataStep.OutputEvents.PatientDataCollected).send_event_to(appointment_confirmation_step)

        # appointment_confirmation_step.on_event(AppointmentConfirmationStep.OutputEvents.AppointmentConfirmed).send_event_to(closing_step)
        closing_step.on_event(ClosingStep.OutputEvents.CallClosed).send_event_to(greeting_step, parameter_name="state")
        # closing_step.on_event(ClosingStep.OutputEvents.CallClosed).stop_process()

        return process_builder
 